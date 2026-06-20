import os
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

MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

WATERSHED_GEOJSON = os.path.join(WATERSHED_DIR, "nj_watershed_management_areas.geojson")

STATION_WATERSHED_CSV = os.path.join(PROCESSED_DIR, "station_watershed_summary.csv")
WATERSHED_SUMMARY_CSV = os.path.join(PROCESSED_DIR, "watershed_summary.csv")

COMPARISON_MAP_HTML = os.path.join(MAPS_DIR, "watershed_comparison_map.html")
LOG_FILE = os.path.join(LOG_DIR, "09_watershed_comparison_map_log.txt")

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
    required_files = [
        WATERSHED_GEOJSON,
        STATION_WATERSHED_CSV,
        WATERSHED_SUMMARY_CSV,
    ]

    for path in required_files:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required file not found:\n{path}\n\n"
                "Run these scripts first:\n"
                "python scripts/08_watershed_join.py"
            )


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


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


# ============================================================
# Color functions
# ============================================================

def hotspot_rate_color(rate):
    rate = safe_float(rate, None)

    if rate is None:
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


def mean_nitrate_color(value):
    value = safe_float(value, None)

    if value is None:
        return "#e5e7eb"

    if value >= 2.0:
        return "#581c87"

    if value >= 1.5:
        return "#7e22ce"

    if value >= 1.0:
        return "#a855f7"

    if value >= 0.5:
        return "#c4b5fd"

    return "#dbeafe"


def confidence_rate_color(rate):
    rate = safe_float(rate, None)

    if rate is None:
        return "#e5e7eb"

    if rate >= 10:
        return "#166534"

    if rate >= 5:
        return "#22c55e"

    if rate >= 1:
        return "#86efac"

    return "#fef3c7"


def station_confidence_color(level):
    if level == "High":
        return "green"

    if level == "Medium":
        return "orange"

    return "gray"


def station_radius(count):
    count = safe_int(count, 0)

    if count >= 100:
        return 8

    if count >= 30:
        return 6

    if count >= 10:
        return 4

    return 3


# ============================================================
# Main map creation
# ============================================================

def create_comparison_map():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 9C: Watershed Comparison Map ==========")

    check_input_files()

    write_log(f"[READ] Watershed GeoJSON: {WATERSHED_GEOJSON}")
    watershed_gdf = gpd.read_file(WATERSHED_GEOJSON)

    write_log(f"[READ] Station watershed CSV: {STATION_WATERSHED_CSV}")
    station_df = pd.read_csv(STATION_WATERSHED_CSV, low_memory=False)

    write_log(f"[READ] Watershed summary CSV: {WATERSHED_SUMMARY_CSV}")
    watershed_summary = pd.read_csv(WATERSHED_SUMMARY_CSV, low_memory=False)

    write_log(f"Watershed polygons: {len(watershed_gdf):,}")
    write_log(f"Station watershed rows: {len(station_df):,}")
    write_log(f"Watershed summary rows: {len(watershed_summary):,}")

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
        watershed_gdf["watershed_name"] = watershed_gdf["watershed_name"].replace("", "Unknown Watershed")
        watershed_gdf["watershed_name"] = watershed_gdf["watershed_name"].replace(" ", "Unknown Watershed")

    watershed_summary["watershed_join_id"] = watershed_summary["watershed_join_id"].astype(str)

    map_gdf = watershed_gdf.merge(
        watershed_summary,
        on=["watershed_join_id", "watershed_name"],
        how="left"
    )

    # ------------------------------------------------------------
    # Prepare station data
    # ------------------------------------------------------------

    station_df["latitude"] = pd.to_numeric(station_df["latitude"], errors="coerce")
    station_df["longitude"] = pd.to_numeric(station_df["longitude"], errors="coerce")
    station_df["mean_nitrate_mg_L"] = pd.to_numeric(station_df["mean_nitrate_mg_L"], errors="coerce")
    station_df["p90_nitrate_mg_L"] = pd.to_numeric(station_df["p90_nitrate_mg_L"], errors="coerce")
    station_df["observation_count"] = pd.to_numeric(station_df["observation_count"], errors="coerce")

    station_df = station_df[
        station_df["latitude"].notna()
        & station_df["longitude"].notna()
    ].copy()

    center_lat = station_df["latitude"].median()
    center_lon = station_df["longitude"].median()

    # ------------------------------------------------------------
    # Base map
    # ------------------------------------------------------------

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles="CartoDB positron"
    )

    # ------------------------------------------------------------
    # Layer 1: Hotspot rate
    # ------------------------------------------------------------

    hotspot_layer = folium.FeatureGroup(
        name="Watershed Hotspot Rate",
        show=True
    )

    def hotspot_style(feature):
        rate = feature["properties"].get("hotspot_rate_percent", None)

        return {
            "fillColor": hotspot_rate_color(rate),
            "color": "#334155",
            "weight": 1,
            "fillOpacity": 0.58,
        }

    folium.GeoJson(
        map_gdf,
        name="Watershed Hotspot Rate",
        style_function=hotspot_style,
        highlight_function=lambda feature: {
            "fillColor": "#38bdf8",
            "color": "#0f172a",
            "weight": 3,
            "fillOpacity": 0.70,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "watershed_name",
                "station_count",
                "hotspot_station_count",
                "hotspot_rate_percent",
                "mean_nitrate_mg_L",
                "high_confidence_rate_percent",
            ],
            aliases=[
                "Watershed",
                "Stations",
                "Hotspot Stations",
                "Hotspot Rate (%)",
                "Mean Nitrate (mg/L)",
                "High Confidence Rate (%)",
            ],
            localize=True,
            sticky=False,
        )
    ).add_to(hotspot_layer)

    hotspot_layer.add_to(m)

    # ------------------------------------------------------------
    # Layer 2: Mean nitrate
    # ------------------------------------------------------------

    mean_layer = folium.FeatureGroup(
        name="Watershed Mean Nitrate",
        show=False
    )

    def mean_style(feature):
        value = feature["properties"].get("mean_nitrate_mg_L", None)

        return {
            "fillColor": mean_nitrate_color(value),
            "color": "#334155",
            "weight": 1,
            "fillOpacity": 0.58,
        }

    folium.GeoJson(
        map_gdf,
        name="Watershed Mean Nitrate",
        style_function=mean_style,
        highlight_function=lambda feature: {
            "fillColor": "#38bdf8",
            "color": "#0f172a",
            "weight": 3,
            "fillOpacity": 0.70,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "watershed_name",
                "mean_nitrate_mg_L",
                "median_station_mean_nitrate_mg_L",
                "mean_p90_nitrate_mg_L",
                "max_station_nitrate_mg_L",
                "total_observations",
            ],
            aliases=[
                "Watershed",
                "Mean Nitrate (mg/L)",
                "Median Station Mean",
                "Mean P90 Nitrate",
                "Max Station Nitrate",
                "Total Observations",
            ],
            localize=True,
            sticky=False,
        )
    ).add_to(mean_layer)

    mean_layer.add_to(m)

    # ------------------------------------------------------------
    # Layer 3: High confidence rate
    # ------------------------------------------------------------

    confidence_layer = folium.FeatureGroup(
        name="Watershed High-Confidence Coverage",
        show=False
    )

    def confidence_style(feature):
        rate = feature["properties"].get("high_confidence_rate_percent", None)

        return {
            "fillColor": confidence_rate_color(rate),
            "color": "#334155",
            "weight": 1,
            "fillOpacity": 0.58,
        }

    folium.GeoJson(
        map_gdf,
        name="Watershed High-Confidence Coverage",
        style_function=confidence_style,
        highlight_function=lambda feature: {
            "fillColor": "#38bdf8",
            "color": "#0f172a",
            "weight": 3,
            "fillOpacity": 0.70,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "watershed_name",
                "station_count",
                "high_confidence_stations",
                "medium_confidence_stations",
                "low_confidence_stations",
                "high_confidence_rate_percent",
            ],
            aliases=[
                "Watershed",
                "Stations",
                "High Confidence Stations",
                "Medium Confidence Stations",
                "Low Confidence Stations",
                "High Confidence Rate (%)",
            ],
            localize=True,
            sticky=False,
        )
    ).add_to(confidence_layer)

    confidence_layer.add_to(m)

    # ------------------------------------------------------------
    # Layer 4: Hotspot station points
    # ------------------------------------------------------------

    hotspot_points_layer = folium.FeatureGroup(
        name="Hotspot Station Points",
        show=True
    )

    hotspot_station_df = station_df[station_df["is_hotspot"] == True].copy()

    for _, row in hotspot_station_df.iterrows():
        popup_html = f"""
        <div style="font-family: Arial; width: 300px;">
            <h4>{row.get("station_id", "Unknown Station")}</h4>
            <b>Station Name:</b> {row.get("station_name", "")}<br>
            <b>Watershed:</b> {row.get("watershed_name", "Unmatched")}<br>
            <b>Observation Count:</b> {safe_int(row.get("observation_count", 0))}<br>
            <b>Confidence:</b> {row.get("confidence_level", "Unknown")}<br>
            <b>Mean Nitrate:</b> {safe_float(row.get("mean_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>P90 Nitrate:</b> {safe_float(row.get("p90_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>Max Nitrate:</b> {safe_float(row.get("max_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>Hotspot:</b> True<br>
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=station_radius(row.get("observation_count", 0)),
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.75,
            weight=1.5,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"Hotspot | {row.get('station_id', '')}"
        ).add_to(hotspot_points_layer)

    hotspot_points_layer.add_to(m)

    # ------------------------------------------------------------
    # Layer 5: Confidence station points
    # ------------------------------------------------------------

    confidence_points_layer = folium.FeatureGroup(
        name="All Station Points by Confidence",
        show=False
    )

    for _, row in station_df.iterrows():
        color = station_confidence_color(row.get("confidence_level", "Low"))

        popup_html = f"""
        <div style="font-family: Arial; width: 300px;">
            <h4>{row.get("station_id", "Unknown Station")}</h4>
            <b>Station Name:</b> {row.get("station_name", "")}<br>
            <b>Watershed:</b> {row.get("watershed_name", "Unmatched")}<br>
            <b>Observation Count:</b> {safe_int(row.get("observation_count", 0))}<br>
            <b>Confidence:</b> {row.get("confidence_level", "Unknown")}<br>
            <b>Mean Nitrate:</b> {safe_float(row.get("mean_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>P90 Nitrate:</b> {safe_float(row.get("p90_nitrate_mg_L", 0)):.4f} mg/L<br>
            <b>Hotspot:</b> {bool(row.get("is_hotspot", False))}<br>
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=station_radius(row.get("observation_count", 0)),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.60,
            weight=1.2,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{row.get('confidence_level', 'Unknown')} confidence | {row.get('station_id', '')}"
        ).add_to(confidence_points_layer)

    confidence_points_layer.add_to(m)

    # ------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------

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
        width: 330px;
        max-height: 520px;
        overflow-y: auto;
    ">
        <b>Watershed Comparison Map</b><br><br>

        <b>Hotspot Rate Layer</b><br>
        <span style="color:#7f1d1d;">●</span> ≥ 30% hotspot stations<br>
        <span style="color:#dc2626;">●</span> 20–30%<br>
        <span style="color:#f97316;">●</span> 10–20%<br>
        <span style="color:#facc15;">●</span> 5–10%<br>
        <span style="color:#bfdbfe;">●</span> &lt; 5%<br><br>

        <b>Mean Nitrate Layer</b><br>
        <span style="color:#581c87;">●</span> ≥ 2.0 mg/L<br>
        <span style="color:#7e22ce;">●</span> 1.5–2.0 mg/L<br>
        <span style="color:#a855f7;">●</span> 1.0–1.5 mg/L<br>
        <span style="color:#c4b5fd;">●</span> 0.5–1.0 mg/L<br>
        <span style="color:#dbeafe;">●</span> &lt; 0.5 mg/L<br><br>

        <b>High-Confidence Coverage</b><br>
        <span style="color:#166534;">●</span> ≥ 10% high-confidence stations<br>
        <span style="color:#22c55e;">●</span> 5–10%<br>
        <span style="color:#86efac;">●</span> 1–5%<br>
        <span style="color:#fef3c7;">●</span> &lt; 1%<br><br>

        <b>Station Points</b><br>
        <span style="color:red;">●</span> Hotspot station<br>
        <span style="color:green;">●</span> High confidence station<br>
        <span style="color:orange;">●</span> Medium confidence station<br>
        <span style="color:gray;">●</span> Low confidence station<br>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(COMPARISON_MAP_HTML)

    # ------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------

    write_log("")
    write_log("========== Comparison Map Summary ==========")
    write_log(f"Watershed polygons: {len(map_gdf):,}")
    write_log(f"Station points: {len(station_df):,}")
    write_log(f"Hotspot station points: {len(hotspot_station_df):,}")

    write_log("")
    write_log("========== Top 5 Watersheds by Hotspot Rate ==========")

    top5 = watershed_summary.sort_values(
        by=["hotspot_rate_percent", "hotspot_station_count", "mean_nitrate_mg_L"],
        ascending=[False, False, False]
    ).head(5)

    for _, row in top5.iterrows():
        write_log(
            f"{row['watershed_name']} | "
            f"hotspot_rate={safe_float(row['hotspot_rate_percent']):.2f}% | "
            f"hotspots={safe_int(row['hotspot_station_count'])} | "
            f"stations={safe_int(row['station_count'])} | "
            f"mean_nitrate={safe_float(row['mean_nitrate_mg_L']):.4f} mg/L | "
            f"high_confidence_rate={safe_float(row['high_confidence_rate_percent']):.2f}%"
        )

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Comparison map HTML: {COMPARISON_MAP_HTML}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 9C Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    create_comparison_map()


if __name__ == "__main__":
    main()