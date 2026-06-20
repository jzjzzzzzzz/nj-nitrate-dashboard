import os
import json
import math
import pandas as pd
import geopandas as gpd
import folium


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
EXTERNAL_DIR = os.path.join(DATA_DIR, "external")
WATERSHED_DIR = os.path.join(EXTERNAL_DIR, "watershed")

DASHBOARD_DIR = os.path.join(OUTPUT_DIR, "dashboard")
MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

STATION_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "station_summary.csv")

# Change this filename if your downloaded GeoJSON has a different name.
WATERSHED_GEOJSON = os.path.join(WATERSHED_DIR, "nj_watershed_management_areas.geojson")

STATION_WATERSHED_CSV = os.path.join(PROCESSED_DIR, "station_watershed_summary.csv")
WATERSHED_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "watershed_summary.csv")

WATERSHED_SUMMARY_JSON = os.path.join(DASHBOARD_DIR, "watershed_summary.json")
WATERSHED_MAP_HTML = os.path.join(MAPS_DIR, "watershed_hotspot_map.html")

LOG_FILE = os.path.join(LOG_DIR, "08_watershed_join_log.txt")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(MAPS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# Helper functions
# ============================================================

def write_log(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def check_input_files():
    if not os.path.exists(STATION_SUMMARY_CSV):
        raise FileNotFoundError(
            f"Station summary file not found:\n{STATION_SUMMARY_CSV}\n\n"
            "Run Step 3 first:\n"
            "python scripts/03_station_summary.py"
        )

    if not os.path.exists(WATERSHED_GEOJSON):
        raise FileNotFoundError(
            f"Watershed GeoJSON file not found:\n{WATERSHED_GEOJSON}\n\n"
            "Put your downloaded watershed GeoJSON into:\n"
            f"{WATERSHED_DIR}\n\n"
            "Recommended filename:\n"
            "nj_watershed_management_areas.geojson"
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


def find_name_column(gdf):
    possible_names = [
        "WMA_NAME",
        "WMA",
        "NAME",
        "Name",
        "name",
        "WATERSHED",
        "Watershed",
        "watershed",
        "HUC_NAME",
        "HU_NAME",
        "GNIS_NAME",
        "LABEL",
        "Label",
        "AREA_NAME",
    ]

    for col in possible_names:
        if col in gdf.columns:
            return col

    non_geometry_cols = [col for col in gdf.columns if col != "geometry"]

    if len(non_geometry_cols) > 0:
        return non_geometry_cols[0]

    return None


def hotspot_rate_color(rate):
    if pd.isna(rate):
        return "#e5e7eb"

    if rate >= 30:
        return "#7f1d1d"

    if rate >= 20:
        return "#dc2626"

    if rate >= 10:
        return "#f97316"

    if rate >= 5:
        return "#facc15"

    return "#bfdbfe"


def confidence_color(level):
    if level == "High":
        return "green"

    if level == "Medium":
        return "orange"

    return "gray"


def station_marker_radius(count):
    if pd.isna(count):
        return 4

    count = int(count)

    if count >= 100:
        return 9

    if count >= 30:
        return 7

    if count >= 10:
        return 5

    return 3


# ============================================================
# Main watershed join
# ============================================================

def watershed_join():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 8: Watershed Spatial Join ==========")

    check_input_files()

    # ------------------------------------------------------------
    # Read data
    # ------------------------------------------------------------

    write_log(f"[READ] Station summary: {STATION_SUMMARY_CSV}")
    station_df = pd.read_csv(STATION_SUMMARY_CSV, low_memory=False)

    write_log(f"[READ] Watershed GeoJSON: {WATERSHED_GEOJSON}")
    watershed_gdf = gpd.read_file(WATERSHED_GEOJSON)

    write_log(f"Station rows before filter: {len(station_df):,}")
    write_log(f"Watershed polygons: {len(watershed_gdf):,}")

    write_log("")
    write_log("========== Watershed Columns ==========")
    for col in watershed_gdf.columns:
        write_log(str(col))

    # ------------------------------------------------------------
    # Clean station data
    # ------------------------------------------------------------

    station_df = station_df[
        station_df["latitude"].notna()
        & station_df["longitude"].notna()
        & station_df["station_id"].notna()
        & station_df["mean_nitrate_mg_L"].notna()
        & station_df["p90_nitrate_mg_L"].notna()
    ].copy()

    station_df["latitude"] = pd.to_numeric(station_df["latitude"], errors="coerce")
    station_df["longitude"] = pd.to_numeric(station_df["longitude"], errors="coerce")

    station_df = station_df[
        station_df["latitude"].notna()
        & station_df["longitude"].notna()
    ].copy()

    write_log("")
    write_log("========== Station Filter ==========")
    write_log(f"Station rows after coordinate filter: {len(station_df):,}")

    # ------------------------------------------------------------
    # Prepare watershed GeoDataFrame
    # ------------------------------------------------------------

    if watershed_gdf.crs is None:
        write_log("[WARNING] Watershed GeoJSON has no CRS. Assuming EPSG:4326.")
        watershed_gdf = watershed_gdf.set_crs(epsg=4326)

    watershed_gdf = watershed_gdf.to_crs(epsg=4326)

    watershed_gdf = watershed_gdf.reset_index(drop=True)
    watershed_gdf["watershed_join_id"] = watershed_gdf.index.astype(str)

    name_col = find_name_column(watershed_gdf)

    if name_col is None:
        watershed_gdf["watershed_name"] = "Unknown Watershed"
    else:
        watershed_gdf["watershed_name"] = watershed_gdf[name_col].astype(str)

    write_log("")
    write_log("========== Watershed Name Column ==========")
    write_log(f"Selected watershed name column: {name_col}")

    # ------------------------------------------------------------
    # Convert stations to GeoDataFrame
    # ------------------------------------------------------------

    station_gdf = gpd.GeoDataFrame(
        station_df,
        geometry=gpd.points_from_xy(station_df["longitude"], station_df["latitude"]),
        crs="EPSG:4326"
    )

    # ------------------------------------------------------------
    # Spatial join
    # ------------------------------------------------------------

    write_log("")
    write_log("========== Spatial Join ==========")

    joined = gpd.sjoin(
        station_gdf,
        watershed_gdf[["watershed_join_id", "watershed_name", "geometry"]],
        how="left",
        predicate="within"
    )

    matched = joined["watershed_join_id"].notna().sum()
    unmatched = joined["watershed_join_id"].isna().sum()

    write_log(f"Stations matched to watershed: {matched:,}")
    write_log(f"Stations not matched to watershed: {unmatched:,}")

    joined_df = pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))

    joined_df.to_csv(STATION_WATERSHED_CSV, index=False, encoding="utf-8")

    # ------------------------------------------------------------
    # Watershed-level summary
    # ------------------------------------------------------------

    matched_df = joined_df[joined_df["watershed_join_id"].notna()].copy()

    watershed_summary = matched_df.groupby(["watershed_join_id", "watershed_name"]).agg(
        station_count=("station_id", "count"),
        hotspot_station_count=("is_hotspot", "sum"),
        high_confidence_stations=("confidence_level", lambda x: (x == "High").sum()),
        medium_confidence_stations=("confidence_level", lambda x: (x == "Medium").sum()),
        low_confidence_stations=("confidence_level", lambda x: (x == "Low").sum()),
        mean_nitrate_mg_L=("mean_nitrate_mg_L", "mean"),
        median_station_mean_nitrate_mg_L=("mean_nitrate_mg_L", "median"),
        mean_p90_nitrate_mg_L=("p90_nitrate_mg_L", "mean"),
        max_station_nitrate_mg_L=("max_nitrate_mg_L", "max"),
        total_observations=("observation_count", "sum"),
    ).reset_index()

    watershed_summary["hotspot_rate_percent"] = (
        watershed_summary["hotspot_station_count"]
        / watershed_summary["station_count"]
        * 100
    )

    watershed_summary["high_confidence_rate_percent"] = (
        watershed_summary["high_confidence_stations"]
        / watershed_summary["station_count"]
        * 100
    )

    watershed_summary = watershed_summary.sort_values(
        by=["hotspot_rate_percent", "hotspot_station_count", "mean_nitrate_mg_L"],
        ascending=[False, False, False]
    )

    watershed_summary.to_csv(WATERSHED_SUMMARY_CSV, index=False, encoding="utf-8")

    with open(WATERSHED_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(df_to_json_records(watershed_summary), f, indent=2)

    # ------------------------------------------------------------
    # Create watershed map
    # ------------------------------------------------------------

    map_gdf = watershed_gdf.merge(
        watershed_summary,
        on=["watershed_join_id", "watershed_name"],
        how="left"
    )

    center_lat = station_df["latitude"].median()
    center_lon = station_df["longitude"].median()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles="CartoDB positron"
    )

    def style_function(feature):
        rate = feature["properties"].get("hotspot_rate_percent", None)

        if rate is None:
            color = "#e5e7eb"
        else:
            color = hotspot_rate_color(rate)

        return {
            "fillColor": color,
            "color": "#334155",
            "weight": 1,
            "fillOpacity": 0.55,
        }

    def highlight_function(feature):
        return {
            "fillColor": "#38bdf8",
            "color": "#0f172a",
            "weight": 3,
            "fillOpacity": 0.70,
        }

    folium.GeoJson(
        map_gdf,
        name="Watershed hotspot rate",
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "watershed_name",
                "station_count",
                "hotspot_station_count",
                "hotspot_rate_percent",
                "mean_nitrate_mg_L",
                "total_observations",
            ],
            aliases=[
                "Watershed",
                "Stations",
                "Hotspot Stations",
                "Hotspot Rate (%)",
                "Mean Nitrate (mg/L)",
                "Total Observations",
            ],
            localize=True,
            sticky=False,
        )
    ).add_to(m)

    station_layer = folium.FeatureGroup(name="Station points", show=True)

    for _, row in joined_df.iterrows():
        color = confidence_color(row.get("confidence_level", "Low"))

        if bool(row.get("is_hotspot", False)):
            color = "red"

        radius = station_marker_radius(row.get("observation_count", 0))

        popup_html = f"""
        <div style="font-family: Arial; width: 280px;">
            <h4>{row.get("station_id", "Unknown Station")}</h4>
            <b>Station Name:</b> {row.get("station_name", "")}<br>
            <b>Watershed:</b> {row.get("watershed_name", "Unmatched")}<br>
            <b>Observation Count:</b> {int(row.get("observation_count", 0))}<br>
            <b>Confidence:</b> {row.get("confidence_level", "Unknown")}<br>
            <b>Mean Nitrate:</b> {float(row.get("mean_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>P90 Nitrate:</b> {float(row.get("p90_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>Hotspot:</b> {bool(row.get("is_hotspot", False))}<br>
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=1.5,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{row.get('station_id', '')} | {row.get('watershed_name', 'Unmatched')}"
        ).add_to(station_layer)

    station_layer.add_to(m)

    legend_html = """
    <div style="
        position: fixed;
        bottom: 35px;
        left: 35px;
        z-index: 9999;
        background: white;
        padding: 12px;
        border: 2px solid #999;
        border-radius: 8px;
        font-family: Arial;
        font-size: 13px;
        width: 280px;
    ">
        <b>Watershed Hotspot Rate</b><br><br>
        <span style="color:#7f1d1d;">●</span> ≥ 30% hotspot stations<br>
        <span style="color:#dc2626;">●</span> 20–30%<br>
        <span style="color:#f97316;">●</span> 10–20%<br>
        <span style="color:#facc15;">●</span> 5–10%<br>
        <span style="color:#bfdbfe;">●</span> &lt; 5%<br>
        <span style="color:#e5e7eb;">●</span> No matched stations<br>
        <br>
        <b>Station Points</b><br>
        <span style="color:red;">●</span> Hotspot station<br>
        <span style="color:green;">●</span> High confidence<br>
        <span style="color:orange;">●</span> Medium confidence<br>
        <span style="color:gray;">●</span> Low confidence<br>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(WATERSHED_MAP_HTML)

    # ------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------

    write_log("")
    write_log("========== Watershed Summary ==========")
    write_log(f"Watersheds with matched stations: {len(watershed_summary):,}")
    write_log(f"Station-watershed file saved: {STATION_WATERSHED_CSV}")
    write_log(f"Watershed summary saved: {WATERSHED_SUMMARY_CSV}")
    write_log(f"Watershed summary JSON saved: {WATERSHED_SUMMARY_JSON}")
    write_log(f"Watershed map saved: {WATERSHED_MAP_HTML}")

    write_log("")
    write_log("========== Top 15 Watersheds by Hotspot Rate ==========")

    top15 = watershed_summary.head(15)

    for _, row in top15.iterrows():
        write_log(
            f"{row['watershed_name']} | "
            f"stations={int(row['station_count'])} | "
            f"hotspots={int(row['hotspot_station_count'])} | "
            f"hotspot_rate={row['hotspot_rate_percent']:.2f}% | "
            f"mean_nitrate={row['mean_nitrate_mg_L']:.4f} mg/L | "
            f"observations={int(row['total_observations'])}"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Station watershed CSV: {STATION_WATERSHED_CSV}")
    write_log(f"Watershed summary CSV: {WATERSHED_SUMMARY_CSV}")
    write_log(f"Watershed summary JSON: {WATERSHED_SUMMARY_JSON}")
    write_log(f"Watershed map HTML: {WATERSHED_MAP_HTML}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 8 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    watershed_join()


if __name__ == "__main__":
    main()