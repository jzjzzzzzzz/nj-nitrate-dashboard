import os
import pandas as pd


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

INPUT_CSV = os.path.join(DATA_DIR, "processed", "clean_results.csv")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

OUTPUT_CSV = os.path.join(PROCESSED_DIR, "nitrate_results.csv")
LOG_FILE = os.path.join(LOG_DIR, "02_extract_nitrate_log.txt")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Settings
# ============================================================

CHUNK_SIZE = 100_000


# ============================================================
# Helper functions
# ============================================================

def write_log(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def check_input_file():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_CSV}\n\n"
            "Run Step 1 first:\n"
            "python scripts/01_clean_wqp_data.py"
        )


def classify_nitrate(characteristic):
    if pd.isna(characteristic):
        return None

    text = str(characteristic).lower().strip()

    if text == "nitrate":
        return "Nitrate"

    if "nitrate" in text and "nitrite" in text:
        return "Nitrate + Nitrite"

    if "nitrate" in text:
        return "Other Nitrate Related"

    return None


def clean_nitrate_chunk(df):
    df = df.copy()

    df["nitrate_category"] = df["characteristic"].apply(classify_nitrate)

    before_nitrate_filter = len(df)

    df = df[df["nitrate_category"].notna()].copy()

    after_nitrate_filter = len(df)

    before_routine_filter = len(df)

    df = df[
        (df["is_routine_sample"] == True)
        & (df["is_qc_sample"] == False)
    ].copy()

    after_routine_filter = len(df)

    before_numeric_filter = len(df)

    df = df[df["result_value"].notna()].copy()

    after_numeric_filter = len(df)

    before_location_filter = len(df)

    df = df[
        df["latitude"].notna()
        & df["longitude"].notna()
    ].copy()

    after_location_filter = len(df)

    # Remove impossible negative concentration values.
    before_negative_filter = len(df)

    df = df[df["result_value"] >= 0].copy()

    after_negative_filter = len(df)

    # Standardize useful columns
    keep_cols = [
        "organization_id",
        "organization_name",
        "provider",
        "activity_id",
        "activity_type",
        "media_subdivision",
        "date",
        "time",
        "timezone",
        "year",
        "month",
        "season",
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "characteristic",
        "nitrate_category",
        "sample_fraction",
        "result_value",
        "unit",
        "qualifier",
        "result_status",
        "value_type",
        "detection_condition",
        "is_not_detected",
        "is_qc_sample",
        "is_routine_sample",
        "usgs_pcode",
        "method_id",
        "method_name",
        "detection_limit_value",
        "detection_limit_unit",
        "last_updated",
    ]

    existing_cols = [col for col in keep_cols if col in df.columns]
    df = df[existing_cols].copy()

    stats = {
        "input_rows": before_nitrate_filter,
        "after_nitrate_filter": after_nitrate_filter,
        "after_routine_filter": after_routine_filter,
        "after_numeric_filter": after_numeric_filter,
        "after_location_filter": after_location_filter,
        "after_negative_filter": after_negative_filter,
        "removed_non_nitrate": before_nitrate_filter - after_nitrate_filter,
        "removed_non_routine_or_qc": before_routine_filter - after_routine_filter,
        "removed_missing_numeric": before_numeric_filter - after_numeric_filter,
        "removed_missing_location": before_location_filter - after_location_filter,
        "removed_negative": before_negative_filter - after_negative_filter,
    }

    return df, stats


# ============================================================
# Main extraction pipeline
# ============================================================

def extract_nitrate():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)

    write_log("========== Step 2: Extract Nitrate Data ==========")
    write_log("Mode: chunked extraction")
    write_log(f"Chunk size: {CHUNK_SIZE:,}")

    check_input_file()

    total_input_rows = 0
    total_nitrate_rows = 0
    total_routine_rows = 0
    total_numeric_rows = 0
    total_location_rows = 0
    total_final_rows = 0

    total_removed_non_nitrate = 0
    total_removed_non_routine_or_qc = 0
    total_removed_missing_numeric = 0
    total_removed_missing_location = 0
    total_removed_negative = 0

    chunk_number = 0
    first_write = True

    reader = pd.read_csv(
        INPUT_CSV,
        chunksize=CHUNK_SIZE,
        low_memory=False,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    for chunk in reader:
        chunk_number += 1

        nitrate_chunk, stats = clean_nitrate_chunk(chunk)

        total_input_rows += stats["input_rows"]
        total_nitrate_rows += stats["after_nitrate_filter"]
        total_routine_rows += stats["after_routine_filter"]
        total_numeric_rows += stats["after_numeric_filter"]
        total_location_rows += stats["after_location_filter"]
        total_final_rows += stats["after_negative_filter"]

        total_removed_non_nitrate += stats["removed_non_nitrate"]
        total_removed_non_routine_or_qc += stats["removed_non_routine_or_qc"]
        total_removed_missing_numeric += stats["removed_missing_numeric"]
        total_removed_missing_location += stats["removed_missing_location"]
        total_removed_negative += stats["removed_negative"]

        if len(nitrate_chunk) > 0:
            nitrate_chunk.to_csv(
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
            f"nitrate={stats['after_nitrate_filter']:,}, "
            f"routine={stats['after_routine_filter']:,}, "
            f"numeric={stats['after_numeric_filter']:,}, "
            f"with_location={stats['after_location_filter']:,}, "
            f"saved={len(nitrate_chunk):,}"
        )

    write_log("")
    write_log("========== Nitrate Extraction Summary ==========")
    write_log(f"Input clean rows processed: {total_input_rows:,}")
    write_log(f"Nitrate-related rows found: {total_nitrate_rows:,}")
    write_log(f"Rows after routine/QC filter: {total_routine_rows:,}")
    write_log(f"Rows after numeric-value filter: {total_numeric_rows:,}")
    write_log(f"Rows after location filter: {total_location_rows:,}")
    write_log(f"Final nitrate rows saved: {total_final_rows:,}")

    write_log("")
    write_log("========== Removed Rows Summary ==========")
    write_log(f"Removed non-nitrate rows: {total_removed_non_nitrate:,}")
    write_log(f"Removed non-routine or QC rows: {total_removed_non_routine_or_qc:,}")
    write_log(f"Removed missing numeric values: {total_removed_missing_numeric:,}")
    write_log(f"Removed missing location rows: {total_removed_missing_location:,}")
    write_log(f"Removed negative values: {total_removed_negative:,}")

    if os.path.exists(OUTPUT_CSV):
        nitrate_df_sample = pd.read_csv(OUTPUT_CSV, nrows=100_000, low_memory=False)

        write_log("")
        write_log("========== Sample Category Counts ==========")

        if "nitrate_category" in nitrate_df_sample.columns:
            counts = nitrate_df_sample["nitrate_category"].value_counts(dropna=False)
            for category, count in counts.items():
                write_log(f"{category}: {count:,}")

        write_log("")
        write_log("========== Sample Unit Counts ==========")

        if "unit" in nitrate_df_sample.columns:
            counts = nitrate_df_sample["unit"].value_counts(dropna=False).head(20)
            for unit, count in counts.items():
                write_log(f"{unit}: {count:,}")

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Nitrate data saved to: {OUTPUT_CSV}")
    write_log(f"Log saved to: {LOG_FILE}")

    write_log("")
    write_log("========== Step 2 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    extract_nitrate()


if __name__ == "__main__":
    main()