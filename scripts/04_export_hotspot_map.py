import os
import json
import math
import pandas as pd
import folium
from folium.plugins import MarkerCluster


# ============================================================
# Project paths
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

INPUT_CSV = os.path.join(DATA_DIR, "processed", "station_summary.csv")

DASHBOARD_DIR = os.path.join(OUTPUT_DIR, "dashboard")
MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

MAP_POINTS_JSON = os.path.join(DASHBOARD_DIR, "map_points.json")
HOTSPOT_POINTS_JSON = os.path.join(DASHBOARD_DIR, "hotspot_points.json")
SUMMARY_CARDS_JSON = os.path.join(DASHBOARD_DIR, "summary_cards.json")
WEBSITE_TABLE_CSV = os.path.join(TABLES_DIR, "station_summary_for_website.csv")
MAP_HTML = os.path.join(MAPS_DIR, "nitrate_hotspot_map.html")
LOG_FILE = os.path.join(LOG_DIR, "04_export_hotspot_map_log.txt")

os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(MAPS_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)
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
            "Run Step 3 first:\n"
            "python scripts/03_station_summary.py"
        )


def clean_for_json(value):
    if pd.isna(value):
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    if isinstance(value, bool):
        return bool(value)

    return value


def nitrate_level(row):
    mean_value = row["mean_nitrate_mg_L"]
    p90_value = row["p90_nitrate_mg_L"]

    if p90_value >= 10 or mean_value >= 10:
        return "Very High"
    if p90_value >= 5 or mean_value >= 5:
        return "High"
    if p90_value >= 2.1337 or mean_value >= 1.6947:
        return "Elevated"
    return "Normal"


def marker_color(level, confidence):
    if confidence == "Low" and level in ["Very High", "High", "Elevated"]:
        return "gray"

    if level == "Very High":
        return "darkred"
    if level == "High":
        return "red"
    if level == "Elevated":
        return "orange"

    return "blue"


def marker_radius(count):
    if pd.isna(count):
        return 4

    count = int(count)

    if count >= 100:
        return 10
    if count >= 30:
        return 8
    if count >= 10:
        return 6

    return 4


def confidence_warning(confidence):
    if confidence == "High":
        return "High confidence: 100 or more observations"
    if confidence == "Medium":
        return "Medium confidence: 30 to 99 observations"
    return "Low confidence: fewer than 30 observations"


def create_popup_html(row):
    station_name = clean_for_json(row.get("station_name", "Unknown"))
    station_id = clean_for_json(row.get("station_id", "Unknown"))

    html = f"""
    <div style="font-family: Arial; width: 280px;">
        <h4 style="margin-bottom: 6px;">{station_name}</h4>
        <b>Station ID:</b> {station_id}<br>
        <b>Observation Count:</b> {int(row["observation_count"])}<br>
        <b>Confidence:</b> {row["confidence_level"]}<br>
        <b>Mean Nitrate:</b> {row["mean_nitrate_mg_L"]:.4f} mg/L<br>
        <b>Median Nitrate:</b> {row["median_nitrate_mg_L"]:.4f} mg/L<br>
        <b>P90 Nitrate:</b> {row["p90_nitrate_mg_L"]:.4f} mg/L<br>
        <b>Max Nitrate:</b> {row["max_nitrate_mg_L"]:.4f} mg/L<br>
        <b>Years:</b> {int(row["first_year"])}–{int(row["last_year"])}<br>
        <b>Hotspot:</b> {bool(row["is_hotspot"])}<br>
        <br>
        <i>{confidence_warning(row["confidence_level"])}</i>
    </div>
    """

    return html


# ============================================================
# JSON export
# ============================================================

def export_json_files(df):
    map_points = []

    for _, row in df.iterrows():
        level = nitrate_level(row)

        item = {
            "station_id": clean_for_json(row["station_id"]),
            "station_name": clean_for_json(row["station_name"]),
            "latitude": clean_for_json(row["latitude"]),
            "longitude": clean_for_json(row["longitude"]),
            "observation_count": int(row["observation_count"]),
            "mean_nitrate_mg_L": clean_for_json(row["mean_nitrate_mg_L"]),
            "median_nitrate_mg_L": clean_for_json(row["median_nitrate_mg_L"]),
            "p90_nitrate_mg_L": clean_for_json(row["p90_nitrate_mg_L"]),
            "max_nitrate_mg_L": clean_for_json(row["max_nitrate_mg_L"]),
            "first_year": int(row["first_year"]),
            "last_year": int(row["last_year"]),
            "confidence_level": clean_for_json(row["confidence_level"]),
            "confidence_score": clean_for_json(row["confidence_score"]),
            "is_hotspot": bool(row["is_hotspot"]),
            "nitrate_level": level,
            "provider": clean_for_json(row["provider"]),
            "nitrate_categories": clean_for_json(row["nitrate_categories"]),
            "units_seen": clean_for_json(row["units_seen"]),
        }

        map_points.append(item)

    hotspot_points = [item for item in map_points if item["is_hotspot"]]

    summary_cards = {
        "total_stations": int(len(df)),
        "hotspot_stations": int(df["is_hotspot"].sum()),
        "high_confidence_stations": int((df["confidence_level"] == "High").sum()),
        "medium_confidence_stations": int((df["confidence_level"] == "Medium").sum()),
        "low_confidence_stations": int((df["confidence_level"] == "Low").sum()),
        "mean_nitrate_all_stations": clean_for_json(df["mean_nitrate_mg_L"].mean()),
        "median_nitrate_all_stations": clean_for_json(df["median_nitrate_mg_L"].median()),
        "max_nitrate_all_stations": clean_for_json(df["max_nitrate_mg_L"].max()),
        "highest_p90_station": clean_for_json(df.iloc[0]["station_id"]) if len(df) > 0 else None,
        "note": (
            "Hotspots are based on top 10% station-level mean or p90 nitrate values. "
            "Low-confidence hotspots should be interpreted carefully."
        ),
    }

    with open(MAP_POINTS_JSON, "w", encoding="utf-8") as f:
        json.dump(map_points, f, indent=2)

    with open(HOTSPOT_POINTS_JSON, "w", encoding="utf-8") as f:
        json.dump(hotspot_points, f, indent=2)

    with open(SUMMARY_CARDS_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_cards, f, indent=2)

    write_log(f"[OK] Map points JSON saved: {MAP_POINTS_JSON}")
    write_log(f"[OK] Hotspot points JSON saved: {HOTSPOT_POINTS_JSON}")
    write_log(f"[OK] Summary cards JSON saved: {SUMMARY_CARDS_JSON}")


# ============================================================
# Map export
# ============================================================

def create_map(df):
    center_lat = df["latitude"].median()
    center_lon = df["longitude"].median()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles=None
    )

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB positron",
        name="Light Map",
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="Dark Map",
        control=True
    ).add_to(m)

    all_layer = folium.FeatureGroup(name="All nitrate stations", show=True)
    hotspot_layer = folium.FeatureGroup(name="Hotspot stations only", show=True)
    high_conf_layer = folium.FeatureGroup(name="High confidence stations", show=False)
    low_conf_hotspot_layer = folium.FeatureGroup(name="Low-confidence hotspots", show=False)

    for _, row in df.iterrows():
        level = nitrate_level(row)
        color = marker_color(level, row["confidence_level"])
        radius = marker_radius(row["observation_count"])
        popup_html = create_popup_html(row)

        marker = folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=2,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{row['station_id']} | {level} | {row['confidence_level']}"
        )

        marker.add_to(all_layer)

        if row["is_hotspot"]:
            hotspot_marker = folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=radius + 2,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                weight=3,
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"HOTSPOT | {row['station_id']} | {row['confidence_level']}"
            )
            hotspot_marker.add_to(hotspot_layer)

        if row["confidence_level"] == "High":
            high_conf_marker = folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                weight=2,
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"HIGH CONFIDENCE | {row['station_id']}"
            )
            high_conf_marker.add_to(high_conf_layer)

        if row["is_hotspot"] and row["confidence_level"] == "Low":
            low_conf_marker = folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=radius + 1,
                color="gray",
                fill=True,
                fill_color="gray",
                fill_opacity=0.60,
                weight=2,
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"LOW CONFIDENCE HOTSPOT | {row['station_id']}"
            )
            low_conf_marker.add_to(low_conf_hotspot_layer)

    all_layer.add_to(m)
    hotspot_layer.add_to(m)
    high_conf_layer.add_to(m)
    low_conf_hotspot_layer.add_to(m)

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
        width: 260px;
    ">
        <b>Nitrate Station Map</b><br><br>
        <span style="color:darkred;">●</span> Very High<br>
        <span style="color:red;">●</span> High<br>
        <span style="color:orange;">●</span> Elevated<br>
        <span style="color:blue;">●</span> Normal<br>
        <span style="color:gray;">●</span> Low-confidence hotspot<br>
        <br>
        <b>Circle size:</b> observation count<br>
        <b>Confidence:</b><br>
        High ≥ 100 observations<br>
        Medium = 30–99 observations<br>
        Low &lt; 30 observations<br>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(MAP_HTML)

    write_log(f"[OK] Interactive map saved: {MAP_HTML}")


# ============================================================
# Main pipeline
# ============================================================

def export_hotspot_map():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    write_log("========== Step 4: Export Hotspot Map ==========")

    check_input_file()

    write_log(f"[READ] {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV, low_memory=False)

    write_log(f"Input stations: {len(df):,}")

    before_location_filter = len(df)

    df = df[
        df["latitude"].notna()
        & df["longitude"].notna()
        & df["mean_nitrate_mg_L"].notna()
        & df["p90_nitrate_mg_L"].notna()
    ].copy()

    after_location_filter = len(df)

    df["nitrate_level"] = df.apply(nitrate_level, axis=1)

    df.to_csv(WEBSITE_TABLE_CSV, index=False, encoding="utf-8")

    export_json_files(df)
    create_map(df)

    write_log("")
    write_log("========== Export Summary ==========")
    write_log(f"Stations before filter: {before_location_filter:,}")
    write_log(f"Stations after filter: {after_location_filter:,}")
    write_log(f"Hotspot stations: {int(df['is_hotspot'].sum()):,}")
    write_log(f"High confidence stations: {int((df['confidence_level'] == 'High').sum()):,}")
    write_log(f"Medium confidence stations: {int((df['confidence_level'] == 'Medium').sum()):,}")
    write_log(f"Low confidence stations: {int((df['confidence_level'] == 'Low').sum()):,}")

    write_log("")
    write_log("========== Nitrate Level Counts ==========")
    counts = df["nitrate_level"].value_counts()
    for level, count in counts.items():
        write_log(f"{level}: {count:,}")

    write_log("")
    write_log("========== Output ==========")
    write_log(f"Map points JSON: {MAP_POINTS_JSON}")
    write_log(f"Hotspot points JSON: {HOTSPOT_POINTS_JSON}")
    write_log(f"Summary cards JSON: {SUMMARY_CARDS_JSON}")
    write_log(f"Website table CSV: {WEBSITE_TABLE_CSV}")
    write_log(f"Interactive map HTML: {MAP_HTML}")
    write_log(f"Log file: {LOG_FILE}")

    write_log("")
    write_log("========== Step 4 Finished ==========")


# ============================================================
# Main
# ============================================================

def main():
    export_hotspot_map()


if __name__ == "__main__":
    main()