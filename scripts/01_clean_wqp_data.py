import os
import pandas as pd


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

INPUT_CSV = os.path.join(DATA_DIR, "combined", "wqp_nj_2000_2026_combined.csv")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

OUTPUT_CSV = os.path.join(PROCESSED_DIR, "clean_results.csv")
LOG_FILE = os.path.join(LOG_DIR, "01_clean_wqp_data_log.txt")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Performance settings
# ============================================================

CHUNK_SIZE = 100_000


# ============================================================
# Columns to keep
# ============================================================

KEEP_COLUMNS = [
    "OrganizationIdentifier",
    "OrganizationFormalName",
    "ProviderName",

    "ActivityIdentifier",
    "ActivityTypeCode",
    "ActivityMediaName",
    "ActivityMediaSubdivisionName",
    "ActivityStartDate",
    "ActivityStartTime/Time",
    "ActivityStartTime/TimeZoneCode",

    "MonitoringLocationIdentifier",
    "MonitoringLocationName",
    "ActivityLocation/LatitudeMeasure",
    "ActivityLocation/LongitudeMeasure",

    "CharacteristicName",
    "ResultSampleFractionText",
    "ResultMeasureValue",
    "ResultMeasure/MeasureUnitCode",
    "MeasureQualifierCode",
    "ResultStatusIdentifier",
    "ResultValueTypeName",
    "ResultDetectionConditionText",
    "USGSPCode",

    "ResultAnalyticalMethod/MethodIdentifier",
    "ResultAnalyticalMethod/MethodName",
    "DetectionQuantitationLimitTypeName",
    "DetectionQuantitationLimitMeasure/MeasureValue",
    "DetectionQuantitationLimitMeasure/MeasureUnitCode",
    "LastUpdated",
]


# ============================================================
# Rename columns
# ============================================================

RENAME_COLUMNS = {
    "OrganizationIdentifier": "organization_id",
    "OrganizationFormalName": "organization_name",
    "ProviderName": "provider",

    "ActivityIdentifier": "activity_id",
    "ActivityTypeCode": "activity_type",
    "ActivityMediaName": "media",
    "ActivityMediaSubdivisionName": "media_subdivision",
    "ActivityStartDate": "date",
    "ActivityStartTime/Time": "time",
    "ActivityStartTime/TimeZoneCode": "timezone",

    "MonitoringLocationIdentifier": "station_id",
    "MonitoringLocationName": "station_name",
    "ActivityLocation/LatitudeMeasure": "latitude",
    "ActivityLocation/LongitudeMeasure": "longitude",

    "CharacteristicName": "characteristic",
    "ResultSampleFractionText": "sample_fraction",
    "ResultMeasureValue": "result_value",
    "ResultMeasure/MeasureUnitCode": "unit",
    "MeasureQualifierCode": "qualifier",
    "ResultStatusIdentifier": "result_status",
    "ResultValueTypeName": "value_type",
    "ResultDetectionConditionText": "detection_condition",
    "USGSPCode": "usgs_pcode",

    "ResultAnalyticalMethod/MethodIdentifier": "method_id",
    "ResultAnalyticalMethod/MethodName": "method_name",
    "DetectionQuantitationLimitTypeName": "detection_limit_type",
    "DetectionQuantitationLimitMeasure/MeasureValue": "detection_limit_value",
    "DetectionQuantitationLimitMeasure/MeasureUnitCode": "detection_limit_unit",
    "LastUpdated": "last_updated",
}


# ============================================================
# Helper functions
# ============================================================

def write_log(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def get_season(month):
    if pd.isna(month):
        return None

    month = int(month)

    if month in [12, 1, 2]:
        return "Winter"
    if month in [3, 4, 5]:
        return "Spring"
    if month in [6, 7, 8]:
        return "Summer"
    if month in [9, 10, 11]:
        return "Fall"

    return None


def check_input_file():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_CSV}\n\n"
            "Make sure your combined WQP file is located at:\n"
            "data/combined/wqp_nj_2000_2026_combined.csv"
        )


def get_existing_columns():
    header = pd.read_csv(INPUT_CSV, nrows=0)
    all_columns = list(header.columns)

    existing_columns = [col for col in KEEP_COLUMNS if col in all_columns]
    missing_columns = [col for col in KEEP_COLUMNS if col not in all_columns]

    return all_columns, existing_columns, missing_columns


# ============================================================
# Clean one chunk
# ============================================================

def clean_chunk(df):
    df = df.copy()

    df = df.rename(columns=RENAME_COLUMNS)

    text_columns = [
        "organization_id",
        "organization_name",
        "provider",
        "activity_id",
        "activity_type",
        "media",
        "media_subdivision",
        "station_id",
        "station_name",
        "characteristic",
        "sample_fraction",
        "unit",
        "qualifier",
        "result_status",
        "value_type",
        "detection_condition",
        "usgs_pcode",
        "method_id",
        "method_name",
        "detection_limit_type",
        "detection_limit_unit",
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["season"] = df["month"].apply(get_season)

    df["result_value_raw"] = df["result_value"]
    df["result_value"] = pd.to_numeric(df["result_value"], errors="coerce")

    if "detection_limit_value" in df.columns:
        df["detection_limit_value"] = pd.to_numeric(
            df["detection_limit_value"],
            errors="coerce"
        )

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df["is_not_detected"] = False
    if "detection_condition" in df.columns:
        df["is_not_detected"] = df["detection_condition"].fillna("").str.contains(
            "Not Detected",
            case=False,
            regex=False
        )

    df["is_qc_sample"] = False
    if "activity_type" in df.columns:
        df["is_qc_sample"] = df["activity_type"].fillna("").str.contains(
            "Quality Control",
            case=False,
            regex=False
        )

    df["is_routine_sample"] = False
    if "activity_type" in df.columns:
        df["is_routine_sample"] = df["activity_type"].fillna("").str.contains(
            "Sample-Routine",
            case=False,
            regex=False
        )

    before_water_filter = len(df)

    if "media" in df.columns:
        df = df[df["media"].fillna("").str.lower() == "water"].copy()

    after_water_filter = len(df)

    before_required_filter = len(df)

    df = df[
        df["date"].notna()
        & df["station_id"].notna()
        & df["characteristic"].notna()
    ].copy()

    after_required_filter = len(df)

    stats = {
        "input_rows": before_water_filter,
        "after_water_filter": after_water_filter,
        "after_required_filter": after_required_filter,
        "numeric_result_value": int(df["result_value"].notna().sum()),
        "missing_result_value": int(df["result_value"].isna().sum()),
        "not_detected": int(df["is_not_detected"].sum()),
        "qc_sample": int(df["is_qc_sample"].sum()),
        "routine_sample": int(df["is_routine_sample"].sum()),
        "with_lat_lon": int((df["latitude"].notna() & df["longitude"].notna()).sum()),
    }

    return df, stats


# ============================================================
# Cleaning pipeline
# ============================================================

def clean_data():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    write_log("========== Step 1: Clean WQP Data ==========")
    write_log("Mode: chunked cleaning")
    write_log(f"Chunk size: {CHUNK_SIZE:,}")

    check_input_file()

    all_columns, existing_columns, missing_columns = get_existing_columns()

    write_log(f"Input file: {INPUT_CSV}")
    write_log(f"Original columns: {len(all_columns):,}")
    write_log(f"Columns kept: {len(existing_columns):,}")

    if missing_columns:
        write_log("[WARNING] Missing expected columns:")
        for col in missing_columns:
            write_log(f"  - {col}")

    total_input_rows = 0
    total_after_water_filter = 0
    total_after_required_filter = 0
    total_numeric_result_value = 0
    total_missing_result_value = 0
    total_not_detected = 0
    total_qc_sample = 0
    total_routine_sample = 0
    total_with_lat_lon = 0

    chunk_number = 0
    first_write = True

    reader = pd.read_csv(
        INPUT_CSV,
        usecols=existing_columns,
        chunksize=CHUNK_SIZE,
        low_memory=False,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    for chunk in reader:
        chunk_number += 1

        cleaned_chunk, stats = clean_chunk(chunk)

        total_input_rows += stats["input_rows"]
        total_after_water_filter += stats["after_water_filter"]
        total_after_required_filter += stats["after_required_filter"]
        total_numeric_result_value += stats["numeric_result_value"]
        total_missing_result_value += stats["missing_result_value"]
        total_not_detected += stats["not_detected"]
        total_qc_sample += stats["qc_sample"]
        total_routine_sample += stats["routine_sample"]
        total_with_lat_lon += stats["with_lat_lon"]

        cleaned_chunk.to_csv(
            OUTPUT_CSV,
            mode="w" if first_write else "a",
            index=False,
            header=first_write,
            encoding="utf-8"
        )

        first_write = False

        write_log(
            f"[CHUNK {chunk_number}] "
            f"input={stats['input_rows']:,}, "
            f"saved={len(cleaned_chunk):,}, "
            f"numeric={stats['numeric_result_value']:,}, "
            f"not_detected={stats['not_detected']:,}, "
            f"qc={stats['qc_sample']:,}"
        )

    write_log("")
    write_log("========== Cleaning Summary ==========")
    write_log(f"Original rows processed: {total_input_rows:,}")
    write_log(f"Rows after water filter: {total_after_water_filter:,}")
    write_log(f"Rows after required-field filter: {total_after_required_filter:,}")
    write_log(f"Final rows saved: {total_after_required_filter:,}")

    write_log("")
    write_log("========== Data Quality Summary ==========")
    write_log(f"Rows with numeric result_value: {total_numeric_result_value:,}")
    write_log(f"Rows with missing result_value: {total_missing_result_value:,}")
    write_log(f"Rows marked Not Detected: {total_not_detected:,}")
    write_log(f"Rows marked QC sample: {total_qc_sample:,}")
    write_log(f"Rows marked Routine sample: {total_routine_sample:,}")
    write_log(f"Rows with latitude/longitude: {total_with_lat_lon:,}")

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Clean data saved to: {OUTPUT_CSV}")
    write_log(f"Log saved to: {LOG_FILE}")

    write_log("")
    write_log("========== Step 1 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    clean_data()


if __name__ == "__main__":
    main()