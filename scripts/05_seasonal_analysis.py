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

SEASONAL_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "seasonal_summary.csv")
MONTHLY_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "monthly_summary.csv")
SEASONAL_HOTSPOT_COMPARISON_CSV = os.path.join(PROCESSED_DIR, "seasonal_hotspot_comparison.csv")

SEASONAL_CHART_JSON = os.path.join(DASHBOARD_DIR, "seasonal_chart.json")
MONTHLY_CHART_JSON = os.path.join(DASHBOARD_DIR, "monthly_chart.json")
SEASONAL_HOTSPOT_COMPARISON_JSON = os.path.join(DASHBOARD_DIR, "seasonal_hotspot_comparison.json")

LOG_FILE = os.path.join(LOG_DIR, "05_seasonal_analysis_log.txt")

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


def season_order_value(season):
    order = {
        "Winter": 1,
        "Spring": 2,
        "Summer": 3,
        "Fall": 4,
    }
    return order.get(season, 99)


# ============================================================
# Main seasonal analysis
# ============================================================

def seasonal_analysis():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 5: Seasonal Analysis ==========")

    check_input_files()

    write_log(f"[READ] {NITRATE_CSV}")
    nitrate_df = pd.read_csv(NITRATE_CSV, low_memory=False)

    write_log(f"[READ] {STATION_SUMMARY_CSV}")
    station_df = pd.read_csv(STATION_SUMMARY_CSV, low_memory=False)

    write_log(f"Nitrate rows: {len(nitrate_df):,}")
    write_log(f"Station summary rows: {len(station_df):,}")

    nitrate_df["date"] = pd.to_datetime(nitrate_df["date"], errors="coerce")
    nitrate_df["year"] = pd.to_numeric(nitrate_df["year"], errors="coerce")
    nitrate_df["month"] = pd.to_numeric(nitrate_df["month"], errors="coerce")
    nitrate_df["nitrate_mg_L"] = pd.to_numeric(nitrate_df["nitrate_mg_L"], errors="coerce")

    nitrate_df = nitrate_df[
        nitrate_df["date"].notna()
        & nitrate_df["year"].notna()
        & nitrate_df["month"].notna()
        & nitrate_df["season"].notna()
        & nitrate_df["nitrate_mg_L"].notna()
    ].copy()

    write_log(f"Rows after required fields filter: {len(nitrate_df):,}")

    # Add hotspot and confidence info from station_summary
    station_flags = station_df[
        [
            "station_id",
            "is_hotspot",
            "confidence_level",
            "observation_count",
            "mean_nitrate_mg_L",
            "p90_nitrate_mg_L",
        ]
    ].copy()

    nitrate_df = nitrate_df.merge(
        station_flags,
        on="station_id",
        how="left",
        suffixes=("", "_station")
    )

    nitrate_df["is_hotspot"] = nitrate_df["is_hotspot"].fillna(False)
    nitrate_df["confidence_level"] = nitrate_df["confidence_level"].fillna("Unknown")

    # ------------------------------------------------------------
    # Seasonal summary
    # ------------------------------------------------------------

    seasonal_summary = nitrate_df.groupby("season").agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
    ).reset_index()

    seasonal_summary["season_order"] = seasonal_summary["season"].apply(season_order_value)

    seasonal_summary = seasonal_summary.sort_values("season_order")

    seasonal_summary.to_csv(SEASONAL_SUMMARY_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # Monthly summary
    # ------------------------------------------------------------

    monthly_summary = nitrate_df.groupby("month").agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
    ).reset_index()

    month_names = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    }

    monthly_summary["month_name"] = monthly_summary["month"].map(month_names)

    monthly_summary = monthly_summary.sort_values("month")

    monthly_summary.to_csv(MONTHLY_SUMMARY_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # Seasonal hotspot comparison
    # ------------------------------------------------------------

    nitrate_df["site_group"] = nitrate_df["is_hotspot"].apply(
        lambda x: "Hotspot Stations" if x else "Non-Hotspot Stations"
    )

    seasonal_hotspot_comparison = nitrate_df.groupby(["season", "site_group"]).agg(
        observation_count=("nitrate_mg_L", "count"),
        station_count=("station_id", "nunique"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
    ).reset_index()

    seasonal_hotspot_comparison["season_order"] = seasonal_hotspot_comparison["season"].apply(
        season_order_value
    )

    seasonal_hotspot_comparison = seasonal_hotspot_comparison.sort_values(
        by=["season_order", "site_group"]
    )

    seasonal_hotspot_comparison.to_csv(
        SEASONAL_HOTSPOT_COMPARISON_CSV,
        index=False,
        encoding="utf-8"
    )

    # ------------------------------------------------------------
    # Export JSON
    # ------------------------------------------------------------

    with open(SEASONAL_CHART_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(seasonal_summary), f, indent=2)

    with open(MONTHLY_CHART_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(monthly_summary), f, indent=2)

    with open(SEASONAL_HOTSPOT_COMPARISON_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(seasonal_hotspot_comparison), f, indent=2)

    # ------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------

    write_log("")
    write_log("========== Seasonal Summary ==========")

    for _, row in seasonal_summary.iterrows():
        write_log(
            f"{row['season']} | "
            f"obs={int(row['observation_count']):,} | "
            f"stations={int(row['station_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"median={row['median_nitrate_mg_L']:.4f} mg/L | "
            f"p90={row['p90_nitrate_mg_L']:.4f} mg/L | "
            f"max={row['max_nitrate_mg_L']:.4f} mg/L"
        )

    write_log("")
    write_log("========== Monthly Summary ==========")

    for _, row in monthly_summary.iterrows():
        write_log(
            f"{row['month_name']} | "
            f"obs={int(row['observation_count']):,} | "
            f"stations={int(row['station_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"median={row['median_nitrate_mg_L']:.4f} mg/L | "
            f"p90={row['p90_nitrate_mg_L']:.4f} mg/L"
        )

    write_log("")
    write_log("========== Hotspot vs Non-Hotspot Seasonal Comparison ==========")

    for _, row in seasonal_hotspot_comparison.iterrows():
        write_log(
            f"{row['season']} | {row['site_group']} | "
            f"obs={int(row['observation_count']):,} | "
            f"stations={int(row['station_count']):,} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"median={row['median_nitrate_mg_L']:.4f} mg/L | "
            f"p90={row['p90_nitrate_mg_L']:.4f} mg/L"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Seasonal summary CSV: {SEASONAL_SUMMARY_CSV}")
    write_log(f"Monthly summary CSV: {MONTHLY_SUMMARY_CSV}")
    write_log(f"Seasonal hotspot comparison CSV: {SEASONAL_HOTSPOT_COMPARISON_CSV}")
    write_log(f"Seasonal chart JSON: {SEASONAL_CHART_JSON}")
    write_log(f"Monthly chart JSON: {MONTHLY_CHART_JSON}")
    write_log(f"Seasonal hotspot comparison JSON: {SEASONAL_HOTSPOT_COMPARISON_JSON}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 5 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    seasonal_analysis()


if __name__ == "__main__":
    main()