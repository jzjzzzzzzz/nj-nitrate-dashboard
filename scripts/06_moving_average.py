import os
import json
import math
import pandas as pd


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

NITRATE_CSV = os.path.join(DATA_DIR, "processed", "nitrate_standardized.csv")
STATION_SUMMARY_CSV = os.path.join(DATA_DIR, "processed", "station_summary.csv")

PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
DASHBOARD_DIR = os.path.join(OUTPUT_DIR, "dashboard")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

YEARLY_TREND_CSV = os.path.join(PROCESSED_DIR, "yearly_trend_summary.csv")
MONTHLY_TREND_CSV = os.path.join(PROCESSED_DIR, "monthly_trend_summary.csv")
MOVING_AVERAGE_CSV = os.path.join(PROCESSED_DIR, "moving_average_summary.csv")
HOTSPOT_MOVING_AVERAGE_CSV = os.path.join(PROCESSED_DIR, "hotspot_moving_average.csv")

YEARLY_TREND_JSON = os.path.join(DASHBOARD_DIR, "yearly_trend_chart.json")
MONTHLY_MOVING_AVERAGE_JSON = os.path.join(DASHBOARD_DIR, "monthly_moving_average_chart.json")
HOTSPOT_MOVING_AVERAGE_JSON = os.path.join(DASHBOARD_DIR, "hotspot_moving_average_chart.json")

LOG_FILE = os.path.join(LOG_DIR, "06_moving_average_log.txt")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Helper functions
# ============================================================

def write_log(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def check_input_files():
    if not os.path.exists(NITRATE_CSV):
        raise FileNotFoundError(
            f"Input file not found:\n{NITRATE_CSV}\n\n"
            "Run Step 3 first:\n"
            "python scripts/03_station_summary.py"
        )

    if not os.path.exists(STATION_SUMMARY_CSV):
        raise FileNotFoundError(
            f"Input file not found:\n{STATION_SUMMARY_CSV}\n\n"
            "Run Step 3 first:\n"
            "python scripts/03_station_summary.py"
        )


def clean_for_json(value):
    if pd.isna(value):
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    if isinstance(value, int):
        return int(value)

    if isinstance(value, bool):
        return bool(value)

    return value


def df_to_json_records(df):
    records = []

    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            item[col] = clean_for_json(row[col])
        records.append(item)

    return records


# ============================================================
# Main moving average analysis
# ============================================================

def moving_average_analysis():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 6: Moving Average Trend Analysis ==========")

    check_input_files()

    write_log(f"[READ] {NITRATE_CSV}")
    nitrate_df = pd.read_csv(NITRATE_CSV, low_memory=False)

    write_log(f"[READ] {STATION_SUMMARY_CSV}")
    station_df = pd.read_csv(STATION_SUMMARY_CSV, low_memory=False)

    write_log(f"Nitrate rows: {len(nitrate_df):,}")
    write_log(f"Station summary rows: {len(station_df):,}")

    nitrate_df["date"] = pd.to_datetime(nitrate_df["date"], errors="coerce")
    nitrate_df["nitrate_mg_L"] = pd.to_numeric(nitrate_df["nitrate_mg_L"], errors="coerce")

    nitrate_df = nitrate_df[
        nitrate_df["date"].notna()
        & nitrate_df["nitrate_mg_L"].notna()
        & nitrate_df["station_id"].notna()
    ].copy()

    nitrate_df["year"] = nitrate_df["date"].dt.year
    nitrate_df["month"] = nitrate_df["date"].dt.month
    nitrate_df["year_month"] = nitrate_df["date"].dt.to_period("M").astype(str)

    # Add hotspot flag
    station_flags = station_df[["station_id", "is_hotspot", "confidence_level"]].copy()

    nitrate_df = nitrate_df.merge(
        station_flags,
        on="station_id",
        how="left"
    )

    nitrate_df["is_hotspot"] = nitrate_df["is_hotspot"].fillna(False)
    nitrate_df["confidence_level"] = nitrate_df["confidence_level"].fillna("Unknown")

    write_log(f"Rows after required fields filter: {len(nitrate_df):,}")

    # ------------------------------------------------------------
    # 1. Yearly trend summary
    # ------------------------------------------------------------

    yearly_summary = nitrate_df.groupby("year").agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
    ).reset_index()

    yearly_summary = yearly_summary.sort_values("year")

    yearly_summary["mean_3yr_moving_average"] = yearly_summary["mean_nitrate_mg_L"].rolling(
        window=3,
        min_periods=1
    ).mean()

    yearly_summary["median_3yr_moving_average"] = yearly_summary["median_nitrate_mg_L"].rolling(
        window=3,
        min_periods=1
    ).mean()

    yearly_summary.to_csv(YEARLY_TREND_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # 2. Monthly trend summary
    # ------------------------------------------------------------

    monthly_summary = nitrate_df.groupby("year_month").agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
    ).reset_index()

    monthly_summary["date"] = pd.to_datetime(monthly_summary["year_month"] + "-01")
    monthly_summary = monthly_summary.sort_values("date")

    monthly_summary["mean_6mo_moving_average"] = monthly_summary["mean_nitrate_mg_L"].rolling(
        window=6,
        min_periods=3
    ).mean()

    monthly_summary["mean_12mo_moving_average"] = monthly_summary["mean_nitrate_mg_L"].rolling(
        window=12,
        min_periods=6
    ).mean()

    monthly_summary["median_12mo_moving_average"] = monthly_summary["median_nitrate_mg_L"].rolling(
        window=12,
        min_periods=6
    ).mean()

    monthly_summary.to_csv(MONTHLY_TREND_CSV, index=False, encoding="utf-8")
    monthly_summary.to_csv(MOVING_AVERAGE_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # 3. Hotspot vs Non-hotspot moving average
    # ------------------------------------------------------------

    nitrate_df["site_group"] = nitrate_df["is_hotspot"].apply(
        lambda x: "Hotspot Stations" if x else "Non-Hotspot Stations"
    )

    hotspot_monthly = nitrate_df.groupby(["year_month", "site_group"]).agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
    ).reset_index()

    hotspot_monthly["date"] = pd.to_datetime(hotspot_monthly["year_month"] + "-01")
    hotspot_monthly = hotspot_monthly.sort_values(["site_group", "date"])

    hotspot_monthly["mean_6mo_moving_average"] = hotspot_monthly.groupby("site_group")[
        "mean_nitrate_mg_L"
    ].transform(lambda x: x.rolling(window=6, min_periods=3).mean())

    hotspot_monthly["mean_12mo_moving_average"] = hotspot_monthly.groupby("site_group")[
        "mean_nitrate_mg_L"
    ].transform(lambda x: x.rolling(window=12, min_periods=6).mean())

    hotspot_monthly.to_csv(HOTSPOT_MOVING_AVERAGE_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # 4. Export JSON
    # ------------------------------------------------------------

    yearly_json_df = yearly_summary.copy()
    monthly_json_df = monthly_summary.copy()
    hotspot_json_df = hotspot_monthly.copy()

    yearly_json_df["year"] = yearly_json_df["year"].astype(int)
    monthly_json_df["date"] = monthly_json_df["date"].astype(str)
    hotspot_json_df["date"] = hotspot_json_df["date"].astype(str)

    with open(YEARLY_TREND_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(yearly_json_df), f, indent=2)

    with open(MONTHLY_MOVING_AVERAGE_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(monthly_json_df), f, indent=2)

    with open(HOTSPOT_MOVING_AVERAGE_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(hotspot_json_df), f, indent=2)

    # ------------------------------------------------------------
    # 5. Logs
    # ------------------------------------------------------------

    write_log("")
    write_log("========== Yearly Trend Summary ==========")

    for _, row in yearly_summary.iterrows():
        write_log(
            f"{int(row['year'])} | "
            f"obs={int(row['observation_count']):,} | "
            f"stations={int(row['station_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"median={row['median_nitrate_mg_L']:.4f} mg/L | "
            f"p90={row['p90_nitrate_mg_L']:.4f} mg/L | "
            f"3yr_MA={row['mean_3yr_moving_average']:.4f} mg/L"
        )

    write_log("")
    write_log("========== Monthly Moving Average Preview ==========")

    preview = monthly_summary.tail(24)

    for _, row in preview.iterrows():
        ma6 = row["mean_6mo_moving_average"]
        ma12 = row["mean_12mo_moving_average"]

        ma6_text = "NA" if pd.isna(ma6) else f"{ma6:.4f}"
        ma12_text = "NA" if pd.isna(ma12) else f"{ma12:.4f}"

        write_log(
            f"{row['year_month']} | "
            f"obs={int(row['observation_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} | "
            f"6mo_MA={ma6_text} | "
            f"12mo_MA={ma12_text}"
        )

    write_log("")
    write_log("========== Hotspot vs Non-Hotspot Latest Moving Average ==========")

    latest_rows = hotspot_monthly.dropna(subset=["mean_12mo_moving_average"]).groupby(
        "site_group"
    ).tail(1)

    for _, row in latest_rows.iterrows():
        write_log(
            f"{row['site_group']} | "
            f"latest_month={row['year_month']} | "
            f"obs={int(row['observation_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} | "
            f"12mo_MA={row['mean_12mo_moving_average']:.4f}"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Yearly trend CSV: {YEARLY_TREND_CSV}")
    write_log(f"Monthly trend CSV: {MONTHLY_TREND_CSV}")
    write_log(f"Moving average CSV: {MOVING_AVERAGE_CSV}")
    write_log(f"Hotspot moving average CSV: {HOTSPOT_MOVING_AVERAGE_CSV}")
    write_log(f"Yearly trend JSON: {YEARLY_TREND_JSON}")
    write_log(f"Monthly moving average JSON: {MONTHLY_MOVING_AVERAGE_JSON}")
    write_log(f"Hotspot moving average JSON: {HOTSPOT_MOVING_AVERAGE_JSON}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 6 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    moving_average_analysis()


if __name__ == "__main__":
    main()