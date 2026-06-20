import os
import json
import glob
import warnings
from pathlib import Path

import pandas as pd
import geopandas as gpd

warnings.filterwarnings("ignore")


# ============================================================
# Step 10: Land Use / Watershed Overlay
# Purpose:
#   Join NJ 2020 land use data with watershed polygons.
#   Then compare watershed nitrate hotspots with land use composition.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

WATERSHED_PATH = BASE_DIR / "data" / "external" / "watershed" / "nj_watershed_management_areas.geojson"
LAND_USE_DIR = BASE_DIR / "data" / "external" / "land_use"

WATERSHED_SUMMARY_PATH = BASE_DIR / "data" / "processed" / "watershed_summary.csv"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_LOGS = BASE_DIR / "output" / "logs"

OUT_LAND_USE_SUMMARY_CSV = OUT_PROCESSED / "watershed_land_use_summary.csv"
OUT_JOINED_CSV = OUT_PROCESSED / "watershed_land_use_nitrate_joined.csv"

OUT_LAND_USE_JSON = OUT_DASHBOARD / "watershed_land_use_summary.json"
OUT_JOINED_JSON = OUT_DASHBOARD / "watershed_land_use_nitrate_joined.json"

LOG_PATH = OUT_LOGS / "10_land_use_watershed_overlay_log.txt"


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def ensure_dirs():
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.mkdir(parents=True, exist_ok=True)
    OUT_LOGS.mkdir(parents=True, exist_ok=True)

    if LOG_PATH.exists():
        LOG_PATH.unlink()


def find_land_use_file():
    """
    Find land use GIS file.
    Your current file should be:
      data/external/land_use/Land_Use_2020.shp

    This also supports shapefiles inside subfolders.
    """

    direct_target = LAND_USE_DIR / "Land_Use_2020.shp"

    if direct_target.exists():
        return direct_target

    patterns = [
        "**/*.shp",
        "**/*.geojson",
        "**/*.json",
        "**/*.gpkg",
    ]

    files = []

    for pattern in patterns:
        files.extend(glob.glob(str(LAND_USE_DIR / pattern), recursive=True))

    if not files:
        raise FileNotFoundError(
            f"No land use GIS file found in:\n{LAND_USE_DIR}\n\n"
            "Expected something like:\n"
            "data/external/land_use/Land_Use_2020.shp"
        )

    shp_files = [Path(f) for f in files if f.lower().endswith(".shp")]

    if shp_files:
        return shp_files[0]

    return Path(files[0])


def check_shapefile_sidecars(shp_path):
    """
    Shapefile needs .shp, .shx, .dbf.
    .prj is also important because it stores projection information.
    """

    if shp_path.suffix.lower() != ".shp":
        return

    required = [".shp", ".shx", ".dbf"]
    recommended = [".prj"]

    missing_required = []
    missing_recommended = []

    for ext in required:
        file_path = shp_path.with_suffix(ext)
        if not file_path.exists():
            missing_required.append(str(file_path))

    for ext in recommended:
        file_path = shp_path.with_suffix(ext)
        if not file_path.exists():
            missing_recommended.append(str(file_path))

    if missing_required:
        raise FileNotFoundError(
            "Your shapefile is missing required sidecar files:\n"
            + "\n".join(missing_required)
            + "\n\nMake sure .shp, .shx, and .dbf are in the same folder."
        )

    if missing_recommended:
        log("WARNING: Missing recommended shapefile file:")
        for file in missing_recommended:
            log(file)


def pick_watershed_name_column(gdf):
    candidates = [
        "WMA_NAME",
        "WMA",
        "WMANAME",
        "NAME",
        "Name",
        "name",
        "BASIN",
        "BASIN_NAME",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    raise ValueError(
        "Could not find watershed name column. Available columns:\n"
        + "\n".join(gdf.columns)
    )


def pick_land_use_column(gdf):
    """
    NJ land use shapefiles often use short column names.
    Your file has:
      TYPE20
      LU20
      LABEL20

    TYPE20 is the best text category column.
    """

    candidates = [
        "TYPE20",
        "LABEL20",
        "TYPE2020",
        "LABEL2020",
        "TYPE",
        "LU2020",
        "LU20",
        "LAND_USE",
        "LANDUSE",
        "LULC",
        "CLASS",
        "CLASS_NAME",
        "DESCRIPT",
        "DESCRIP",
        "DESCRIPTIO",
        "LABEL",
        "NAME",
        "Name",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    text_cols = []

    for col in gdf.columns:
        if col == "geometry":
            continue

        if gdf[col].dtype == "object":
            text_cols.append(col)

    if text_cols:
        return text_cols[0]

    raise ValueError(
        "Could not find land use classification column. Available columns:\n"
        + "\n".join(gdf.columns)
    )


def pick_land_use_code_column(gdf):
    """
    Your file has LU20, which is the Anderson-style land use code.
    """

    candidates = [
        "LU20",
        "LU2020",
        "CODE2020",
        "CODE20",
        "LUCODE",
        "LULC_CODE",
        "TYPE_CODE",
        "LANDUSECOD",
        "LANDUSECO",
        "ANDERSON",
        "LU_CODE",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    numeric_cols = []

    for col in gdf.columns:
        if col == "geometry":
            continue

        if pd.api.types.is_numeric_dtype(gdf[col]):
            numeric_cols.append(col)

    if numeric_cols:
        return numeric_cols[0]

    return None


def classify_land_use(value, code_value=None):
    """
    Group detailed land use classes into broad categories:
      developed, agriculture, forest, wetlands, water, barren, other
    """

    text = str(value).upper() if pd.notna(value) else ""
    code_text = str(code_value).upper() if code_value is not None and pd.notna(code_value) else ""

    combined = f"{text} {code_text}"

    numeric_code = None

    for token in [code_text, text]:
        try:
            numeric_code = int(float(token))
            break
        except Exception:
            pass

    # Anderson-style code grouping
    # 1 = urban/developed
    # 2 = agriculture
    # 3 = barren
    # 4 = forest
    # 5 = water
    # 6 = wetlands
    if numeric_code is not None:
        first_digit = str(abs(numeric_code))[0]

        if first_digit == "1":
            return "developed"
        if first_digit == "2":
            return "agriculture"
        if first_digit == "3":
            return "barren"
        if first_digit == "4":
            return "forest"
        if first_digit == "5":
            return "water"
        if first_digit == "6":
            return "wetlands"

    if any(word in combined for word in [
        "URBAN",
        "RESIDENTIAL",
        "COMMERCIAL",
        "INDUSTRIAL",
        "TRANSPORTATION",
        "DEVELOPED",
        "BUILT",
        "ROAD",
        "RAIL",
        "PARKING",
        "RECREATIONAL",
        "MAINTAINED",
    ]):
        return "developed"

    if any(word in combined for word in [
        "AGRICULTURE",
        "AGRICULTURAL",
        "CROPLAND",
        "CROP",
        "PASTURE",
        "ORCHARD",
        "VINEYARD",
        "FARM",
        "FIELD",
    ]):
        return "agriculture"

    if any(word in combined for word in [
        "FOREST",
        "WOODED",
        "WOODLAND",
        "DECIDUOUS",
        "CONIFEROUS",
        "MIXED FOREST",
        "BRUSH",
        "SHRUB",
    ]):
        return "forest"

    if any(word in combined for word in [
        "WETLAND",
        "MARSH",
        "SWAMP",
        "BOG",
    ]):
        return "wetlands"

    if any(word in combined for word in [
        "WATER",
        "RIVER",
        "STREAM",
        "LAKE",
        "POND",
        "RESERVOIR",
        "BAY",
        "ESTUARY",
        "OCEAN",
    ]):
        return "water"

    if any(word in combined for word in [
        "BARREN",
        "SAND",
        "BEACH",
        "EXTRACTIVE",
        "MINING",
        "QUARRY",
    ]):
        return "barren"

    return "other"


def clean_geometries(gdf, label):
    before = len(gdf)

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        gdf["geometry"] = gdf.geometry.buffer(0)

    after = len(gdf)

    log(f"{label} geometry clean: {before:,} -> {after:,}")

    return gdf


def safe_to_crs(gdf, target_crs, label):
    if gdf.crs is None:
        raise ValueError(
            f"{label} has no CRS.\n"
            "For a shapefile, make sure the .prj file is in the same folder."
        )

    log(f"{label} original CRS: {gdf.crs}")

    return gdf.to_crs(target_crs)


def export_json(df, path):
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def find_column(df, candidates):
    """
    Find the first existing column from a candidate list.
    """

    for col in candidates:
        if col in df.columns:
            return col

    return None


def main():
    ensure_dirs()

    log("========== Step 10: Land Use / Watershed Overlay ==========")

    if not WATERSHED_PATH.exists():
        raise FileNotFoundError(f"Missing watershed file:\n{WATERSHED_PATH}")

    if not WATERSHED_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Missing watershed nitrate summary:\n{WATERSHED_SUMMARY_PATH}")

    land_use_path = find_land_use_file()
    check_shapefile_sidecars(land_use_path)

    log(f"[READ] Watershed file: {WATERSHED_PATH}")
    log(f"[READ] Land use file: {land_use_path}")
    log(f"[READ] Watershed nitrate summary: {WATERSHED_SUMMARY_PATH}")

    watersheds = gpd.read_file(WATERSHED_PATH)
    land_use = gpd.read_file(land_use_path)

    log("")
    log("========== Watershed Columns ==========")
    for col in watersheds.columns:
        log(col)

    log("")
    log("========== Land Use Columns ==========")
    for col in land_use.columns:
        log(col)

    watershed_name_col = pick_watershed_name_column(watersheds)
    land_use_text_col = pick_land_use_column(land_use)
    land_use_code_col = pick_land_use_code_column(land_use)

    log("")
    log(f"Selected watershed name column: {watershed_name_col}")
    log(f"Selected land use text column: {land_use_text_col}")
    log(f"Selected land use code column: {land_use_code_col}")

    watersheds = clean_geometries(watersheds, "Watershed")
    land_use = clean_geometries(land_use, "Land use")

    watersheds = watersheds[[watershed_name_col, "geometry"]].copy()
    watersheds = watersheds.rename(columns={watershed_name_col: "watershed_name"})

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
        lambda row: classify_land_use(row["land_use_raw"], row["land_use_code"]),
        axis=1
    )

    log("")
    log("========== Land Use Group Counts ==========")
    land_use_group_counts = land_use["land_use_group"].value_counts(dropna=False)

    for group, count in land_use_group_counts.items():
        log(f"{group}: {count:,}")

    # EPSG:3424 = NAD83 / New Jersey, units in feet.
    # We convert area to square meters later.
    target_crs = "EPSG:3424"

    watersheds = safe_to_crs(watersheds, target_crs, "Watershed")
    land_use = safe_to_crs(land_use, target_crs, "Land use")

    log("")
    log("========== Spatial Overlay ==========")
    log("Running intersection overlay. This may take a while.")

    intersected = gpd.overlay(
        land_use,
        watersheds,
        how="intersection",
        keep_geom_type=False
    )

    intersected = intersected[intersected.geometry.notna()].copy()
    intersected = intersected[~intersected.geometry.is_empty].copy()

    # EPSG:3424 uses US survey feet, so geometry.area is square feet.
    # Convert square feet to square meters.
    intersected["area_sqft"] = intersected.geometry.area
    intersected["area_m2"] = intersected["area_sqft"] * 0.09290304

    log(f"Intersection rows: {len(intersected):,}")

    summary_long = (
        intersected
        .groupby(["watershed_name", "land_use_group"], as_index=False)
        .agg(area_m2=("area_m2", "sum"))
    )

    total_area = (
        summary_long
        .groupby("watershed_name", as_index=False)
        .agg(total_land_use_area_m2=("area_m2", "sum"))
    )

    summary_long = summary_long.merge(total_area, on="watershed_name", how="left")
    summary_long["percent"] = summary_long["area_m2"] / summary_long["total_land_use_area_m2"] * 100

    pivot_area = summary_long.pivot_table(
        index="watershed_name",
        columns="land_use_group",
        values="area_m2",
        aggfunc="sum",
        fill_value=0
    )

    pivot_percent = summary_long.pivot_table(
        index="watershed_name",
        columns="land_use_group",
        values="percent",
        aggfunc="sum",
        fill_value=0
    )

    pivot_area.columns = [f"{col}_area_m2" for col in pivot_area.columns]
    pivot_percent.columns = [f"{col}_percent" for col in pivot_percent.columns]

    land_use_summary = pd.concat([pivot_area, pivot_percent], axis=1).reset_index()
    land_use_summary = land_use_summary.merge(total_area, on="watershed_name", how="left")

    expected_groups = [
        "developed",
        "agriculture",
        "forest",
        "wetlands",
        "water",
        "barren",
        "other",
    ]

    for group in expected_groups:
        area_col = f"{group}_area_m2"
        percent_col = f"{group}_percent"

        if area_col not in land_use_summary.columns:
            land_use_summary[area_col] = 0.0

        if percent_col not in land_use_summary.columns:
            land_use_summary[percent_col] = 0.0

    ordered_cols = [
        "watershed_name",
        "total_land_use_area_m2",
    ]

    for group in expected_groups:
        ordered_cols.append(f"{group}_area_m2")
        ordered_cols.append(f"{group}_percent")

    land_use_summary = land_use_summary[ordered_cols].copy()

    for col in land_use_summary.columns:
        if col.endswith("_percent"):
            land_use_summary[col] = land_use_summary[col].round(2)

        if col.endswith("_area_m2") or col == "total_land_use_area_m2":
            land_use_summary[col] = land_use_summary[col].round(2)

    nitrate_summary = pd.read_csv(WATERSHED_SUMMARY_PATH)

    if "watershed_name" not in nitrate_summary.columns:
        possible_cols = [
            "WMA_NAME",
            "WMA",
            "name",
            "Name",
            "watershed",
            "watershed_id",
        ]

        found = None

        for col in possible_cols:
            if col in nitrate_summary.columns:
                found = col
                break

        if found is None:
            raise ValueError(
                "Could not find watershed name column in watershed_summary.csv.\n"
                f"Available columns: {list(nitrate_summary.columns)}"
            )

        nitrate_summary = nitrate_summary.rename(columns={found: "watershed_name"})

    joined = nitrate_summary.merge(
        land_use_summary,
        on="watershed_name",
        how="left"
    )

    mean_col = find_column(joined, [
        "mean_nitrate_mg_L",
        "mean_nitrate",
        "mean_result",
        "mean",
        "avg_nitrate",
        "avg_nitrate_mg_L",
    ])

    hotspot_rate_col = find_column(joined, [
        "hotspot_rate_percent",
        "hotspot_rate",
        "hotspot_station_rate",
        "hotspot_percent",
    ])

    high_confidence_rate_col = find_column(joined, [
        "high_confidence_rate_percent",
        "high_confidence_rate",
    ])

    station_count_col = find_column(joined, [
        "station_count",
        "stations",
        "total_stations",
    ])

    total_observations_col = find_column(joined, [
        "total_observations",
        "observation_count",
        "observations",
    ])

    log("")
    log("========== Nitrate Column Check ==========")
    log(f"Detected mean nitrate column: {mean_col}")
    log(f"Detected hotspot rate column: {hotspot_rate_col}")
    log(f"Detected high confidence rate column: {high_confidence_rate_col}")
    log(f"Detected station count column: {station_count_col}")
    log(f"Detected total observations column: {total_observations_col}")

    unmatched = joined[joined["total_land_use_area_m2"].isna()].copy()

    log("")
    log("========== Join Check ==========")
    log(f"Watersheds in nitrate summary: {len(nitrate_summary):,}")
    log(f"Watersheds in land use summary: {len(land_use_summary):,}")
    log(f"Watersheds after join: {len(joined):,}")
    log(f"Watersheds missing land use after join: {len(unmatched):,}")

    if len(unmatched) > 0:
        log("")
        log("Missing land use for these watersheds:")
        for name in unmatched["watershed_name"].tolist():
            log(name)

    land_use_summary.to_csv(OUT_LAND_USE_SUMMARY_CSV, index=False)
    joined.to_csv(OUT_JOINED_CSV, index=False)

    export_json(land_use_summary, OUT_LAND_USE_JSON)
    export_json(joined, OUT_JOINED_JSON)

    log("")
    log("========== Export Complete ==========")
    log(f"[EXPORT] {OUT_LAND_USE_SUMMARY_CSV}")
    log(f"[EXPORT] {OUT_JOINED_CSV}")
    log(f"[EXPORT] {OUT_LAND_USE_JSON}")
    log(f"[EXPORT] {OUT_JOINED_JSON}")

    log("")
    log("========== Top 10 Watersheds by Agriculture Percent ==========")

    top_agriculture = joined.sort_values("agriculture_percent", ascending=False).head(10)

    for _, row in top_agriculture.iterrows():
        line = (
            f"{row['watershed_name']} | "
            f"agriculture={row.get('agriculture_percent', None)}% | "
            f"developed={row.get('developed_percent', None)}% | "
            f"forest={row.get('forest_percent', None)}% | "
            f"wetlands={row.get('wetlands_percent', None)}% | "
            f"mean_nitrate={row.get(mean_col, None)} | "
            f"hotspot_rate={row.get(hotspot_rate_col, None)} | "
            f"high_confidence_rate={row.get(high_confidence_rate_col, None)}"
        )

        log(line)

    log("")
    log("========== Top 10 Watersheds by Developed Percent ==========")

    top_developed = joined.sort_values("developed_percent", ascending=False).head(10)

    for _, row in top_developed.iterrows():
        line = (
            f"{row['watershed_name']} | "
            f"developed={row.get('developed_percent', None)}% | "
            f"agriculture={row.get('agriculture_percent', None)}% | "
            f"forest={row.get('forest_percent', None)}% | "
            f"wetlands={row.get('wetlands_percent', None)}% | "
            f"mean_nitrate={row.get(mean_col, None)} | "
            f"hotspot_rate={row.get(hotspot_rate_col, None)} | "
            f"high_confidence_rate={row.get(high_confidence_rate_col, None)}"
        )

        log(line)

    log("")
    log("========== Top 10 Watersheds by Hotspot Rate ==========")

    if hotspot_rate_col:
        top_hotspot = joined.sort_values(hotspot_rate_col, ascending=False).head(10)

        for _, row in top_hotspot.iterrows():
            line = (
                f"{row['watershed_name']} | "
                f"hotspot_rate={row.get(hotspot_rate_col, None)} | "
                f"mean_nitrate={row.get(mean_col, None)} | "
                f"developed={row.get('developed_percent', None)}% | "
                f"agriculture={row.get('agriculture_percent', None)}% | "
                f"forest={row.get('forest_percent', None)}% | "
                f"wetlands={row.get('wetlands_percent', None)}% | "
                f"stations={row.get(station_count_col, None)} | "
                f"observations={row.get(total_observations_col, None)}"
            )

            log(line)

    log("")
    log("========== Top 10 Watersheds by Mean Nitrate ==========")

    if mean_col:
        top_mean = joined.sort_values(mean_col, ascending=False).head(10)

        for _, row in top_mean.iterrows():
            line = (
                f"{row['watershed_name']} | "
                f"mean_nitrate={row.get(mean_col, None)} | "
                f"hotspot_rate={row.get(hotspot_rate_col, None)} | "
                f"developed={row.get('developed_percent', None)}% | "
                f"agriculture={row.get('agriculture_percent', None)}% | "
                f"forest={row.get('forest_percent', None)}% | "
                f"wetlands={row.get('wetlands_percent', None)}% | "
                f"stations={row.get(station_count_col, None)} | "
                f"observations={row.get(total_observations_col, None)}"
            )

            log(line)

    log("")
    log("Step 10 finished successfully.")


if __name__ == "__main__":
    main()