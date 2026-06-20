import os
import json
import math
import re
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

DASHBOARD_DIR = os.path.join(OUTPUT_DIR, "dashboard")
STATION_DETAILS_DIR = os.path.join(DASHBOARD_DIR, "station_details")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

STATION_DETAIL_INDEX_JSON = os.path.join(DASHBOARD_DIR, "station_detail_index.json")
STATION_DETAIL_INDEX_CSV = os.path.join(TABLES_DIR, "station_detail_index.csv")
LOG_FILE = os.path.join(LOG_DIR, "07_station_detail_export_log.txt")

os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(STATION_DETAILS_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Settings
# ============================================================

MAX_RAW_OBSERVATIONS_PER_STATION = 500


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


def safe_filename(text):
    text = str(text)
    text = re.sub(r"[^A-Za-z0-9_\-]+", "_", text)
    text = text.strip("_")

    if not text:
        text = "unknown_station"

    return text[:150] + ".json"


def season_order_value(season):
    order = {
        "Winter": 1,
        "Spring": 2,
        "Summer": 3,
        "Fall": 4,
    }
    return order.get(season, 99)


# ============================================================
# Station detail export
# ============================================================

def export_station_details():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 7: Export Station Detail Data ==========")

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
        & nitrate_df["station_id"].notna()
        & nitrate_df["nitrate_mg_L"].notna()
    ].copy()

    nitrate_df["year"] = nitrate_df["date"].dt.year
    nitrate_df["month"] = nitrate_df["date"].dt.month
    nitrate_df["year_month"] = nitrate_df["date"].dt.to_period("M").astype(str)

    station_df = station_df[
        station_df["station_id"].notna()
        & station_df["latitude"].notna()
        & station_df["longitude"].notna()
    ].copy()

    # Clear old station detail JSON files
    for file_name in os.listdir(STATION_DETAILS_DIR):
        if file_name.lower().endswith(".json"):
            os.remove(os.path.join(STATION_DETAILS_DIR, file_name))

    index_records = []
    total_exported = 0

    for _, station_row in station_df.iterrows():
        station_id = station_row["station_id"]
        station_data = nitrate_df[nitrate_df["station_id"] == station_id].copy()

        if len(station_data) == 0:
            continue

        station_data = station_data.sort_values("date")

        file_name = safe_filename(station_id)
        relative_path = f"station_details/{file_name}"
        output_path = os.path.join(STATION_DETAILS_DIR, file_name)

        # --------------------------------------------------------
        # Seasonal summary for one station
        # --------------------------------------------------------

        seasonal_summary = station_data.groupby("season").agg(
            observation_count=("nitrate_mg_L", "count"),
            mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
            median_nitrate_mg_L=("nitrate_mg_L", "median"),
            p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
            max_nitrate_mg_L=("nitrate_mg_L", "max"),
        ).reset_index()

        seasonal_summary["season_order"] = seasonal_summary["season"].apply(season_order_value)
        seasonal_summary = seasonal_summary.sort_values("season_order")

        # --------------------------------------------------------
        # Yearly trend for one station
        # --------------------------------------------------------

        yearly_trend = station_data.groupby("year").agg(
            observation_count=("nitrate_mg_L", "count"),
            mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
            median_nitrate_mg_L=("nitrate_mg_L", "median"),
            p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
            max_nitrate_mg_L=("nitrate_mg_L", "max"),
        ).reset_index()

        yearly_trend = yearly_trend.sort_values("year")

        yearly_trend["mean_3yr_moving_average"] = yearly_trend["mean_nitrate_mg_L"].rolling(
            window=3,
            min_periods=1
        ).mean()

        # --------------------------------------------------------
        # Monthly moving average for one station
        # --------------------------------------------------------

        monthly_trend = station_data.groupby("year_month").agg(
            observation_count=("nitrate_mg_L", "count"),
            mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
            median_nitrate_mg_L=("nitrate_mg_L", "median"),
            p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
            max_nitrate_mg_L=("nitrate_mg_L", "max"),
        ).reset_index()

        monthly_trend["date"] = pd.to_datetime(monthly_trend["year_month"] + "-01")
        monthly_trend = monthly_trend.sort_values("date")

        monthly_trend["mean_6mo_moving_average"] = monthly_trend["mean_nitrate_mg_L"].rolling(
            window=6,
            min_periods=3
        ).mean()

        monthly_trend["mean_12mo_moving_average"] = monthly_trend["mean_nitrate_mg_L"].rolling(
            window=12,
            min_periods=6
        ).mean()

        monthly_trend["date"] = monthly_trend["date"].astype(str)

        # --------------------------------------------------------
        # Raw observations
        # --------------------------------------------------------

        raw_cols = [
            "date",
            "year",
            "month",
            "season",
            "nitrate_mg_L",
            "result_value",
            "unit",
            "characteristic",
            "nitrate_category",
            "sample_fraction",
            "activity_type",
            "provider",
            "result_status",
            "value_type",
            "detection_condition",
        ]

        raw_cols = [col for col in raw_cols if col in station_data.columns]

        raw_observations = station_data[raw_cols].copy()
        raw_observations["date"] = raw_observations["date"].astype(str)

        if len(raw_observations) > MAX_RAW_OBSERVATIONS_PER_STATION:
            raw_observations = raw_observations.tail(MAX_RAW_OBSERVATIONS_PER_STATION)

        # --------------------------------------------------------
        # Build JSON
        # --------------------------------------------------------

        station_json = {
            "station_info": {
                "station_id": clean_for_json(station_row["station_id"]),
                "station_name": clean_for_json(station_row["station_name"]),
                "latitude": clean_for_json(station_row["latitude"]),
                "longitude": clean_for_json(station_row["longitude"]),
                "provider": clean_for_json(station_row["provider"]),
                "nitrate_categories": clean_for_json(station_row["nitrate_categories"]),
                "units_seen": clean_for_json(station_row["units_seen"]),
            },
            "summary": {
                "observation_count": int(station_row["observation_count"]),
                "confidence_level": clean_for_json(station_row["confidence_level"]),
                "confidence_score": clean_for_json(station_row["confidence_score"]),
                "mean_nitrate_mg_L": clean_for_json(station_row["mean_nitrate_mg_L"]),
                "median_nitrate_mg_L": clean_for_json(station_row["median_nitrate_mg_L"]),
                "p90_nitrate_mg_L": clean_for_json(station_row["p90_nitrate_mg_L"]),
                "max_nitrate_mg_L": clean_for_json(station_row["max_nitrate_mg_L"]),
                "min_nitrate_mg_L": clean_for_json(station_row["min_nitrate_mg_L"]),
                "first_year": int(station_row["first_year"]),
                "last_year": int(station_row["last_year"]),
                "is_hotspot": bool(station_row["is_hotspot"]),
                "is_p90_hotspot": bool(station_row["is_p90_hotspot"]),
                "is_mean_hotspot": bool(station_row["is_mean_hotspot"]),
            },
            "seasonal_summary": df_to_json_records(seasonal_summary),
            "yearly_trend": df_to_json_records(yearly_trend),
            "monthly_trend": df_to_json_records(monthly_trend),
            "raw_observations": df_to_json_records(raw_observations),
            "notes": {
                "raw_observation_limit": MAX_RAW_OBSERVATIONS_PER_STATION,
                "confidence_rule": "High: >=100 observations; Medium: 30-99 observations; Low: <30 observations.",
                "interpretation_warning": "Low-confidence stations should not be overinterpreted."
            }
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(station_json, f, indent=2)

        index_records.append({
            "station_id": clean_for_json(station_row["station_id"]),
            "station_name": clean_for_json(station_row["station_name"]),
            "latitude": clean_for_json(station_row["latitude"]),
            "longitude": clean_for_json(station_row["longitude"]),
            "observation_count": int(station_row["observation_count"]),
            "confidence_level": clean_for_json(station_row["confidence_level"]),
            "mean_nitrate_mg_L": clean_for_json(station_row["mean_nitrate_mg_L"]),
            "p90_nitrate_mg_L": clean_for_json(station_row["p90_nitrate_mg_L"]),
            "max_nitrate_mg_L": clean_for_json(station_row["max_nitrate_mg_L"]),
            "is_hotspot": bool(station_row["is_hotspot"]),
            "detail_json": relative_path,
        })

        total_exported += 1

        if total_exported % 500 == 0:
            write_log(f"[EXPORT] Station detail files exported: {total_exported:,}")

    index_df = pd.DataFrame(index_records)

    index_df = index_df.sort_values(
        by=["is_hotspot", "p90_nitrate_mg_L", "mean_nitrate_mg_L", "observation_count"],
        ascending=[False, False, False, False]
    )

    index_df.to_csv(STATION_DETAIL_INDEX_CSV, index=False, encoding="utf-8")

    with open(STATION_DETAIL_INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(index_df), f, indent=2)

    write_log("")
    write_log("========== Station Detail Export Summary ==========")
    write_log(f"Station detail files exported: {total_exported:,}")
    write_log(f"Index rows: {len(index_df):,}")
    write_log(f"Hotspot stations in index: {int(index_df['is_hotspot'].sum()):,}")

    write_log("")
    write_log("========== Top 10 Detail Index ==========")

    top10 = index_df.head(10)

    for _, row in top10.iterrows():
        write_log(
            f"{row['station_id']} | "
            f"count={row['observation_count']} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} | "
            f"p90={row['p90_nitrate_mg_L']:.4f} | "
            f"confidence={row['confidence_level']} | "
            f"file={row['detail_json']}"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Station detail index JSON: {STATION_DETAIL_INDEX_JSON}")
    write_log(f"Station detail index CSV: {STATION_DETAIL_INDEX_CSV}")
    write_log(f"Station detail files folder: {STATION_DETAILS_DIR}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 7 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    export_station_details()


if __name__ == "__main__":
    main()