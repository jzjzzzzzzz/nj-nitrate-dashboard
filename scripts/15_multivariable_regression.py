import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


# ============================================================
# Step 15: Multivariable Regression / Control Model
# Purpose:
#   Test whether NJPDES facility density is still associated with
#   nitrate hotspot metrics after controlling for developed land use.
#
# Important:
#   This is watershed-level exploratory modeling.
#   It shows association, not causation.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / "data" / "processed" / "watershed_land_use_wastewater_nitrate_joined.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_FIGURES = BASE_DIR / "output" / "figures"
OUT_LOGS = BASE_DIR / "output" / "logs"

OUT_MODEL_COMPARISON_CSV = OUT_PROCESSED / "multivariable_model_comparison.csv"
OUT_MODEL_COEFFICIENTS_CSV = OUT_PROCESSED / "multivariable_model_coefficients.csv"
OUT_MODEL_PREDICTIONS_CSV = OUT_PROCESSED / "multivariable_model_predictions.csv"
OUT_MODEL_VIF_CSV = OUT_PROCESSED / "multivariable_model_vif.csv"

OUT_MODEL_COMPARISON_JSON = OUT_DASHBOARD / "multivariable_model_comparison.json"
OUT_MODEL_COEFFICIENTS_JSON = OUT_DASHBOARD / "multivariable_model_coefficients.json"
OUT_MODEL_PREDICTIONS_JSON = OUT_DASHBOARD / "multivariable_model_predictions.json"
OUT_MODEL_VIF_JSON = OUT_DASHBOARD / "multivariable_model_vif.json"

OUT_FIG_R2 = OUT_FIGURES / "multivariable_model_r2_comparison.png"
OUT_FIG_HOTSPOT_OBS_PRED = OUT_FIGURES / "observed_vs_predicted_hotspot_rate.png"
OUT_FIG_MEAN_OBS_PRED = OUT_FIGURES / "observed_vs_predicted_mean_nitrate.png"
OUT_FIG_HOTSPOT_COEF = OUT_FIGURES / "hotspot_rate_model_coefficients.png"
OUT_FIG_MEAN_COEF = OUT_FIGURES / "mean_nitrate_model_coefficients.png"
OUT_FIG_HOTSPOT_RESID = OUT_FIGURES / "hotspot_rate_residuals.png"
OUT_FIG_MEAN_RESID = OUT_FIGURES / "mean_nitrate_residuals.png"

LOG_PATH = OUT_LOGS / "15_multivariable_regression_log.txt"


# ============================================================
# Utility functions
# ============================================================

def ensure_dirs():
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)
    OUT_LOGS.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        LOG_PATH.unlink()


def log(message):
    print(message)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def export_json(df, path):
    clean = df.copy()
    clean = clean.replace([np.inf, -np.inf], np.nan)
    records = clean.where(pd.notna(clean), None).to_dict(orient="records")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def safe_numeric(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def require_columns(df, required_cols):
    missing = []

    for col in required_cols:
        if col not in df.columns:
            missing.append(col)

    if missing:
        raise ValueError(
            "Missing required columns:\n"
            + "\n".join(missing)
            + "\n\nPlease rerun Step 10, Step 11, Step 12, and Step 13 first."
        )


def clean_metric_name(name):
    return (
        str(name)
        .replace("_", " ")
        .replace("per 100 km2", "per 100 km²")
        .replace("per 100 km 2", "per 100 km²")
    )


def standardize_columns(df, cols):
    result = df.copy()
    means = {}
    stds = {}

    for col in cols:
        mean = result[col].mean()
        std = result[col].std(ddof=0)

        means[col] = mean
        stds[col] = std

        if pd.isna(std) or std == 0:
            result[col + "_z"] = 0
        else:
            result[col + "_z"] = (result[col] - mean) / std

    return result, means, stds


def ols_fit(X, y):
    """
    OLS using numpy only.
    X should already include intercept column.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    n = X.shape[0]
    p = X.shape[1]

    beta = np.linalg.pinv(X.T @ X) @ X.T @ y
    y_pred = X @ beta

    residuals = y - y_pred

    sse = float(np.sum(residuals ** 2))
    mse = sse / n if n > 0 else np.nan
    rmse = math.sqrt(mse) if mse >= 0 else np.nan

    y_mean = float(np.mean(y))
    sst = float(np.sum((y - y_mean) ** 2))

    if sst == 0:
        r2 = np.nan
    else:
        r2 = 1 - (sse / sst)

    if n - p - 1 == 0:
        adjusted_r2 = np.nan
    else:
        adjusted_r2 = 1 - ((1 - r2) * (n - 1) / max(n - p, 1))

    mae = float(np.mean(np.abs(residuals)))

    if mse <= 0:
        aic = np.nan
        bic = np.nan
    else:
        aic = n * math.log(mse) + 2 * p
        bic = n * math.log(mse) + p * math.log(n)

    return {
        "beta": beta,
        "y_pred": y_pred,
        "residuals": residuals,
        "n": n,
        "p": p,
        "sse": sse,
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "adjusted_r2": adjusted_r2,
        "aic": aic,
        "bic": bic,
    }


def calculate_vif(df, predictor_cols):
    """
    Calculate VIF for each predictor.
    VIF = 1 / (1 - R²)
    """
    rows = []

    usable = df[predictor_cols].dropna().copy()

    if len(usable) < 3:
        return pd.DataFrame(columns=["predictor", "vif", "interpretation"])

    for target_col in predictor_cols:
        other_cols = [col for col in predictor_cols if col != target_col]

        if len(other_cols) == 0:
            rows.append({
                "predictor": target_col,
                "vif": None,
                "interpretation": "Only one predictor"
            })
            continue

        temp = usable[[target_col] + other_cols].dropna()

        if len(temp) < len(other_cols) + 2:
            rows.append({
                "predictor": target_col,
                "vif": None,
                "interpretation": "Too few rows"
            })
            continue

        y = temp[target_col].values
        X = temp[other_cols].values
        X = np.column_stack([np.ones(len(X)), X])

        fit = ols_fit(X, y)
        r2 = fit["r2"]

        if pd.isna(r2) or r2 >= 1:
            vif = None
        else:
            vif = 1 / (1 - r2)

        if vif is None:
            interpretation = "not available"
        elif vif < 5:
            interpretation = "acceptable"
        elif vif < 10:
            interpretation = "possible multicollinearity"
        else:
            interpretation = "high multicollinearity"

        rows.append({
            "predictor": target_col,
            "vif": round(float(vif), 4) if vif is not None else None,
            "interpretation": interpretation
        })

    return pd.DataFrame(rows)


def run_model(df, target_col, predictor_cols, model_name):
    """
    Run regression with standardized predictors.
    Target remains in original units.
    """
    needed_cols = ["watershed_name", target_col] + predictor_cols
    temp = df[needed_cols].copy()
    temp = temp.dropna(subset=[target_col] + predictor_cols).copy()

    if len(temp) < len(predictor_cols) + 3:
        return None, None, None

    z_df, means, stds = standardize_columns(temp, predictor_cols)
    z_cols = [col + "_z" for col in predictor_cols]

    X = z_df[z_cols].values
    X = np.column_stack([np.ones(len(X)), X])
    y = z_df[target_col].values

    fit = ols_fit(X, y)

    comparison_row = {
        "target_metric": target_col,
        "model_name": model_name,
        "predictors": ", ".join(predictor_cols),
        "n": fit["n"],
        "num_parameters_including_intercept": fit["p"],
        "r2": round(float(fit["r2"]), 4) if pd.notna(fit["r2"]) else None,
        "adjusted_r2": round(float(fit["adjusted_r2"]), 4) if pd.notna(fit["adjusted_r2"]) else None,
        "rmse": round(float(fit["rmse"]), 4) if pd.notna(fit["rmse"]) else None,
        "mae": round(float(fit["mae"]), 4) if pd.notna(fit["mae"]) else None,
        "aic": round(float(fit["aic"]), 4) if pd.notna(fit["aic"]) else None,
        "bic": round(float(fit["bic"]), 4) if pd.notna(fit["bic"]) else None,
    }

    coef_rows = []

    coef_rows.append({
        "target_metric": target_col,
        "model_name": model_name,
        "predictor": "intercept",
        "coefficient": round(float(fit["beta"][0]), 6),
        "coefficient_type": "intercept"
    })

    for idx, predictor in enumerate(predictor_cols):
        coef_rows.append({
            "target_metric": target_col,
            "model_name": model_name,
            "predictor": predictor,
            "coefficient": round(float(fit["beta"][idx + 1]), 6),
            "coefficient_type": "standardized_predictor"
        })

    prediction_df = pd.DataFrame({
        "watershed_name": z_df["watershed_name"],
        "target_metric": target_col,
        "model_name": model_name,
        "observed": y,
        "predicted": fit["y_pred"],
        "residual": fit["residuals"]
    })

    prediction_df["observed"] = prediction_df["observed"].round(6)
    prediction_df["predicted"] = prediction_df["predicted"].round(6)
    prediction_df["residual"] = prediction_df["residual"].round(6)

    return comparison_row, coef_rows, prediction_df


def plot_r2_comparison(model_comparison_df):
    if model_comparison_df.empty:
        return

    temp = model_comparison_df.copy()
    temp["label"] = temp["target_metric"] + "\n" + temp["model_name"]

    plt.figure(figsize=(12, 7))
    plt.bar(temp["label"], temp["r2"])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("R²")
    plt.title("Step 15 Multivariable Model Comparison")
    plt.tight_layout()
    plt.savefig(OUT_FIG_R2, dpi=200)
    plt.close()

    log(f"[EXPORT] {OUT_FIG_R2}")


def plot_observed_vs_predicted(prediction_df, target_col, model_name, output_path, title, y_label):
    sub = prediction_df[
        (prediction_df["target_metric"] == target_col)
        & (prediction_df["model_name"] == model_name)
    ].copy()

    if sub.empty:
        return

    plt.figure(figsize=(8, 8))
    plt.scatter(sub["observed"], sub["predicted"])

    min_value = min(sub["observed"].min(), sub["predicted"].min())
    max_value = max(sub["observed"].max(), sub["predicted"].max())

    plt.plot([min_value, max_value], [min_value, max_value], linestyle="--")

    for _, row in sub.iterrows():
        name = str(row["watershed_name"])

        if abs(row["residual"]) >= sub["residual"].abs().quantile(0.8):
            plt.annotate(
                name,
                (row["observed"], row["predicted"]),
                fontsize=8,
                xytext=(5, 5),
                textcoords="offset points"
            )

    plt.xlabel("Observed " + y_label)
    plt.ylabel("Predicted " + y_label)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()

    log(f"[EXPORT] {output_path}")


def plot_coefficients(coef_df, target_col, model_name, output_path, title):
    sub = coef_df[
        (coef_df["target_metric"] == target_col)
        & (coef_df["model_name"] == model_name)
        & (coef_df["predictor"] != "intercept")
    ].copy()

    if sub.empty:
        return

    sub = sub.sort_values("coefficient")

    labels = [clean_metric_name(x) for x in sub["predictor"]]

    plt.figure(figsize=(10, 6))
    plt.barh(labels, sub["coefficient"])
    plt.axvline(0, linestyle="--")
    plt.xlabel("Coefficient with standardized predictors")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()

    log(f"[EXPORT] {output_path}")


def plot_residuals(prediction_df, target_col, model_name, output_path, title):
    sub = prediction_df[
        (prediction_df["target_metric"] == target_col)
        & (prediction_df["model_name"] == model_name)
    ].copy()

    if sub.empty:
        return

    sub = sub.sort_values("residual")

    plt.figure(figsize=(11, 6))
    plt.bar(sub["watershed_name"], sub["residual"])
    plt.axhline(0, linestyle="--")
    plt.xticks(rotation=60, ha="right")
    plt.ylabel("Residual")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()

    log(f"[EXPORT] {output_path}")


def main():
    ensure_dirs()

    log("========== Step 15: Multivariable Regression / Control Model ==========")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing input file:\n{INPUT_PATH}\n\nPlease run Step 12 first."
        )

    log(f"[READ] {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    log(f"Rows loaded: {len(df):,}")
    log(f"Columns loaded: {len(df.columns):,}")

    required_cols = [
        "watershed_name",
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "developed_percent",
        "agriculture_percent",
        "facility_density_per_100_km2",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_density_per_100_km2",
    ]

    require_columns(df, required_cols)

    numeric_cols = [
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
        "mean_p90_nitrate_mg_L",
        "max_station_nitrate_mg_L",
        "developed_percent",
        "agriculture_percent",
        "forest_percent",
        "wetlands_percent",
        "facility_density_per_100_km2",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_density_per_100_km2",
        "residuals_or_recycling_density_per_100_km2",
        "construction_or_permit_density_per_100_km2",
        "mining_quarrying_density_per_100_km2",
    ]

    df = safe_numeric(df, numeric_cols)

    log("")
    log("========== Modeling Columns ==========")
    for col in required_cols:
        log(col)

    target_metrics = [
        "hotspot_rate_percent",
        "mean_nitrate_mg_L",
    ]

    if "mean_p90_nitrate_mg_L" in df.columns:
        target_metrics.append("mean_p90_nitrate_mg_L")

    if "max_station_nitrate_mg_L" in df.columns:
        target_metrics.append("max_station_nitrate_mg_L")

    models = {
        "land_use_only": [
            "developed_percent",
            "agriculture_percent",
        ],
        "facility_only": [
            "facility_density_per_100_km2",
            "industrial_stormwater_density_per_100_km2",
            "septic_groundwater_density_per_100_km2",
        ],
        "developed_plus_total_facility": [
            "developed_percent",
            "facility_density_per_100_km2",
        ],
        "developed_plus_industrial": [
            "developed_percent",
            "industrial_stormwater_density_per_100_km2",
        ],
        "combined_core": [
            "developed_percent",
            "agriculture_percent",
            "facility_density_per_100_km2",
            "industrial_stormwater_density_per_100_km2",
        ],
        "combined_extended": [
            "developed_percent",
            "agriculture_percent",
            "facility_density_per_100_km2",
            "industrial_stormwater_density_per_100_km2",
            "septic_groundwater_density_per_100_km2",
            "groundwater_discharge_density_per_100_km2",
            "stormwater_or_surface_density_per_100_km2",
        ],
    }

    comparison_rows = []
    coefficient_rows = []
    prediction_tables = []

    for target_col in target_metrics:
        log("")
        log(f"========== Target Metric: {target_col} ==========")

        for model_name, predictors in models.items():
            predictors = [col for col in predictors if col in df.columns]

            if len(predictors) == 0:
                continue

            comparison_row, coef_rows, prediction_df = run_model(
                df=df,
                target_col=target_col,
                predictor_cols=predictors,
                model_name=model_name
            )

            if comparison_row is None:
                log(f"[SKIP] {model_name}: too few rows or too many predictors")
                continue

            comparison_rows.append(comparison_row)
            coefficient_rows.extend(coef_rows)
            prediction_tables.append(prediction_df)

            log(
                f"{model_name} | "
                f"predictors={predictors} | "
                f"R2={comparison_row['r2']} | "
                f"Adjusted R2={comparison_row['adjusted_r2']} | "
                f"RMSE={comparison_row['rmse']} | "
                f"n={comparison_row['n']}"
            )

    model_comparison_df = pd.DataFrame(comparison_rows)
    model_coefficients_df = pd.DataFrame(coefficient_rows)

    if prediction_tables:
        model_predictions_df = pd.concat(prediction_tables, ignore_index=True)
    else:
        model_predictions_df = pd.DataFrame()

    all_predictors_for_vif = [
        "developed_percent",
        "agriculture_percent",
        "facility_density_per_100_km2",
        "industrial_stormwater_density_per_100_km2",
        "septic_groundwater_density_per_100_km2",
        "groundwater_discharge_density_per_100_km2",
        "stormwater_or_surface_density_per_100_km2",
    ]

    all_predictors_for_vif = [col for col in all_predictors_for_vif if col in df.columns]

    vif_df = calculate_vif(df, all_predictors_for_vif)

    if not model_comparison_df.empty:
        model_comparison_df = model_comparison_df.sort_values(
            ["target_metric", "adjusted_r2"],
            ascending=[True, False]
        ).reset_index(drop=True)

    model_comparison_df.to_csv(OUT_MODEL_COMPARISON_CSV, index=False)
    model_coefficients_df.to_csv(OUT_MODEL_COEFFICIENTS_CSV, index=False)
    model_predictions_df.to_csv(OUT_MODEL_PREDICTIONS_CSV, index=False)
    vif_df.to_csv(OUT_MODEL_VIF_CSV, index=False)

    export_json(model_comparison_df, OUT_MODEL_COMPARISON_JSON)
    export_json(model_coefficients_df, OUT_MODEL_COEFFICIENTS_JSON)
    export_json(model_predictions_df, OUT_MODEL_PREDICTIONS_JSON)
    export_json(vif_df, OUT_MODEL_VIF_JSON)

    log("")
    log("========== Exported Tables ==========")
    log(f"[EXPORT] {OUT_MODEL_COMPARISON_CSV}")
    log(f"[EXPORT] {OUT_MODEL_COEFFICIENTS_CSV}")
    log(f"[EXPORT] {OUT_MODEL_PREDICTIONS_CSV}")
    log(f"[EXPORT] {OUT_MODEL_VIF_CSV}")
    log(f"[EXPORT] {OUT_MODEL_COMPARISON_JSON}")
    log(f"[EXPORT] {OUT_MODEL_COEFFICIENTS_JSON}")
    log(f"[EXPORT] {OUT_MODEL_PREDICTIONS_JSON}")
    log(f"[EXPORT] {OUT_MODEL_VIF_JSON}")

    log("")
    log("========== VIF / Multicollinearity Check ==========")
    if vif_df.empty:
        log("No VIF results available.")
    else:
        log(vif_df.to_string(index=False))

    plot_r2_comparison(model_comparison_df)

    best_hotspot_model = "combined_core"
    best_mean_model = "combined_core"

    plot_observed_vs_predicted(
        prediction_df=model_predictions_df,
        target_col="hotspot_rate_percent",
        model_name=best_hotspot_model,
        output_path=OUT_FIG_HOTSPOT_OBS_PRED,
        title="Observed vs Predicted Hotspot Rate",
        y_label="Hotspot Rate (%)"
    )

    plot_observed_vs_predicted(
        prediction_df=model_predictions_df,
        target_col="mean_nitrate_mg_L",
        model_name=best_mean_model,
        output_path=OUT_FIG_MEAN_OBS_PRED,
        title="Observed vs Predicted Mean Nitrate",
        y_label="Mean Nitrate (mg/L)"
    )

    plot_coefficients(
        coef_df=model_coefficients_df,
        target_col="hotspot_rate_percent",
        model_name=best_hotspot_model,
        output_path=OUT_FIG_HOTSPOT_COEF,
        title="Hotspot Rate Model Coefficients"
    )

    plot_coefficients(
        coef_df=model_coefficients_df,
        target_col="mean_nitrate_mg_L",
        model_name=best_mean_model,
        output_path=OUT_FIG_MEAN_COEF,
        title="Mean Nitrate Model Coefficients"
    )

    plot_residuals(
        prediction_df=model_predictions_df,
        target_col="hotspot_rate_percent",
        model_name=best_hotspot_model,
        output_path=OUT_FIG_HOTSPOT_RESID,
        title="Hotspot Rate Residuals by Watershed"
    )

    plot_residuals(
        prediction_df=model_predictions_df,
        target_col="mean_nitrate_mg_L",
        model_name=best_mean_model,
        output_path=OUT_FIG_MEAN_RESID,
        title="Mean Nitrate Residuals by Watershed"
    )

    log("")
    log("========== Main Interpretation Guide ==========")
    log("Use the model comparison table to answer the research question:")
    log("1. If land_use_only has high R² and facility_only does not add much, facility density may mostly reflect developed land.")
    log("2. If developed_plus_total_facility improves adjusted R² over land_use_only, facility density may add extra explanatory value.")
    log("3. If combined_core improves adjusted R² but VIF is high, be careful because predictors may be strongly correlated.")
    log("4. Because there are only about 21 watersheds, avoid overinterpreting the extended model.")
    log("5. These models show association, not causation.")

    log("")
    log("========== Step 15 Complete ==========")


if __name__ == "__main__":
    main()