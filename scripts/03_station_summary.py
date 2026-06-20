import os
import pandas as pd
import numpy as np


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

INPUT_CSV = os.path.join(DATA_DIR, "processed", "nitrate_results.csv")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

STANDARDIZED_CSV = os.path.join(PROCESSED_DIR, "nitrate_standardized.csv")
STATION_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "station_summary.csv")
LOG_FILE = os.path.join(LOG_DIR, "03_station_summary_log.txt")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


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
            "Run Step 2 first:\n"
            "python scripts/02_extract_nitrate.py"
        )


def standardize_unit(row):
    value = row["result_value"]
    unit = str(row["unit"]).strip().lower()

    if pd.isna(value):
        return np.nan

    # mg/L and related forms
    if unit in ["mg/l", "mg/l as n", "mg n/l******", "ppm"]:
        return value

    # WQP sometimes uses mg/L with uppercase L
    if unit.replace(" ", "") in ["mg/l", "mg/lasn"]:
        return value

    # ug/L -> mg/L
    if unit in ["ug/l", "µg/l"]:
        return value / 1000.0

    # Unknown unit
    return np.nan


def confidence_level(n):
    if n >= 100:
        return "High"
    if n >= 30:
        return "Medium"
    return "Low"


def confidence_score(n):
    # Smooth score from 0 to 1.
    # 100 observations is treated as approximately full confidence.
    return min(1.0, np.log10(n + 1) / np.log10(101))


# ============================================================
# Main pipeline
# ============================================================

def create_station_summary():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 3: Station Summary ==========")

    check_input_file()

    write_log(f"[READ] {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV, low_memory=False)

    write_log(f"Input nitrate rows: {len(df):,}")

    # Convert date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Standardize nitrate value to mg/L
    df["nitrate_mg_L"] = df.apply(standardize_unit, axis=1)

    before_standard_filter = len(df)
    df = df[df["nitrate_mg_L"].notna()].copy()
    after_standard_filter = len(df)

    # Remove impossible or extreme values.
    # Keep this loose for now; later we can do outlier review separately.
    before_value_filter = len(df)
    df = df[df["nitrate_mg_L"] >= 0].copy()
    after_value_filter = len(df)

    # Save standardized nitrate data
    df.to_csv(STANDARDIZED_CSV, index=False, encoding="utf-8")

    write_log("")
    write_log("========== Unit Standardization ==========")
    write_log(f"Rows before unit standardization filter: {before_standard_filter:,}")
    write_log(f"Rows after unit standardization filter: {after_standard_filter:,}")
    write_log(f"Rows after non-negative filter: {after_value_filter:,}")
    write_log(f"Standardized nitrate data saved to: {STANDARDIZED_CSV}")

    write_log("")
    write_log("========== Unit Counts Before Standardization ==========")
    unit_counts = df["unit"].value_counts(dropna=False)
    for unit, count in unit_counts.items():
        write_log(f"{unit}: {count:,}")

    # Make station-level summary
    group_cols = ["station_id"]

    summary = df.groupby(group_cols).agg(
        station_name=("station_name", "first"),
        latitude=("latitude", "median"),
        longitude=("longitude", "median"),
        observation_count=("nitrate_mg_L", "count"),
        mean_nitrate_mg_L=("nitrate_mg_L", "mean"),
        median_nitrate_mg_L=("nitrate_mg_L", "median"),
        max_nitrate_mg_L=("nitrate_mg_L", "max"),
        p90_nitrate_mg_L=("nitrate_mg_L", lambda x: x.quantile(0.90)),
        min_nitrate_mg_L=("nitrate_mg_L", "min"),
        first_date=("date", "min"),
        last_date=("date", "max"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        provider=("provider", lambda x: ", ".join(sorted(set(x.dropna().astype(str))))),
        nitrate_categories=("nitrate_category", lambda x: ", ".join(sorted(set(x.dropna().astype(str))))),
        units_seen=("unit", lambda x: ", ".join(sorted(set(x.dropna().astype(str))))),
    ).reset_index()

    summary["confidence_level"] = summary["observation_count"].apply(confidence_level)
    summary["confidence_score"] = summary["observation_count"].apply(confidence_score)

    # Simple hotspot ranking based on p90
    p90_threshold = summary["p90_nitrate_mg_L"].quantile(0.90)
    mean_threshold = summary["mean_nitrate_mg_L"].quantile(0.90)

    summary["is_p90_hotspot"] = summary["p90_nitrate_mg_L"] >= p90_threshold
    summary["is_mean_hotspot"] = summary["mean_nitrate_mg_L"] >= mean_threshold
    summary["is_hotspot"] = summary["is_p90_hotspot"] | summary["is_mean_hotspot"]

    summary = summary.sort_values(
        by=["is_hotspot", "p90_nitrate_mg_L", "mean_nitrate_mg_L", "observation_count"],
        ascending=[False, False, False, False]
    )

    summary.to_csv(STATION_SUMMARY_CSV, index=False, encoding="utf-8")

    write_log("")
    write_log("========== Station Summary ==========")
    write_log(f"Stations summarized: {len(summary):,}")
    write_log(f"High confidence stations: {(summary['confidence_level'] == 'High').sum():,}")
    write_log(f"Medium confidence stations: {(summary['confidence_level'] == 'Medium').sum():,}")
    write_log(f"Low confidence stations: {(summary['confidence_level'] == 'Low').sum():,}")
    write_log(f"P90 hotspot threshold: {p90_threshold:.4f} mg/L")
    write_log(f"Mean hotspot threshold: {mean_threshold:.4f} mg/L")
    write_log(f"Hotspot stations: {summary['is_hotspot'].sum():,}")

    write_log("")
    write_log("========== Top 20 Hotspot Stations ==========")
    top20 = summary.head(20)

    for _, row in top20.iterrows():
        write_log(
            f"{row['station_id']} | "
            f"count={row['observation_count']} | "
            f"mean={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"p90={row['p90_nitrate_mg_L']:.4f} mg/L | "
            f"max={row['max_nitrate_mg_L']:.4f} mg/L | "
            f"confidence={row['confidence_level']}"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Standardized nitrate data saved to: {STANDARDIZED_CSV}")
    write_log(f"Station summary saved to: {STATION_SUMMARY_CSV}")
    write_log(f"Log saved to: {LOG_FILE}")

    write_log("")
    write_log("========== Step 3 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    create_station_summary()


if __name__ == "__main__":
    main()