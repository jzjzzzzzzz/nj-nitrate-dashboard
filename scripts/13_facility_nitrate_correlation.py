import json
import warnings
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


# ============================================================
# Step 13: Facility Density vs Nitrate Correlation
# Purpose:
#   Quantify watershed-level associations between NJPDES facility
#   counts/densities and nitrate hotspot patterns.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / "data" / "processed" / "watershed_land_use_wastewater_nitrate_joined.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_FIGURES = BASE_DIR / "output" / "figures"
OUT_LOGS = BASE_DIR / "output" / "logs"

OUT_CORRELATION_CSV = OUT_PROCESSED / "facility_nitrate_correlation.csv"
OUT_RANKING_CSV = OUT_PROCESSED / "facility_nitrate_ranking.csv"

OUT_CORRELATION_JSON = OUT_DASHBOARD / "facility_nitrate_correlation.json"
OUT_RANKING_JSON = OUT_DASHBOARD / "facility_nitrate_ranking.json"

OUT_SCATTER_HOTSPOT = OUT_FIGURES / "facility_density_vs_hotspot_rate_scatter.png"
OUT_SCATTER_MEAN = OUT_FIGURES / "facility_density_vs_mean_nitrate_scatter.png"
OUT_SCATTER_INDUSTRIAL = OUT_FIGURES / "industrial_stormwater_density_vs_hotspot_rate_scatter.png"
OUT_SCATTER_SEPTIC = OUT_FIGURES / "septic_groundwater_density_vs_mean_nitrate_scatter.png"

LOG_PATH = OUT_LOGS / "13_facility_nitrate_correlation_log.txt"


def log(message):
    print(message)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def ensure_dirs():
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)
    OUT_LOGS.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        LOG_PATH.unlink()


def export_json(df, path):
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def check_required_columns(df):
    required = [
        "watershed_name",
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
        "facility_count",
        "facility_density_per_100_km2",
        "industrial_stormwater_facility_count",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_facility_count",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_facility_count",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_facility_count",
        "stormwater_or_surface_density_per_100_km2",
    ]

    missing = []

    for col in required:
        if col not in df.columns:
            missing.append(col)

    if missing:
        raise ValueError(
            "Missing required columns in watershed_land_use_wastewater_nitrate_joined.csv:\n"
            + "\n".join(missing)
            + "\n\nPlease rerun Step 12 first."
        )


def clean_numeric_pair(df, x_col, y_col):
    sub = df[[x_col, y_col, "watershed_name"]].copy()

    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")

    sub = sub.dropna(subset=[x_col, y_col]).copy()

    return sub


def pearson_corr(x, y):
    if len(x) < 2:
        return None

    if x.nunique() <= 1 or y.nunique() <= 1:
        return None

    return x.corr(y, method="pearson")


def spearman_corr(x, y):
    if len(x) < 2:
        return None

    if x.nunique() <= 1 or y.nunique() <= 1:
        return None

    x_rank = x.rank(method="average")
    y_rank = y.rank(method="average")

    return x_rank.corr(y_rank, method="pearson")


def direction_from_r(r):
    if r is None or pd.isna(r):
        return "not available"

    if r > 0:
        return "positive"

    if r < 0:
        return "negative"

    return "no direction"


def strength_from_r(r):
    if r is None or pd.isna(r):
        return "not available"

    abs_r = abs(r)

    if abs_r >= 0.7:
        return "strong"

    if abs_r >= 0.4:
        return "moderate"

    if abs_r >= 0.2:
        return "weak"

    return "very weak"


def make_correlation_table(df, facility_metrics, nitrate_metrics):
    rows = []

    for x_col in facility_metrics:
        for y_col in nitrate_metrics:
            sub = clean_numeric_pair(df, x_col, y_col)

            r_pearson = pearson_corr(sub[x_col], sub[y_col])
            r_spearman = spearman_corr(sub[x_col], sub[y_col])

            if r_pearson is not None:
                r_pearson = round(float(r_pearson), 4)

            if r_spearman is not None:
                r_spearman = round(float(r_spearman), 4)

            rows.append({
                "facility_metric": x_col,
                "nitrate_metric": y_col,
                "n": len(sub),
                "pearson_r": r_pearson,
                "spearman_r": r_spearman,
                "pearson_direction": direction_from_r(r_pearson),
                "pearson_strength": strength_from_r(r_pearson),
                "spearman_direction": direction_from_r(r_spearman),
                "spearman_strength": strength_from_r(r_spearman),
            })

    result = pd.DataFrame(rows)

    result["abs_pearson_r"] = result["pearson_r"].abs()
    result["abs_spearman_r"] = result["spearman_r"].abs()

    result = result.sort_values(
        ["nitrate_metric", "abs_pearson_r"],
        ascending=[True, False]
    ).reset_index(drop=True)

    return result


def make_ranking_table(df):
    ranking_cols = [
        "watershed_name",
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
        "developed_percent",
        "agriculture_percent",
        "facility_count",
        "facility_density_per_100_km2",
        "industrial_stormwater_facility_count",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_facility_count",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_facility_count",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_facility_count",
        "stormwater_or_surface_density_per_100_km2",
    ]

    existing_cols = [col for col in ranking_cols if col in df.columns]

    ranking = df[existing_cols].copy()

    numeric_cols = [col for col in ranking.columns if col != "watershed_name"]

    for col in numeric_cols:
        ranking[col] = pd.to_numeric(ranking[col], errors="coerce")

    ranking["hotspot_rank"] = ranking["hotspot_rate_percent"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["mean_nitrate_rank"] = ranking["mean_nitrate_mg_L"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["facility_density_rank"] = ranking["facility_density_per_100_km2"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["industrial_stormwater_density_rank"] = ranking[
        "industrial_stormwater_density_per_100_km2"
    ].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking = ranking.sort_values(
        ["hotspot_rank", "mean_nitrate_rank"],
        ascending=[True, True]
    ).reset_index(drop=True)

    return ranking


def scatter_plot(df, x_col, y_col, label_col, output_path, title, x_label, y_label):
    sub = clean_numeric_pair(df, x_col, y_col)

    plt.figure(figsize=(10, 7))
    plt.scatter(sub[x_col], sub[y_col])

    for _, row in sub.iterrows():
        name = str(row[label_col])

        if (
            row[y_col] >= sub[y_col].quantile(0.8)
            or row[x_col] >= sub[x_col].quantile(0.8)
        ):
            plt.annotate(
                name,
                (row[x_col], row[y_col]),
                fontsize=8,
                xytext=(5, 5),
                textcoords="offset points"
            )

    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def log_top_correlations(correlation_df, nitrate_metric):
    sub = correlation_df[correlation_df["nitrate_metric"] == nitrate_metric].copy()

    sub = sub.sort_values("abs_pearson_r", ascending=False).head(10)

    log("")
    log(f"========== Top Correlations for {nitrate_metric} ==========")

    for _, row in sub.iterrows():
        log(
            f"{row['facility_metric']} vs {row['nitrate_metric']} | "
            f"Pearson r={row['pearson_r']} "
            f"({row['pearson_direction']}, {row['pearson_strength']}) | "
            f"Spearman r={row['spearman_r']} "
            f"({row['spearman_direction']}, {row['spearman_strength']}) | "
            f"n={row['n']}"
        )


def log_top_rankings(ranking_df):
    log("")
    log("========== Top 10 Watersheds by Hotspot Rate ==========")

    top_hotspot = ranking_df.sort_values("hotspot_rate_percent", ascending=False).head(10)

    for _, row in top_hotspot.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"hotspot_rate={row.get('hotspot_rate_percent')} | "
            f"mean_nitrate={row.get('mean_nitrate_mg_L')} | "
            f"facility_density={row.get('facility_density_per_100_km2')} | "
            f"industrial_stormwater_density={row.get('industrial_stormwater_density_per_100_km2')} | "
            f"developed={row.get('developed_percent')}%"
        )

    log("")
    log("========== Top 10 Watersheds by Facility Density ==========")

    top_facility = ranking_df.sort_values(
        "facility_density_per_100_km2",
        ascending=False
    ).head(10)

    for _, row in top_facility.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"facility_density={row.get('facility_density_per_100_km2')} | "
            f"facility_count={row.get('facility_count')} | "
            f"hotspot_rate={row.get('hotspot_rate_percent')} | "
            f"mean_nitrate={row.get('mean_nitrate_mg_L')} | "
            f"developed={row.get('developed_percent')}%"
        )

    log("")
    log("========== Top 10 Watersheds by Industrial Stormwater Density ==========")

    top_industrial = ranking_df.sort_values(
        "industrial_stormwater_density_per_100_km2",
        ascending=False
    ).head(10)

    for _, row in top_industrial.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"industrial_stormwater_density={row.get('industrial_stormwater_density_per_100_km2')} | "
            f"industrial_stormwater_count={row.get('industrial_stormwater_facility_count')} | "
            f"hotspot_rate={row.get('hotspot_rate_percent')} | "
            f"mean_nitrate={row.get('mean_nitrate_mg_L')} | "
            f"developed={row.get('developed_percent')}%"
        )


def main():
    ensure_dirs()

    log("========== Step 13: Facility Density vs Nitrate Correlation ==========")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing input file:\n{INPUT_PATH}\n\n"
            "Please run Step 12 first."
        )

    log(f"[READ] {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    log(f"Rows loaded: {len(df):,}")
    log(f"Columns loaded: {len(df.columns):,}")

    log("")
    log("========== Columns ==========")
    for col in df.columns:
        log(col)

    check_required_columns(df)

    facility_metrics = [
        "facility_count",
        "facility_density_per_100_km2",
        "industrial_stormwater_facility_count",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_facility_count",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_facility_count",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_facility_count",
        "stormwater_or_surface_density_per_100_km2",
        "residuals_or_recycling_facility_count",
        "residuals_or_recycling_density_per_100_km2",
        "construction_or_permit_facility_count",
        "construction_or_permit_density_per_100_km2",
        "mining_quarrying_facility_count",
        "mining_quarrying_density_per_100_km2",
    ]

    facility_metrics = [col for col in facility_metrics if col in df.columns]

    nitrate_metrics = [
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
    ]

    log("")
    log("========== Facility Metrics ==========")
    for col in facility_metrics:
        log(col)

    log("")
    log("========== Nitrate Metrics ==========")
    for col in nitrate_metrics:
        log(col)

    correlation_df = make_correlation_table(df, facility_metrics, nitrate_metrics)
    ranking_df = make_ranking_table(df)

    correlation_df.to_csv(OUT_CORRELATION_CSV, index=False)
    ranking_df.to_csv(OUT_RANKING_CSV, index=False)

    export_json(correlation_df, OUT_CORRELATION_JSON)
    export_json(ranking_df, OUT_RANKING_JSON)

    scatter_plot(
        df=df,
        x_col="facility_density_per_100_km2",
        y_col="hotspot_rate_percent",
        label_col="watershed_name",
        output_path=OUT_SCATTER_HOTSPOT,
        title="Facility Density vs Nitrate Hotspot Rate",
        x_label="NJPDES Facility Density per 100 km²",
        y_label="Nitrate Hotspot Rate (%)"
    )

    scatter_plot(
        df=df,
        x_col="facility_density_per_100_km2",
        y_col="mean_nitrate_mg_L",
        label_col="watershed_name",
        output_path=OUT_SCATTER_MEAN,
        title="Facility Density vs Mean Nitrate",
        x_label="NJPDES Facility Density per 100 km²",
        y_label="Mean Nitrate (mg/L)"
    )

    scatter_plot(
        df=df,
        x_col="industrial_stormwater_density_per_100_km2",
        y_col="hotspot_rate_percent",
        label_col="watershed_name",
        output_path=OUT_SCATTER_INDUSTRIAL,
        title="Industrial Stormwater Density vs Nitrate Hotspot Rate",
        x_label="Industrial Stormwater Facility Density per 100 km²",
        y_label="Nitrate Hotspot Rate (%)"
    )

    scatter_plot(
        df=df,
        x_col="septic_groundwater_density_per_100_km2",
        y_col="mean_nitrate_mg_L",
        label_col="watershed_name",
        output_path=OUT_SCATTER_SEPTIC,
        title="Septic / Groundwater Facility Density vs Mean Nitrate",
        x_label="Septic / Groundwater Facility Density per 100 km²",
        y_label="Mean Nitrate (mg/L)"
    )

    log_top_correlations(correlation_df, "hotspot_rate_percent")
    log_top_correlations(correlation_df, "mean_nitrate_mg_L")
    log_top_correlations(correlation_df, "mean_p90_nitrate_mg_L")
    log_top_correlations(correlation_df, "max_station_nitrate_mg_L")

    log_top_rankings(ranking_df)

    strongest_hotspot = (
        correlation_df[correlation_df["nitrate_metric"] == "hotspot_rate_percent"]
        .sort_values("abs_pearson_r", ascending=False)
        .head(1)
    )

    strongest_mean = (
        correlation_df[correlation_df["nitrate_metric"] == "mean_nitrate_mg_L"]
        .sort_values("abs_pearson_r", ascending=False)
        .head(1)
    )

    log("")
    log("========== Main Interpretation ==========")

    if not strongest_hotspot.empty:
        row = strongest_hotspot.iloc[0]
        log(
            f"Strongest facility association with hotspot_rate_percent: "
            f"{row['facility_metric']} | "
            f"Pearson r={row['pearson_r']} | "
            f"Spearman r={row['spearman_r']} | "
            f"{row['pearson_direction']}, {row['pearson_strength']}"
        )

    if not strongest_mean.empty:
        row = strongest_mean.iloc[0]
        log(
            f"Strongest facility association with mean_nitrate_mg_L: "
            f"{row['facility_metric']} | "
            f"Pearson r={row['pearson_r']} | "
            f"Spearman r={row['spearman_r']} | "
            f"{row['pearson_direction']}, {row['pearson_strength']}"
        )

    log("")
    log("Scientific caution:")
    log(
        "These correlations are watershed-level associations. They do not prove that "
        "NJPDES facilities caused nitrate hotspots. Facility type, discharge volume, "
        "monitoring location, streamflow direction, land use, groundwater movement, "
        "rainfall, and sampling bias should be considered in later analysis."
    )

    log("")
    log("========== Export Complete ==========")
    log(f"[EXPORT] {OUT_CORRELATION_CSV}")
    log(f"[EXPORT] {OUT_RANKING_CSV}")
    log(f"[EXPORT] {OUT_CORRELATION_JSON}")
    log(f"[EXPORT] {OUT_RANKING_JSON}")
    log(f"[EXPORT] {OUT_SCATTER_HOTSPOT}")
    log(f"[EXPORT] {OUT_SCATTER_MEAN}")
    log(f"[EXPORT] {OUT_SCATTER_INDUSTRIAL}")
    log(f"[EXPORT] {OUT_SCATTER_SEPTIC}")

    log("")
    log("Step 13 finished successfully.")


if __name__ == "__main__":
    main()