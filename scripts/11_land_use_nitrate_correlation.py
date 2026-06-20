import json
import warnings
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


# ============================================================
# Step 11: Land Use vs Nitrate Correlation
# Purpose:
#   Quantify watershed-level associations between land use
#   composition and nitrate hotspot patterns.
#
# Important:
#   This version does NOT require scipy.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / "data" / "processed" / "watershed_land_use_nitrate_joined.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_LOGS = BASE_DIR / "output" / "logs"
OUT_FIGURES = BASE_DIR / "output" / "figures"

OUT_CORRELATION_CSV = OUT_PROCESSED / "land_use_nitrate_correlation.csv"
OUT_RANKING_CSV = OUT_PROCESSED / "land_use_nitrate_ranking.csv"

OUT_CORRELATION_JSON = OUT_DASHBOARD / "land_use_nitrate_correlation.json"
OUT_RANKING_JSON = OUT_DASHBOARD / "land_use_nitrate_ranking.json"

OUT_SCATTER_HOTSPOT = OUT_FIGURES / "land_use_vs_hotspot_rate_scatter.png"
OUT_SCATTER_MEAN = OUT_FIGURES / "land_use_vs_mean_nitrate_scatter.png"

LOG_PATH = OUT_LOGS / "11_land_use_nitrate_correlation_log.txt"


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def ensure_dirs():
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.mkdir(parents=True, exist_ok=True)
    OUT_LOGS.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        LOG_PATH.unlink()


def export_json(df, path):
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def check_required_columns(df):
    required = [
        "watershed_name",
        "mean_nitrate_mg_L",
        "hotspot_rate_percent",
        "station_count",
        "total_observations",
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
        "water_percent",
        "barren_percent",
    ]

    missing = []

    for col in required:
        if col not in df.columns:
            missing.append(col)

    if missing:
        raise ValueError(
            "Missing required columns in watershed_land_use_nitrate_joined.csv:\n"
            + "\n".join(missing)
            + "\n\nPlease rerun Step 10 first."
        )


def clean_numeric_pair(df, x_col, y_col):
    sub = df[[x_col, y_col, "watershed_name"]].copy()

    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")

    sub = sub.dropna(subset=[x_col, y_col]).copy()

    return sub


def pearson_corr(x, y):
    if len(x) < 3:
        return None

    if x.nunique() <= 1 or y.nunique() <= 1:
        return None

    return x.corr(y, method="pearson")


def spearman_corr_no_scipy(x, y):
    """
    Spearman correlation = Pearson correlation of ranks.
    This avoids scipy completely.
    """

    if len(x) < 3:
        return None

    if x.nunique() <= 1 or y.nunique() <= 1:
        return None

    x_rank = x.rank(method="average")
    y_rank = y.rank(method="average")

    return x_rank.corr(y_rank, method="pearson")


def correlation_direction(r):
    if r is None or pd.isna(r):
        return "unknown"

    if r > 0:
        return "positive"

    if r < 0:
        return "negative"

    return "none"


def correlation_strength(r):
    if r is None or pd.isna(r):
        return "unknown"

    abs_r = abs(r)

    if abs_r >= 0.7:
        return "strong"

    if abs_r >= 0.4:
        return "moderate"

    if abs_r >= 0.2:
        return "weak"

    return "very weak"


def make_interpretation(x_col, y_col, pearson_r):
    x_label = x_col.replace("_percent", "").replace("_", " ")
    y_label = (
        y_col
        .replace("_mg_L", "")
        .replace("_percent", "")
        .replace("_", " ")
    )

    direction = correlation_direction(pearson_r)
    strength = correlation_strength(pearson_r)

    if direction == "positive":
        text = (
            f"{x_label} has a {strength} positive association with {y_label}. "
            "Watersheds with higher values of this land use type tend to have higher nitrate values in this metric."
        )
    elif direction == "negative":
        text = (
            f"{x_label} has a {strength} negative association with {y_label}. "
            "Watersheds with higher values of this land use type tend to have lower nitrate values in this metric."
        )
    elif direction == "none":
        text = (
            f"{x_label} shows almost no linear association with {y_label}."
        )
    else:
        text = (
            f"The association between {x_label} and {y_label} could not be evaluated."
        )

    text += " This is an association only, not proof of causation."

    return text


def compute_correlations(df, land_use_cols, nitrate_cols):
    rows = []

    for x_col in land_use_cols:
        for y_col in nitrate_cols:
            sub = clean_numeric_pair(df, x_col, y_col)

            n = len(sub)

            if n < 3:
                pearson_r = None
                spearman_r = None
            else:
                pearson_r = pearson_corr(sub[x_col], sub[y_col])
                spearman_r = spearman_corr_no_scipy(sub[x_col], sub[y_col])

            rows.append({
                "land_use_variable": x_col,
                "nitrate_metric": y_col,
                "n_watersheds": n,
                "pearson_r": pearson_r,
                "spearman_r": spearman_r,
                "pearson_abs_r": abs(pearson_r) if pearson_r is not None and pd.notna(pearson_r) else None,
                "direction": correlation_direction(pearson_r),
                "strength": correlation_strength(pearson_r),
                "interpretation": make_interpretation(x_col, y_col, pearson_r),
            })

    result = pd.DataFrame(rows)

    for col in ["pearson_r", "spearman_r", "pearson_abs_r"]:
        result[col] = pd.to_numeric(result[col], errors="coerce").round(4)

    result = result.sort_values(
        by=["nitrate_metric", "pearson_abs_r"],
        ascending=[True, False]
    ).reset_index(drop=True)

    return result


def make_ranking_table(df):
    ranking_cols = [
        "watershed_name",
        "station_count",
        "total_observations",
        "mean_nitrate_mg_L",
        "median_station_mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
        "hotspot_rate_percent",
        "high_confidence_rate_percent",
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
        "water_percent",
        "barren_percent",
    ]

    available_cols = [col for col in ranking_cols if col in df.columns]

    ranking = df[available_cols].copy()

    numeric_cols = [
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
        "hotspot_rate_percent",
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
    ]

    for col in numeric_cols:
        if col in ranking.columns:
            ranking[col] = pd.to_numeric(ranking[col], errors="coerce")

    ranking["hotspot_rank"] = ranking["hotspot_rate_percent"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["mean_nitrate_rank"] = ranking["mean_nitrate_mg_L"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["developed_rank"] = ranking["developed_percent"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking["agriculture_rank"] = ranking["agriculture_percent"].rank(
        ascending=False,
        method="min"
    ).astype(int)

    ranking = ranking.sort_values(
        by=["hotspot_rank", "mean_nitrate_rank"],
        ascending=[True, True]
    ).reset_index(drop=True)

    for col in ranking.columns:
        if col.endswith("_percent") or col.endswith("_mg_L"):
            ranking[col] = pd.to_numeric(ranking[col], errors="coerce").round(4)

    return ranking


def add_best_fit_line(ax, x, y):
    clean = pd.DataFrame({"x": x, "y": y}).dropna()

    if len(clean) < 2:
        return

    if clean["x"].nunique() <= 1:
        return

    slope = clean["x"].cov(clean["y"]) / clean["x"].var()

    if pd.isna(slope):
        return

    intercept = clean["y"].mean() - slope * clean["x"].mean()

    x_min = clean["x"].min()
    x_max = clean["x"].max()

    y_min = slope * x_min + intercept
    y_max = slope * x_max + intercept

    ax.plot([x_min, x_max], [y_min, y_max], linestyle="--")


def make_scatter_plot(df, y_col, output_path, title, y_label):
    land_use_cols = [
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    for i, x_col in enumerate(land_use_cols):
        ax = axes[i]

        plot_df = clean_numeric_pair(df, x_col, y_col)

        ax.scatter(plot_df[x_col], plot_df[y_col])

        add_best_fit_line(ax, plot_df[x_col], plot_df[y_col])

        r = pearson_corr(plot_df[x_col], plot_df[y_col])

        x_label = x_col.replace("_percent", "").capitalize() + " land (%)"

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        if r is None or pd.isna(r):
            ax.set_title(f"{x_label} vs {y_label}\nr = NA")
        else:
            ax.set_title(f"{x_label} vs {y_label}\nr = {r:.3f}")

        for _, row in plot_df.iterrows():
            should_label = False

            if row[y_col] == plot_df[y_col].max():
                should_label = True

            if row[x_col] == plot_df[x_col].max():
                should_label = True

            if should_label:
                ax.annotate(
                    row["watershed_name"],
                    (row[x_col], row[y_col]),
                    fontsize=7,
                    xytext=(4, 4),
                    textcoords="offset points"
                )

    fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def write_summary_notes(correlation_df, ranking_df):
    log("")
    log("========== Summary Interpretation ==========")

    for metric in ["hotspot_rate_percent", "mean_nitrate_mg_L"]:
        metric_df = correlation_df[correlation_df["nitrate_metric"] == metric].copy()
        metric_df = metric_df.sort_values("pearson_abs_r", ascending=False)

        if len(metric_df) == 0:
            continue

        top = metric_df.iloc[0]

        log("")
        log(f"Strongest land-use association for {metric}:")
        log(
            f"{top['land_use_variable']} | "
            f"Pearson r={top['pearson_r']} | "
            f"Spearman r={top['spearman_r']} | "
            f"direction={top['direction']} | "
            f"strength={top['strength']}"
        )
        log(top["interpretation"])

    log("")
    log("========== Important Watersheds ==========")

    important = ranking_df.sort_values("hotspot_rank").head(5)

    for _, row in important.iterrows():
        log(
            f"{row['watershed_name']} | "
            f"hotspot_rank={row['hotspot_rank']} | "
            f"hotspot_rate={row['hotspot_rate_percent']} | "
            f"mean_nitrate={row['mean_nitrate_mg_L']} | "
            f"developed={row['developed_percent']}% | "
            f"agriculture={row['agriculture_percent']}% | "
            f"forest={row['forest_percent']}% | "
            f"wetlands={row['wetlands_percent']}%"
        )

    log("")
    log("Important caution:")
    log(
        "This watershed-level analysis shows associations between land use and nitrate metrics. "
        "It does not prove that a land use category directly caused nitrate hotspots. "
        "Further analysis with wastewater facilities, rainfall, groundwater, soil, and time-specific data is needed."
    )


def main():
    ensure_dirs()

    log("========== Step 11: Land Use vs Nitrate Correlation ==========")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing input file:\n{INPUT_PATH}\n\n"
            "Please run Step 10 first."
        )

    log(f"[READ] {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    log(f"Rows loaded: {len(df):,}")
    log(f"Columns loaded: {len(df.columns):,}")

    check_required_columns(df)

    land_use_cols = [
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
        "water_percent",
        "barren_percent",
    ]

    nitrate_cols = [
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
    ]

    nitrate_cols = [col for col in nitrate_cols if col in df.columns]

    log("")
    log("========== Variables Used ==========")
    log(f"Land use variables: {land_use_cols}")
    log(f"Nitrate metrics: {nitrate_cols}")

    correlation_df = compute_correlations(df, land_use_cols, nitrate_cols)
    ranking_df = make_ranking_table(df)

    correlation_df.to_csv(OUT_CORRELATION_CSV, index=False)
    ranking_df.to_csv(OUT_RANKING_CSV, index=False)

    export_json(correlation_df, OUT_CORRELATION_JSON)
    export_json(ranking_df, OUT_RANKING_JSON)

    make_scatter_plot(
        df=df,
        y_col="hotspot_rate_percent",
        output_path=OUT_SCATTER_HOTSPOT,
        title="Land Use vs Nitrate Hotspot Rate by Watershed",
        y_label="Hotspot rate (%)"
    )

    make_scatter_plot(
        df=df,
        y_col="mean_nitrate_mg_L",
        output_path=OUT_SCATTER_MEAN,
        title="Land Use vs Mean Nitrate by Watershed",
        y_label="Mean nitrate (mg/L)"
    )

    log("")
    log("========== Correlation Results ==========")

    for _, row in correlation_df.iterrows():
        log(
            f"{row['land_use_variable']} vs {row['nitrate_metric']} | "
            f"n={row['n_watersheds']} | "
            f"Pearson r={row['pearson_r']} | "
            f"Spearman r={row['spearman_r']} | "
            f"{row['direction']} | {row['strength']}"
        )

    write_summary_notes(correlation_df, ranking_df)

    log("")
    log("========== Export Complete ==========")
    log(f"[EXPORT] {OUT_CORRELATION_CSV}")
    log(f"[EXPORT] {OUT_RANKING_CSV}")
    log(f"[EXPORT] {OUT_CORRELATION_JSON}")
    log(f"[EXPORT] {OUT_RANKING_JSON}")
    log(f"[EXPORT] {OUT_SCATTER_HOTSPOT}")
    log(f"[EXPORT] {OUT_SCATTER_MEAN}")

    log("")
    log("Step 11 finished successfully.")


if __name__ == "__main__":
    main()