import json
import math
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

STATION_SUMMARY = BASE_DIR / "data" / "processed" / "station_summary.csv"
STATION_WATERSHED = BASE_DIR / "data" / "processed" / "station_watershed_summary.csv"
NITRATE_STANDARDIZED = BASE_DIR / "data" / "processed" / "nitrate_standardized.csv"
WATERSHED_JOINED = BASE_DIR / "data" / "processed" / "watershed_land_use_wastewater_nitrate_joined.csv"

RAINFALL_DIR = BASE_DIR / "data" / "external" / "rainfall"
RAINFALL_CSV = RAINFALL_DIR / "nj_annual_precip_noaa.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_FIGURES = BASE_DIR / "output" / "figures"
OUT_LOGS = BASE_DIR / "output" / "logs"
LOG_PATH = OUT_LOGS / "18_robustness_reliability_model_log.txt"

OUT_THRESHOLD_CSV = OUT_PROCESSED / "hotspot_threshold_robustness.csv"
OUT_THRESHOLD_WATERSHED_CSV = OUT_PROCESSED / "hotspot_threshold_watershed_summary.csv"
OUT_RELIABILITY_CSV = OUT_PROCESSED / "confidence_weighted_watershed_summary.csv"
OUT_MODEL_CSV = OUT_PROCESSED / "simplified_model_vif_comparison.csv"
OUT_RAINFALL_CSV = OUT_PROCESSED / "rainfall_nitrate_yearly_correlation.csv"

OUT_THRESHOLD_JSON = OUT_DASHBOARD / "hotspot_threshold_robustness.json"
OUT_THRESHOLD_WATERSHED_JSON = OUT_DASHBOARD / "hotspot_threshold_watershed_summary.json"
OUT_RELIABILITY_JSON = OUT_DASHBOARD / "confidence_weighted_watershed_summary.json"
OUT_MODEL_JSON = OUT_DASHBOARD / "simplified_model_vif_comparison.json"
OUT_RAINFALL_JSON = OUT_DASHBOARD / "rainfall_nitrate_yearly_correlation.json"

FIG_THRESHOLD = OUT_FIGURES / "hotspot_threshold_robustness.png"
FIG_RELIABILITY = OUT_FIGURES / "confidence_weighted_hotspot_comparison.png"
FIG_MODEL = OUT_FIGURES / "simplified_model_r2_vif_comparison.png"
FIG_RAINFALL = OUT_FIGURES / "rainfall_vs_yearly_nitrate.png"


def ensure_dirs():
    for path in [OUT_PROCESSED, OUT_DASHBOARD, OUT_FIGURES, OUT_LOGS, RAINFALL_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def export_json(df, path):
    clean = df.replace([np.inf, -np.inf], np.nan)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean.where(pd.notna(clean), None).to_dict(orient="records"), f, indent=2)


def pearson(x, y):
    temp = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(temp) < 3 or temp["x"].std(ddof=0) == 0 or temp["y"].std(ddof=0) == 0:
        return None
    return float(temp["x"].corr(temp["y"], method="pearson"))


def spearman(x, y):
    temp = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(temp) < 3:
        return None
    return pearson(temp["x"].rank(method="average"), temp["y"].rank(method="average"))


def ols_fit(X, y):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = X.shape[0]
    p = X.shape[1]
    beta = np.linalg.pinv(X.T @ X) @ X.T @ y
    pred = X @ beta
    resid = y - pred
    sse = float(np.sum(resid ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    r2 = np.nan if sst == 0 else 1 - sse / sst
    adj = np.nan if n <= p else 1 - ((1 - r2) * (n - 1) / (n - p))
    rmse = math.sqrt(sse / n) if n else np.nan
    return {"beta": beta, "pred": pred, "r2": r2, "adjusted_r2": adj, "rmse": rmse, "n": n, "p": p}


def calculate_vif(df, predictors):
    rows = []
    usable = df[predictors].dropna()
    for target in predictors:
        others = [c for c in predictors if c != target]
        if not others:
            rows.append({"predictor": target, "vif": 1.0})
            continue
        temp = usable[[target] + others].dropna()
        if len(temp) < len(others) + 3:
            rows.append({"predictor": target, "vif": None})
            continue
        X = np.column_stack([np.ones(len(temp)), temp[others].values])
        fit = ols_fit(X, temp[target].values)
        r2 = fit["r2"]
        vif = None if pd.isna(r2) or r2 >= 1 else 1 / (1 - r2)
        rows.append({"predictor": target, "vif": round(float(vif), 4) if vif is not None else None})
    return rows


def confidence_weight(count, method):
    if method == "sqrt":
        return math.sqrt(max(float(count), 0.0))
    if method == "log":
        return math.log1p(max(float(count), 0.0))
    return 1.0


def threshold_robustness():
    log("========== Hotspot Threshold Robustness ==========")
    df = pd.read_csv(STATION_WATERSHED)
    df = df.dropna(subset=["mean_nitrate_mg_L", "p90_nitrate_mg_L", "watershed_name"]).copy()

    thresholds = [0.05, 0.10, 0.20]
    baseline_ids = set()
    baseline_top_watersheds = set()
    summary_rows = []
    watershed_rows = []

    for pct in thresholds:
        mean_cutoff = df["mean_nitrate_mg_L"].quantile(1 - pct)
        p90_cutoff = df["p90_nitrate_mg_L"].quantile(1 - pct)
        label = f"top_{int(pct * 100)}pct"
        is_hotspot = (df["mean_nitrate_mg_L"] >= mean_cutoff) | (df["p90_nitrate_mg_L"] >= p90_cutoff)
        hotspot_df = df[is_hotspot].copy()
        hotspot_ids = set(hotspot_df["station_id"])

        watershed_summary = (
            df.assign(threshold_hotspot=is_hotspot)
            .groupby("watershed_name", as_index=False)
            .agg(
                station_count=("station_id", "count"),
                hotspot_station_count=("threshold_hotspot", "sum"),
                mean_nitrate_mg_L=("mean_nitrate_mg_L", "mean"),
            )
        )
        watershed_summary["threshold"] = label
        watershed_summary["hotspot_rate_percent"] = (
            watershed_summary["hotspot_station_count"] / watershed_summary["station_count"] * 100
        )
        watershed_summary = watershed_summary.sort_values("hotspot_rate_percent", ascending=False)
        top_watersheds = set(watershed_summary.head(5)["watershed_name"])

        if pct == 0.10:
            baseline_ids = hotspot_ids
            baseline_top_watersheds = top_watersheds

        station_jaccard = None
        watershed_jaccard = None
        if baseline_ids:
            station_jaccard = len(hotspot_ids & baseline_ids) / len(hotspot_ids | baseline_ids)
            watershed_jaccard = len(top_watersheds & baseline_top_watersheds) / len(top_watersheds | baseline_top_watersheds)

        summary_rows.append({
            "threshold": label,
            "top_percent": int(pct * 100),
            "mean_cutoff_mg_L": round(float(mean_cutoff), 4),
            "p90_cutoff_mg_L": round(float(p90_cutoff), 4),
            "hotspot_station_count": int(len(hotspot_df)),
            "hotspot_station_percent": round(float(len(hotspot_df) / len(df) * 100), 2),
            "top5_watersheds": "; ".join(watershed_summary.head(5)["watershed_name"].tolist()),
            "station_jaccard_vs_10pct": round(float(station_jaccard), 4) if station_jaccard is not None else None,
            "top5_watershed_jaccard_vs_10pct": round(float(watershed_jaccard), 4) if watershed_jaccard is not None else None,
        })
        watershed_rows.extend(watershed_summary.to_dict(orient="records"))

    summary = pd.DataFrame(summary_rows)
    watershed_summary = pd.DataFrame(watershed_rows)
    summary.to_csv(OUT_THRESHOLD_CSV, index=False)
    watershed_summary.to_csv(OUT_THRESHOLD_WATERSHED_CSV, index=False)
    export_json(summary, OUT_THRESHOLD_JSON)
    export_json(watershed_summary, OUT_THRESHOLD_WATERSHED_JSON)

    plt.figure(figsize=(9, 5))
    plt.bar(summary["threshold"], summary["hotspot_station_count"], color=["#2563eb", "#0f766e", "#d97706"])
    plt.ylabel("Hotspot station count")
    plt.title("Hotspot Count Under Alternative Thresholds")
    for _, row in summary.iterrows():
        plt.text(row["threshold"], row["hotspot_station_count"], str(row["hotspot_station_count"]), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(FIG_THRESHOLD, dpi=200)
    plt.close()
    log(summary.to_string(index=False))


def reliability_analysis():
    log("")
    log("========== Confidence and Weighted Reliability ==========")
    df = pd.read_csv(STATION_WATERSHED)
    df = df.dropna(subset=["watershed_name", "mean_nitrate_mg_L", "is_hotspot"]).copy()
    df["is_hotspot"] = df["is_hotspot"].astype(bool)

    scenarios = [
        ("all_stations", df.copy()),
        ("high_medium_only", df[df["confidence_level"].isin(["High", "Medium"])].copy()),
        ("sqrt_weighted", df.copy()),
        ("log_weighted", df.copy()),
    ]

    rows = []
    for scenario, sub in scenarios:
        if sub.empty:
            continue
        method = "sqrt" if scenario == "sqrt_weighted" else "log" if scenario == "log_weighted" else "none"
        sub["analysis_weight"] = sub["observation_count"].apply(lambda x: confidence_weight(x, method))
        for watershed, group in sub.groupby("watershed_name"):
            weight = group["analysis_weight"].values
            mean_values = group["mean_nitrate_mg_L"].values
            hotspot_values = group["is_hotspot"].astype(float).values
            rows.append({
                "scenario": scenario,
                "watershed_name": watershed,
                "station_count": int(len(group)),
                "total_weight": round(float(weight.sum()), 4),
                "weighted_mean_nitrate_mg_L": round(float(np.average(mean_values, weights=weight)), 6),
                "weighted_hotspot_rate_percent": round(float(np.average(hotspot_values, weights=weight) * 100), 6),
                "unweighted_hotspot_rate_percent": round(float(hotspot_values.mean() * 100), 6),
                "high_medium_station_count": int(group["confidence_level"].isin(["High", "Medium"]).sum()),
            })

    result = pd.DataFrame(rows)
    result.to_csv(OUT_RELIABILITY_CSV, index=False)
    export_json(result, OUT_RELIABILITY_JSON)

    plot_df = result[result["scenario"].isin(["all_stations", "high_medium_only", "sqrt_weighted", "log_weighted"])].copy()
    top_names = (
        plot_df[plot_df["scenario"] == "all_stations"]
        .sort_values("weighted_hotspot_rate_percent", ascending=False)
        .head(8)["watershed_name"]
        .tolist()
    )
    plot_df = plot_df[plot_df["watershed_name"].isin(top_names)]
    pivot = plot_df.pivot(index="watershed_name", columns="scenario", values="weighted_hotspot_rate_percent").loc[top_names]
    pivot.plot(kind="bar", figsize=(13, 6))
    plt.ylabel("Hotspot rate (%)")
    plt.title("Hotspot Pattern After Confidence Filtering and Weighting")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(FIG_RELIABILITY, dpi=200)
    plt.close()
    log(result.groupby("scenario")["station_count"].sum().to_string())


def run_simplified_models():
    log("")
    log("========== Simplified Model and VIF Comparison ==========")
    df = pd.read_csv(WATERSHED_JOINED)
    numeric_cols = [c for c in df.columns if c != "watershed_name"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    targets = ["hotspot_rate_percent", "mean_nitrate_mg_L", "mean_p90_nitrate_mg_L"]
    model_sets = {
        "developed_only": ["developed_percent"],
        "agriculture_only": ["agriculture_percent"],
        "developed_agriculture": ["developed_percent", "agriculture_percent"],
        "developed_forest_wetlands": ["developed_percent", "forest_percent", "wetlands_percent"],
        "facility_total_only": ["facility_density_per_100_km2"],
        "industrial_only": ["industrial_stormwater_density_per_100_km2"],
        "developed_industrial": ["developed_percent", "industrial_stormwater_density_per_100_km2"],
        "independent_low_vif_core": ["developed_percent", "agriculture_percent", "septic_groundwater_density_per_100_km2"],
    }

    rows = []
    for target in targets:
        if target not in df.columns:
            continue
        for model_name, predictors in model_sets.items():
            predictors = [p for p in predictors if p in df.columns]
            temp = df[["watershed_name", target] + predictors].dropna().copy()
            if len(temp) < len(predictors) + 3:
                continue
            z = temp[predictors].copy()
            z = (z - z.mean()) / z.std(ddof=0).replace(0, np.nan)
            z = z.fillna(0)
            X = np.column_stack([np.ones(len(z)), z.values])
            fit = ols_fit(X, temp[target].values)
            vif_rows = calculate_vif(temp, predictors)
            max_vif = max([r["vif"] for r in vif_rows if r["vif"] is not None], default=1.0)
            rows.append({
                "target_metric": target,
                "model_name": model_name,
                "predictors": ", ".join(predictors),
                "n": int(fit["n"]),
                "r2": round(float(fit["r2"]), 4),
                "adjusted_r2": round(float(fit["adjusted_r2"]), 4),
                "rmse": round(float(fit["rmse"]), 4),
                "max_vif": round(float(max_vif), 4),
                "vif_status": "acceptable" if max_vif < 5 else "too_high",
            })

    result = pd.DataFrame(rows).sort_values(["target_metric", "adjusted_r2"], ascending=[True, False])
    result.to_csv(OUT_MODEL_CSV, index=False)
    export_json(result, OUT_MODEL_JSON)

    plot_df = result[result["target_metric"].isin(["hotspot_rate_percent", "mean_nitrate_mg_L"])].copy()
    plot_df["label"] = plot_df["target_metric"].str.replace("_", " ") + "\n" + plot_df["model_name"].str.replace("_", " ")
    colors = ["#16a34a" if v < 5 else "#dc2626" for v in plot_df["max_vif"]]
    plt.figure(figsize=(14, 6))
    plt.bar(plot_df["label"], plot_df["r2"], color=colors)
    plt.ylabel("R2")
    plt.title("Simplified Model Comparison (Green = max VIF < 5)")
    plt.xticks(rotation=55, ha="right")
    plt.tight_layout()
    plt.savefig(FIG_MODEL, dpi=200)
    plt.close()
    log(result.to_string(index=False))


def rainfall_analysis():
    log("")
    log("========== Rainfall Factor Analysis ==========")
    nitrate = pd.read_csv(NITRATE_STANDARDIZED, usecols=["year", "nitrate_mg_L"])
    yearly_nitrate = (
        nitrate.dropna()
        .groupby("year", as_index=False)
        .agg(mean_nitrate_mg_L=("nitrate_mg_L", "mean"), observation_count=("nitrate_mg_L", "count"))
    )

    url = (
        "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/"
        "statewide/time-series/28/pcp/12/12/2000-2026.csv"
        "?base_prd=true&begbaseyear=1901&endbaseyear=2000"
    )

    if not RAINFALL_CSV.exists():
        try:
            log(f"Downloading NOAA New Jersey annual precipitation: {url}")
            urllib.request.urlretrieve(url, RAINFALL_CSV)
        except Exception as exc:
            log(f"Rainfall download failed; skipping rainfall analysis. Error: {exc}")
            pd.DataFrame([{
                "status": "download_failed",
                "source": url,
                "note": "Run this script with network access to include NOAA statewide precipitation."
            }]).to_csv(OUT_RAINFALL_CSV, index=False)
            export_json(pd.read_csv(OUT_RAINFALL_CSV), OUT_RAINFALL_JSON)
            return

    rain = pd.read_csv(RAINFALL_CSV, comment="#")
    rain.columns = [str(c).strip() for c in rain.columns]
    year_col = "Date" if "Date" in rain.columns else rain.columns[0]
    value_col = "Value" if "Value" in rain.columns else rain.columns[-1]
    rain = rain[[year_col, value_col]].rename(columns={year_col: "year", value_col: "annual_precip_inches"})
    raw_year = rain["year"].astype(str).str.strip()
    rain["year"] = pd.to_numeric(raw_year, errors="coerce")

    # NOAA Climate at a Glance annual CSV encodes December annual values as YYYY12.
    # Convert YYYYMM to YYYY so it can join with the nitrate observation year.
    yyyymm_mask = raw_year.str.fullmatch(r"\d{6}", na=False)
    rain.loc[yyyymm_mask, "year"] = pd.to_numeric(raw_year[yyyymm_mask].str.slice(0, 4), errors="coerce")

    rain["annual_precip_inches"] = pd.to_numeric(rain["annual_precip_inches"], errors="coerce")
    rain = rain.dropna()
    rain["year"] = rain["year"].astype(int)

    joined = yearly_nitrate.merge(rain, on="year", how="inner")
    r = pearson(joined["annual_precip_inches"], joined["mean_nitrate_mg_L"])
    rho = spearman(joined["annual_precip_inches"], joined["mean_nitrate_mg_L"])
    joined["pearson_r_precip_vs_mean_nitrate"] = round(float(r), 4) if r is not None else None
    joined["spearman_r_precip_vs_mean_nitrate"] = round(float(rho), 4) if rho is not None else None
    joined.to_csv(OUT_RAINFALL_CSV, index=False)
    export_json(joined, OUT_RAINFALL_JSON)

    plt.figure(figsize=(8, 6))
    plt.scatter(joined["annual_precip_inches"], joined["mean_nitrate_mg_L"])
    for _, row in joined.iterrows():
        plt.annotate(str(int(row["year"])), (row["annual_precip_inches"], row["mean_nitrate_mg_L"]), fontsize=8)
    plt.xlabel("NJ annual precipitation (inches)")
    plt.ylabel("Mean nitrate (mg/L)")
    plt.title("NOAA Annual Precipitation vs Mean Nitrate")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_RAINFALL, dpi=200)
    plt.close()
    log(f"Rainfall correlation Pearson={r}, Spearman={rho}, n={len(joined)}")


def main():
    ensure_dirs()
    log("========== Step 18: Robustness, Reliability, Other Factors, and Model Refinement ==========")
    threshold_robustness()
    reliability_analysis()
    run_simplified_models()
    rainfall_analysis()
    log("")
    log("========== Step 18 Complete ==========")


if __name__ == "__main__":
    main()
