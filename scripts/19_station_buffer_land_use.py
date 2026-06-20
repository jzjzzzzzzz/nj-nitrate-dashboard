import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from importlib.machinery import SourceFileLoader

warnings.filterwarnings("ignore")


BASE_DIR = Path(__file__).resolve().parents[1]

STATION_SUMMARY = BASE_DIR / "data" / "processed" / "station_summary.csv"
LAND_USE_PATH = BASE_DIR / "data" / "external" / "land_use" / "Land_Use_2020.shp"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_FIGURES = BASE_DIR / "output" / "figures"
OUT_LOGS = BASE_DIR / "output" / "logs"
LOG_PATH = OUT_LOGS / "19_station_buffer_land_use_log.txt"

OUT_BUFFER_SUMMARY_CSV = OUT_PROCESSED / "station_buffer_land_use_summary.csv"
OUT_BUFFER_CORR_CSV = OUT_PROCESSED / "station_buffer_land_use_correlation.csv"
OUT_BUFFER_SUMMARY_JSON = OUT_DASHBOARD / "station_buffer_land_use_summary.json"
OUT_BUFFER_CORR_JSON = OUT_DASHBOARD / "station_buffer_land_use_correlation.json"

FIG_BUFFER_CORR = OUT_FIGURES / "buffer_land_use_scale_correlation.png"
FIG_BUFFER_DEVELOPED = OUT_FIGURES / "buffer_developed_vs_nitrate_by_scale.png"

LAND_USE_HELPERS = SourceFileLoader(
    "land_use_helpers",
    str(BASE_DIR / "scripts" / "10_land_use_watershed_overlay.py")
).load_module()


def ensure_dirs():
    for path in [OUT_PROCESSED, OUT_DASHBOARD, OUT_FIGURES, OUT_LOGS]:
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
    return float(temp["x"].corr(temp["y"]))


def spearman(x, y):
    temp = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(temp) < 3:
        return None
    return pearson(temp["x"].rank(method="average"), temp["y"].rank(method="average"))


def read_inputs():
    if not STATION_SUMMARY.exists():
        raise FileNotFoundError(f"Missing station summary: {STATION_SUMMARY}")
    if not LAND_USE_PATH.exists():
        raise FileNotFoundError(f"Missing land use shapefile: {LAND_USE_PATH}")

    stations = pd.read_csv(STATION_SUMMARY)
    stations = stations.dropna(subset=["latitude", "longitude", "mean_nitrate_mg_L", "p90_nitrate_mg_L"]).copy()

    station_gdf = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["longitude"], stations["latitude"]),
        crs="EPSG:4326",
    ).to_crs("EPSG:3424")

    land_use = gpd.read_file(LAND_USE_PATH)
    land_use_text_col = LAND_USE_HELPERS.pick_land_use_column(land_use)
    land_use_code_col = LAND_USE_HELPERS.pick_land_use_code_column(land_use)
    keep_cols = [land_use_text_col, "geometry"]
    if land_use_code_col and land_use_code_col not in keep_cols:
        keep_cols.insert(1, land_use_code_col)
    land_use = land_use[keep_cols].copy()
    land_use = land_use.rename(columns={land_use_text_col: "land_use_raw"})
    if land_use_code_col:
        land_use = land_use.rename(columns={land_use_code_col: "land_use_code"})
    else:
        land_use["land_use_code"] = None

    land_use["land_use_group"] = land_use.apply(
        lambda row: LAND_USE_HELPERS.classify_land_use(row["land_use_raw"], row["land_use_code"]),
        axis=1,
    )
    land_use = LAND_USE_HELPERS.clean_geometries(land_use, "Land use")
    land_use = LAND_USE_HELPERS.safe_to_crs(land_use, "EPSG:3424", "Land use")
    land_use = land_use[["land_use_group", "geometry"]].copy()

    return station_gdf, land_use


def summarize_buffers(stations, land_use):
    radii_m = [500, 1000, 5000]
    expected_groups = ["developed", "agriculture", "forest", "wetlands", "water", "barren", "other"]
    rows = []

    # EPSG:3424 uses US survey feet. Convert meter radii to feet for buffering.
    meter_to_foot = 3.2808333333

    station_cols = [
        "station_id",
        "station_name",
        "mean_nitrate_mg_L",
        "p90_nitrate_mg_L",
        "observation_count",
        "confidence_level",
        "is_hotspot",
    ]

    for radius_m in radii_m:
        log(f"Running {radius_m} m buffer overlay.")
        buffers = stations[station_cols + ["geometry"]].copy()
        buffers["buffer_radius_m"] = radius_m
        buffers["geometry"] = buffers.geometry.buffer(radius_m * meter_to_foot)
        buffers["buffer_area_m2"] = buffers.geometry.area * 0.09290304

        joined = gpd.sjoin(
            land_use,
            buffers[["station_id", "buffer_radius_m", "buffer_area_m2", "geometry"]],
            how="inner",
            predicate="intersects",
        )
        joined = joined.merge(
            buffers[["station_id", "buffer_radius_m", "buffer_area_m2", "geometry"]],
            on=["station_id", "buffer_radius_m", "buffer_area_m2"],
            suffixes=("_land", "_buffer"),
        )
        joined = gpd.GeoDataFrame(joined, geometry="geometry_land", crs=land_use.crs)

        joined["intersection_area_m2"] = joined.apply(
            lambda row: row["geometry_land"].intersection(row["geometry_buffer"]).area * 0.09290304,
            axis=1,
        )
        joined = joined[joined["intersection_area_m2"] > 0].copy()

        long_summary = (
            joined
            .groupby(["station_id", "buffer_radius_m", "land_use_group"], as_index=False)
            .agg(area_m2=("intersection_area_m2", "sum"), buffer_area_m2=("buffer_area_m2", "first"))
        )
        long_summary["percent"] = long_summary["area_m2"] / long_summary["buffer_area_m2"] * 100

        pivot = long_summary.pivot_table(
            index=["station_id", "buffer_radius_m"],
            columns="land_use_group",
            values="percent",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        for group in expected_groups:
            if group not in pivot.columns:
                pivot[group] = 0.0
        pivot = pivot.rename(columns={group: f"{group}_percent" for group in expected_groups})

        merged = buffers.drop(columns="geometry").merge(pivot, on=["station_id", "buffer_radius_m"], how="left")
        for group in expected_groups:
            col = f"{group}_percent"
            merged[col] = merged[col].fillna(0).round(4)
        rows.append(merged)

    return pd.concat(rows, ignore_index=True)


def correlation_table(summary):
    land_use_cols = ["developed_percent", "agriculture_percent", "forest_percent", "wetlands_percent", "water_percent", "barren_percent"]
    target_cols = ["mean_nitrate_mg_L", "p90_nitrate_mg_L"]
    rows = []
    for radius, group in summary.groupby("buffer_radius_m"):
        for land_col in land_use_cols:
            for target_col in target_cols:
                r = pearson(group[land_col], group[target_col])
                rho = spearman(group[land_col], group[target_col])
                rows.append({
                    "buffer_radius_m": int(radius),
                    "land_use_metric": land_col,
                    "nitrate_metric": target_col,
                    "pearson_r": round(float(r), 4) if r is not None else None,
                    "spearman_r": round(float(rho), 4) if rho is not None else None,
                    "n": int(group[[land_col, target_col]].dropna().shape[0]),
                })
    return pd.DataFrame(rows)


def make_plots(summary, corr):
    plot_corr = corr[corr["nitrate_metric"] == "mean_nitrate_mg_L"].copy()
    plot_corr["label"] = plot_corr["land_use_metric"].str.replace("_percent", "")
    pivot = plot_corr.pivot(index="label", columns="buffer_radius_m", values="pearson_r")
    pivot.plot(kind="bar", figsize=(10, 6))
    plt.axhline(0, color="black", linewidth=0.8)
    plt.ylabel("Pearson r with station mean nitrate")
    plt.title("Land Use Buffer Scale Correlation")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(FIG_BUFFER_CORR, dpi=200)
    plt.close()

    plt.figure(figsize=(12, 4))
    for idx, radius in enumerate([500, 1000, 5000], start=1):
        sub = summary[summary["buffer_radius_m"] == radius]
        plt.subplot(1, 3, idx)
        plt.scatter(sub["developed_percent"], sub["mean_nitrate_mg_L"], alpha=0.45, s=18)
        plt.xlabel("Developed land (%)")
        plt.ylabel("Mean nitrate (mg/L)" if idx == 1 else "")
        plt.title(f"{radius} m")
        plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG_BUFFER_DEVELOPED, dpi=200)
    plt.close()


def main():
    ensure_dirs()
    log("========== Step 19: Station Buffer Land Use Scale Analysis ==========")
    stations, land_use = read_inputs()
    log(f"Stations loaded: {len(stations):,}")
    log(f"Land use polygons loaded: {len(land_use):,}")

    summary = summarize_buffers(stations, land_use)
    corr = correlation_table(summary)

    summary.to_csv(OUT_BUFFER_SUMMARY_CSV, index=False)
    corr.to_csv(OUT_BUFFER_CORR_CSV, index=False)
    export_json(summary, OUT_BUFFER_SUMMARY_JSON)
    export_json(corr, OUT_BUFFER_CORR_JSON)
    make_plots(summary, corr)

    log("")
    log("========== Strongest Buffer Correlations ==========")
    top = corr.reindex(corr["pearson_r"].abs().sort_values(ascending=False).index).head(12)
    log(top.to_string(index=False))
    log("")
    log(f"[EXPORT] {OUT_BUFFER_SUMMARY_CSV}")
    log(f"[EXPORT] {OUT_BUFFER_CORR_CSV}")
    log(f"[EXPORT] {OUT_BUFFER_SUMMARY_JSON}")
    log(f"[EXPORT] {OUT_BUFFER_CORR_JSON}")
    log(f"[EXPORT] {FIG_BUFFER_CORR}")
    log(f"[EXPORT] {FIG_BUFFER_DEVELOPED}")
    log("========== Step 19 Complete ==========")


if __name__ == "__main__":
    main()
