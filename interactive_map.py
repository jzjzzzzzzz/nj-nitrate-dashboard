import os
import pandas as pd
import folium


DATA_DIR = "data"
OUTPUT_DIR = "output"

STATION_FILE = os.path.join(DATA_DIR, "station.csv")
RESULT_FILE = os.path.join(DATA_DIR, "resultphyschem.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(text):
    return str(text).replace("/", "_").replace("\\", "_").replace(":", "_")


def load_and_clean_data():
    station = pd.read_csv(STATION_FILE, low_memory=False)
    result = pd.read_csv(RESULT_FILE, low_memory=False)

    station_clean = station[
        [
            "MonitoringLocationIdentifier",
            "MonitoringLocationName",
            "MonitoringLocationTypeName",
            "LatitudeMeasure",
            "LongitudeMeasure"
        ]
    ].copy()

    result_clean = result[
        [
            "MonitoringLocationIdentifier",
            "MonitoringLocationName",
            "ActivityStartDate",
            "CharacteristicName",
            "ResultMeasureValue",
            "ResultMeasure/MeasureUnitCode"
        ]
    ].copy()

    result_clean["ActivityStartDate"] = pd.to_datetime(
        result_clean["ActivityStartDate"],
        errors="coerce"
    )

    result_clean["ResultMeasureValue"] = pd.to_numeric(
        result_clean["ResultMeasureValue"],
        errors="coerce"
    )

    result_clean = result_clean.dropna(
        subset=["ActivityStartDate", "ResultMeasureValue"]
    )

    df = result_clean.merge(
        station_clean,
        on="MonitoringLocationIdentifier",
        how="left",
        suffixes=("_result", "_station")
    )

    return df


def get_nitrate_station_summary(df):
    nitrate = df[df["CharacteristicName"] == "Nitrate"].copy()

    summary = nitrate.groupby("MonitoringLocationIdentifier").agg(
        station_name=("MonitoringLocationName_result", "first"),
        latitude=("LatitudeMeasure", "first"),
        longitude=("LongitudeMeasure", "first"),
        avg_nitrate=("ResultMeasureValue", "mean"),
        max_nitrate=("ResultMeasureValue", "max"),
        min_nitrate=("ResultMeasureValue", "min"),
        total_records=("ResultMeasureValue", "count"),
        first_date=("ActivityStartDate", "min"),
        last_date=("ActivityStartDate", "max"),
        unit=("ResultMeasure/MeasureUnitCode", "first")
    ).reset_index()

    summary["days_span"] = (
        summary["last_date"] - summary["first_date"]
    ).dt.days

    summary = summary.dropna(
        subset=["latitude", "longitude", "avg_nitrate"]
    )

    summary["station_name"] = summary["station_name"].fillna(
        summary["MonitoringLocationIdentifier"]
    )

    summary["station_name"] = summary["station_name"].astype(str)

    summary.to_csv(
        os.path.join(OUTPUT_DIR, "nitrate_map_data.csv"),
        index=False
    )

    return summary


def get_color(value):
    if value >= 2.0:
        return "red"
    elif value >= 1.0:
        return "orange"
    elif value >= 0.5:
        return "green"
    else:
        return "blue"


def get_radius(value):
    return max(5, min(value * 6, 18))


def create_nitrate_map(summary):
    center_lat = summary["latitude"].mean()
    center_lon = summary["longitude"].mean()

    water_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles="OpenStreetMap"
    )

    for _, row in summary.iterrows():
        station_id = row["MonitoringLocationIdentifier"]
        station_name = row["station_name"]
        avg_nitrate = row["avg_nitrate"]
        max_nitrate = row["max_nitrate"]
        min_nitrate = row["min_nitrate"]
        total_records = row["total_records"]
        first_date = row["first_date"].date()
        last_date = row["last_date"].date()
        unit = row["unit"]

        popup_html = f"""
        <b>Station:</b> {station_name}<br>
        <b>Station ID:</b> {station_id}<br>
        <b>Average Nitrate:</b> {avg_nitrate:.3f} {unit}<br>
        <b>Max Nitrate:</b> {max_nitrate:.3f} {unit}<br>
        <b>Min Nitrate:</b> {min_nitrate:.3f} {unit}<br>
        <b>Total Records:</b> {total_records}<br>
        <b>Date Range:</b> {first_date} to {last_date}<br><br>
        <a href="/station/{station_id}" target="_blank">View Station Trends</a>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=get_radius(avg_nitrate),
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{station_name}: {avg_nitrate:.2f}",
            color=get_color(avg_nitrate),
            fill=True,
            fill_color=get_color(avg_nitrate),
            fill_opacity=0.7
        ).add_to(water_map)

    legend_html = """
    <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        width: 220px;
        height: 150px;
        background-color: white;
        border:2px solid grey;
        z-index:9999;
        font-size:14px;
        padding: 10px;
    ">
    <b>Nitrate Level</b><br>
    <i style="background:blue;width:12px;height:12px;float:left;margin-right:8px;"></i>
    Low: &lt; 0.5<br>
    <i style="background:green;width:12px;height:12px;float:left;margin-right:8px;"></i>
    Moderate: 0.5 - 1.0<br>
    <i style="background:orange;width:12px;height:12px;float:left;margin-right:8px;"></i>
    High: 1.0 - 2.0<br>
    <i style="background:red;width:12px;height:12px;float:left;margin-right:8px;"></i>
    Very High: ≥ 2.0<br>
    </div>
    """

    water_map.get_root().html.add_child(folium.Element(legend_html))

    output_path = os.path.join(OUTPUT_DIR, "nitrate_interactive_map.html")
    water_map.save(output_path)

    print("Map saved to:", output_path)


def main():
    df = load_and_clean_data()
    summary = get_nitrate_station_summary(df)
    create_nitrate_map(summary)


if __name__ == "__main__":
    main()