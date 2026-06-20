import csv
import io
import json
import math
import zipfile
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping
from shapely.ops import nearest_points


BASE_DIR = Path(__file__).resolve().parents[1]

WATERSHED_PATH = BASE_DIR / "data" / "external" / "watershed" / "nj_watershed_management_areas.geojson"
WASTEWATER_PATH = BASE_DIR / "data" / "external" / "wastewater" / "New_Jersey_Pollution_Discharge_Elimination_System_(NJPDES)_Regulated_Facility_Locations.shp"
DMR_ZIP_DIR = BASE_DIR / "data" / "external" / "discharge" / "npdes_dmr_limits_by_fy"
DMR_SUMMARY_PATH = BASE_DIR / "data" / "external" / "discharge" / "nj_npdes_dmr_flow_load_summary.csv"
HYDROGRAPHY_DIR = BASE_DIR / "data" / "external" / "hydrography"
NHD_ARCGIS_GEOJSON = HYDROGRAPHY_DIR / "nhd_flowline_nj_arcgis.geojson"

OUT_PROCESSED = BASE_DIR / "data" / "processed"
OUT_DASHBOARD = BASE_DIR / "output" / "dashboard"
OUT_MAPS = BASE_DIR / "output" / "maps"
OUT_LOGS = BASE_DIR / "output" / "logs"
LOG_PATH = OUT_LOGS / "21_hydrography_outfall_visualization_log.txt"

OUTFALL_FEATURE_CSV = OUT_PROCESSED / "dmr_permit_feature_summary.csv"
OUTFALL_WATERSHED_CSV = OUT_PROCESSED / "watershed_outfall_feature_summary.csv"
HYDRO_WATERSHED_CSV = OUT_PROCESSED / "watershed_hydrography_flowline_summary.csv"
OUTFALL_PROXY_CSV = OUT_PROCESSED / "dmr_outfall_snapped_proxy_points.csv"

OUTFALL_FEATURE_JSON = OUT_DASHBOARD / "dmr_permit_feature_summary.json"
OUTFALL_WATERSHED_JSON = OUT_DASHBOARD / "watershed_outfall_feature_summary.json"
HYDRO_WATERSHED_JSON = OUT_DASHBOARD / "watershed_hydrography_flowline_summary.json"
HYDRO_STATUS_JSON = OUT_DASHBOARD / "hydrography_outfall_status.json"
OUTFALL_PROXY_JSON = OUT_DASHBOARD / "dmr_outfall_snapped_proxy_points.json"

HYDRO_MAP = OUT_MAPS / "hydrography_outfall_context_map.html"


def ensure_dirs():
    for path in [OUT_PROCESSED, OUT_DASHBOARD, OUT_MAPS, OUT_LOGS]:
        path.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def normalize_permit_id(value):
    if pd.isna(value):
        return ""
    text = str(value).upper().strip()
    if text.endswith(".0"):
        text = text[:-2]
    return "".join(ch for ch in text if ch.isalnum())


def export_json(df, path):
    clean = df.replace([np.inf, -np.inf], np.nan)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean.where(pd.notna(clean), None).to_dict(orient="records"), f, indent=2)


def relevant_parameter(description):
    desc = str(description).lower()
    return any(key in desc for key in ["flow", "nitrogen", "nitrate", "nitrite", "ammonia", "load"])


def read_dmr_permit_features():
    if not DMR_ZIP_DIR.exists():
        raise FileNotFoundError(f"Missing DMR ZIP folder: {DMR_ZIP_DIR}")

    rows = {}
    zip_count = 0
    relevant_rows = 0
    for zip_path in sorted(DMR_ZIP_DIR.glob("NJ_FY*_NPDES_DMRS_LIMITS.zip")):
        zip_count += 1
        with zipfile.ZipFile(zip_path) as zf:
            dmr_names = [name for name in zf.namelist() if "DMRS" in name.upper()]
            if not dmr_names:
                continue
            with zf.open(dmr_names[0]) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""))
                for row in reader:
                    description = row.get("PARAMETER_DESC", "")
                    if not relevant_parameter(description):
                        continue
                    permit = normalize_permit_id(row.get("EXTERNAL_PERMIT_NMBR"))
                    feature_number = str(row.get("PERM_FEATURE_NMBR", "")).strip()
                    feature_type = str(row.get("PERM_FEATURE_TYPE_CODE", "")).strip() or "unknown"
                    if not permit or not feature_number:
                        continue
                    key = (permit, feature_number, feature_type)
                    if key not in rows:
                        rows[key] = {
                            "permit_id_clean": permit,
                            "permit_feature_number": feature_number,
                            "permit_feature_type": feature_type,
                            "dmr_relevant_record_count": 0,
                            "flow_record_count": 0,
                            "nitrogen_record_count": 0,
                            "monitoring_location_codes": set(),
                            "parameters": set(),
                        }
                    item = rows[key]
                    item["dmr_relevant_record_count"] += 1
                    relevant_rows += 1
                    desc_lower = str(description).lower()
                    if "flow" in desc_lower:
                        item["flow_record_count"] += 1
                    if any(key_part in desc_lower for key_part in ["nitrogen", "nitrate", "nitrite", "ammonia"]):
                        item["nitrogen_record_count"] += 1
                    item["monitoring_location_codes"].add(str(row.get("MONITORING_LOCATION_CODE", "")).strip())
                    if len(item["parameters"]) < 12:
                        item["parameters"].add(str(description).strip())

    out_rows = []
    for item in rows.values():
        out_rows.append({
            "permit_id_clean": item["permit_id_clean"],
            "permit_feature_number": item["permit_feature_number"],
            "permit_feature_type": item["permit_feature_type"],
            "dmr_relevant_record_count": item["dmr_relevant_record_count"],
            "flow_record_count": item["flow_record_count"],
            "nitrogen_record_count": item["nitrogen_record_count"],
            "monitoring_location_codes": ", ".join(sorted(code for code in item["monitoring_location_codes"] if code)),
            "example_parameters": "; ".join(sorted(item["parameters"])),
        })

    df = pd.DataFrame(out_rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "permit_id_clean",
            "permit_feature_number",
            "permit_feature_type",
            "dmr_relevant_record_count",
            "flow_record_count",
            "nitrogen_record_count",
            "monitoring_location_codes",
            "example_parameters",
        ])
    log(f"DMR ZIP files read: {zip_count}")
    log(f"Relevant DMR permit-feature rows counted: {relevant_rows:,}")
    log(f"Unique permit features: {len(df):,}")
    return df


def read_base_layers():
    watersheds = gpd.read_file(WATERSHED_PATH)
    facilities = gpd.read_file(WASTEWATER_PATH)
    watersheds = watersheds[["WMA_NAME", "WR_NAME", "geometry"]].rename(columns={"WMA_NAME": "watershed_name"})
    if watersheds.crs is None:
        watersheds = watersheds.set_crs("EPSG:4326")
    if facilities.crs is None:
        raise ValueError("NJPDES facility shapefile has no CRS.")
    return watersheds, facilities


def attach_facility_context(permit_features, watersheds, facilities):
    facilities = facilities.copy()
    facilities["permit_id_clean"] = facilities["NJPDES"].apply(normalize_permit_id)
    facilities["facility_name"] = facilities["FACILITY"].astype(str)
    facilities_wgs = facilities.to_crs("EPSG:4326")
    watersheds_wgs = watersheds.to_crs("EPSG:4326")

    facility_watershed = gpd.sjoin(
        facilities_wgs[["permit_id_clean", "facility_name", "DISTYPE", "geometry"]],
        watersheds_wgs[["watershed_name", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")

    joined = permit_features.merge(
        pd.DataFrame(facility_watershed.drop(columns="geometry")),
        on="permit_id_clean",
        how="left",
    )
    joined["spatial_status"] = np.where(
        joined["watershed_name"].notna(),
        "matched_to_facility_point_watershed",
        "permit_feature_without_local_facility_point",
    )
    return joined, facility_watershed


def read_flowlines_for_watersheds(watersheds):
    watersheds_wgs = watersheds.to_crs("EPSG:4269")
    minx, miny, maxx, maxy = watersheds_wgs.total_bounds
    bbox = (minx - 0.05, miny - 0.05, maxx + 0.05, maxy + 0.05)

    frames = []
    if NHD_ARCGIS_GEOJSON.exists():
        log(f"Reading downloaded NHD ArcGIS GeoJSON: {NHD_ARCGIS_GEOJSON}")
        arcgis_flowlines = gpd.read_file(NHD_ARCGIS_GEOJSON)
        if arcgis_flowlines.crs is None:
            arcgis_flowlines = arcgis_flowlines.set_crs("EPSG:4326")
        arcgis_flowlines = arcgis_flowlines.to_crs("EPSG:4269")
        arcgis_flowlines["source_hu4"] = "arcgis_nhd_service"
        arcgis_flowlines["source_zip"] = NHD_ARCGIS_GEOJSON.name
        frames.append(arcgis_flowlines)

    zip_paths = sorted(HYDROGRAPHY_DIR.glob("NHDPLUS_H_*_HU4_GDB.zip"))
    for zip_path in zip_paths:
        hu4 = zip_path.name.replace("NHDPLUS_H_", "").replace("_HU4_GDB.zip", "")
        gdb_name = zip_path.name.replace(".zip", ".gdb")
        gdb_path = f"/vsizip/{zip_path.resolve()}/{gdb_name}"
        try:
            log(f"Reading NHDFlowline from {zip_path.name} within bbox: {bbox}")
            sub = gpd.read_file(gdb_path, layer="NHDFlowline", bbox=bbox)
            if sub.crs is None:
                sub = sub.set_crs("EPSG:4269")
            sub = sub.to_crs("EPSG:4269")
            sub["source_hu4"] = hu4
            sub["source_zip"] = zip_path.name
            log(f"{zip_path.name}: {len(sub):,} NHDFlowline rows in bbox")
            if not sub.empty:
                frames.append(sub)
        except Exception as exc:
            log(f"[NHDPlus] Could not read {zip_path.name}: {exc}")

    if frames:
        flowlines = pd.concat(frames, ignore_index=True)
        flowlines = gpd.GeoDataFrame(flowlines, geometry="geometry", crs=frames[0].crs)
    else:
        flowlines = gpd.GeoDataFrame(columns=["geometry", "source_hu4", "source_zip"], geometry="geometry", crs="EPSG:4269")

    rename_map = {
        "PERMANENT_IDENTIFIER": "Permanent_Identifier",
        "OBJECTID": "Permanent_Identifier",
        "GNIS_NAME": "GNIS_Name",
        "LENGTHKM": "LengthKM",
        "FTYPE": "FType",
        "FCODE": "FCode",
        "FLOWDIR": "FlowDir",
        "COMID": "NHDPlusID",
    }
    flowlines = flowlines.rename(columns={k: v for k, v in rename_map.items() if k in flowlines.columns})
    flowlines = flowlines.loc[:, ~flowlines.columns.duplicated()].copy()
    if "InNetwork" not in flowlines.columns:
        flowlines["InNetwork"] = 1

    keep_cols = [
        "Permanent_Identifier",
        "GNIS_Name",
        "LengthKM",
        "FType",
        "FCode",
        "FlowDir",
        "InNetwork",
        "NHDPlusID",
        "source_hu4",
        "source_zip",
        "geometry",
    ]
    flowlines = flowlines[[col for col in keep_cols if col in flowlines.columns]].copy()
    flowlines = flowlines[flowlines.geometry.notna()].copy()
    if flowlines.crs is None:
        flowlines = flowlines.set_crs("EPSG:4269")
    flowlines = flowlines.to_crs(watersheds_wgs.crs)

    joined = gpd.sjoin(
        flowlines,
        watersheds_wgs[["watershed_name", "geometry"]],
        how="inner",
        predicate="intersects",
    ).drop(columns=["index_right"], errors="ignore")
    log(f"NHDFlowline rows intersecting NJ watersheds: {len(joined):,}")
    return joined


def summarize_flowlines(flowlines):
    if flowlines.empty:
        return pd.DataFrame(columns=[
            "watershed_name",
            "flowline_segment_count",
            "flowline_total_length_km",
            "named_flowline_count",
            "in_network_segment_count",
        ])
    summary = (
        flowlines.groupby("watershed_name", as_index=False)
        .agg(
            flowline_segment_count=("Permanent_Identifier", "count"),
            flowline_total_length_km=("LengthKM", "sum"),
            named_flowline_count=("GNIS_Name", lambda s: int(s.notna().sum())),
            in_network_segment_count=("InNetwork", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
        )
    )
    summary["flowline_total_length_km"] = summary["flowline_total_length_km"].round(4)
    return summary


def summarize_outfall_features(features_with_context):
    if features_with_context.empty:
        return pd.DataFrame(columns=[
            "watershed_name",
            "dmr_permit_feature_count",
            "exo_feature_count",
            "flow_feature_record_count",
            "nitrogen_feature_record_count",
        ])

    valid = features_with_context.dropna(subset=["watershed_name"]).copy()
    if valid.empty:
        return pd.DataFrame(columns=[
            "watershed_name",
            "dmr_permit_feature_count",
            "exo_feature_count",
            "flow_feature_record_count",
            "nitrogen_feature_record_count",
        ])

    summary = (
        valid.groupby("watershed_name", as_index=False)
        .agg(
            dmr_permit_feature_count=("permit_feature_number", "count"),
            exo_feature_count=("permit_feature_type", lambda s: int((s == "EXO").sum())),
            flow_feature_record_count=("flow_record_count", "sum"),
            nitrogen_feature_record_count=("nitrogen_record_count", "sum"),
        )
    )
    return summary


def make_snapped_outfall_proxies(features_with_context, facility_watershed, flowlines):
    columns = [
        "permit_id_clean",
        "facility_name",
        "watershed_name",
        "permit_feature_count",
        "exo_feature_count",
        "flow_feature_record_count",
        "nitrogen_feature_record_count",
        "facility_lat",
        "facility_lon",
        "snapped_outfall_proxy_lat",
        "snapped_outfall_proxy_lon",
        "nearest_flowline_name",
        "nearest_flowline_id",
        "snap_distance_m",
        "coordinate_status",
    ]
    if features_with_context.empty or flowlines.empty:
        return pd.DataFrame(columns=columns)

    matched = features_with_context.dropna(subset=["watershed_name"]).copy()
    if matched.empty:
        return pd.DataFrame(columns=columns)

    feature_summary = (
        matched.groupby("permit_id_clean", as_index=False)
        .agg(
            permit_feature_count=("permit_feature_number", "count"),
            exo_feature_count=("permit_feature_type", lambda s: int((s == "EXO").sum())),
            flow_feature_record_count=("flow_record_count", "sum"),
            nitrogen_feature_record_count=("nitrogen_record_count", "sum"),
        )
    )

    facilities = facility_watershed[
        facility_watershed["permit_id_clean"].isin(set(feature_summary["permit_id_clean"]))
        & facility_watershed["watershed_name"].notna()
    ].copy()
    if facilities.empty:
        return pd.DataFrame(columns=columns)

    facilities = facilities.merge(feature_summary, on="permit_id_clean", how="left")
    facilities = facilities.drop_duplicates(subset=["permit_id_clean", "watershed_name"]).copy()
    facilities["facility_join_id"] = range(len(facilities))

    lines = flowlines.copy()
    lines = lines[lines.geometry.notna()].copy()
    lines["flowline_join_id"] = range(len(lines))

    facilities_m = facilities.to_crs("EPSG:3857")
    lines_m = lines.to_crs("EPSG:3857")
    nearest = gpd.sjoin_nearest(
        facilities_m,
        lines_m[["flowline_join_id", "GNIS_Name", "NHDPlusID", "geometry"]],
        how="left",
        distance_col="snap_distance_m",
    ).drop(columns=["index_right"], errors="ignore")

    line_geoms = dict(zip(lines_m["flowline_join_id"], lines_m.geometry))
    rows = []
    for _, row in nearest.iterrows():
        line_geom = line_geoms.get(row.get("flowline_join_id"))
        if line_geom is None or row.geometry is None:
            continue
        _, snapped = nearest_points(row.geometry, line_geom)
        facility_wgs = gpd.GeoSeries([row.geometry], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
        snapped_wgs = gpd.GeoSeries([snapped], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
        rows.append({
            "permit_id_clean": row.get("permit_id_clean"),
            "facility_name": row.get("facility_name"),
            "watershed_name": row.get("watershed_name"),
            "permit_feature_count": int(row.get("permit_feature_count", 0) or 0),
            "exo_feature_count": int(row.get("exo_feature_count", 0) or 0),
            "flow_feature_record_count": int(row.get("flow_feature_record_count", 0) or 0),
            "nitrogen_feature_record_count": int(row.get("nitrogen_feature_record_count", 0) or 0),
            "facility_lat": round(float(facility_wgs.y), 6),
            "facility_lon": round(float(facility_wgs.x), 6),
            "snapped_outfall_proxy_lat": round(float(snapped_wgs.y), 6),
            "snapped_outfall_proxy_lon": round(float(snapped_wgs.x), 6),
            "nearest_flowline_name": row.get("GNIS_Name"),
            "nearest_flowline_id": row.get("NHDPlusID"),
            "snap_distance_m": round(float(row.get("snap_distance_m", np.nan)), 2),
            "coordinate_status": "snapped_to_nearest_nhd_flowline_proxy",
        })

    return pd.DataFrame(rows, columns=columns)


def sample_flowlines_for_map(flowlines, max_segments=2200):
    if len(flowlines) <= max_segments:
        return flowlines
    ranked = flowlines.copy()
    ranked["rank_length"] = pd.to_numeric(ranked.get("LengthKM"), errors="coerce").fillna(0)
    ranked = ranked.sort_values(["InNetwork", "rank_length"], ascending=[False, False]).head(max_segments)
    return ranked.drop(columns=["rank_length"], errors="ignore")


def is_in_network(value):
    try:
        if pd.isna(value):
            return 1
        return int(value)
    except (TypeError, ValueError):
        return 1


def make_map(watersheds, flowlines, facilities_with_watershed, features_with_context, outfall_proxies):
    center = [40.15, -74.55]
    m = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron", control_scale=True)

    watershed_layer = folium.FeatureGroup(name="NJ watershed management areas", show=True)
    watersheds_wgs = watersheds.to_crs("EPSG:4326")
    folium.GeoJson(
        watersheds_wgs[["watershed_name", "WR_NAME", "geometry"]].to_json(),
        name="Watersheds",
        style_function=lambda _: {"color": "#334155", "weight": 1, "fillOpacity": 0.04},
        tooltip=folium.GeoJsonTooltip(fields=["watershed_name", "WR_NAME"], aliases=["Watershed", "Region"]),
    ).add_to(watershed_layer)
    watershed_layer.add_to(m)

    flow_layer = folium.FeatureGroup(name="NHDPlus flowlines", show=True)
    map_flowlines = sample_flowlines_for_map(flowlines).to_crs("EPSG:4326")
    for _, row in map_flowlines.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        name = row.get("GNIS_Name")
        popup = (
            f"<b>{name if pd.notna(name) else 'Unnamed flowline'}</b><br>"
            f"Length km: {row.get('LengthKM', 'N/A')}<br>"
            f"NHDPlusID: {row.get('NHDPlusID', 'N/A')}<br>"
            f"Watershed: {row.get('watershed_name', 'N/A')}"
        )
        folium.GeoJson(
            mapping(geom),
            style_function=lambda _, in_network=row.get("InNetwork", 0): {
                "color": "#0f766e" if is_in_network(in_network) == 1 else "#60a5fa",
                "weight": 2 if is_in_network(in_network) == 1 else 1,
                "opacity": 0.55,
            },
            popup=folium.Popup(popup, max_width=320),
        ).add_to(flow_layer)
    flow_layer.add_to(m)

    facility_layer = folium.FeatureGroup(name="Snapped DMR outfall proxies", show=True)
    for _, row in outfall_proxies.iterrows():
        popup = (
            f"<b>{row.get('facility_name', 'Facility')}</b><br>"
            f"Permit: {row.get('permit_id_clean', 'N/A')}<br>"
            f"DMR permit features: {row.get('permit_feature_count', 'N/A')}<br>"
            f"Watershed: {row.get('watershed_name', 'N/A')}<br>"
            f"Nearest flowline: {row.get('nearest_flowline_name') or 'Unnamed'}<br>"
            f"Snap distance: {row.get('snap_distance_m', 'N/A')} m<br>"
            "Marker location: facility point snapped to nearest NHD flowline proxy"
        )
        folium.CircleMarker(
            location=[row["snapped_outfall_proxy_lat"], row["snapped_outfall_proxy_lon"]],
            radius=5 + min(int(row.get("permit_feature_count", 0) or 0), 8),
            color="#b91c1c",
            fill=True,
            fill_color="#ef4444",
            fill_opacity=0.78,
            weight=1,
            popup=folium.Popup(popup, max_width=340),
        ).add_to(facility_layer)
        folium.PolyLine(
            locations=[
                [row["facility_lat"], row["facility_lon"]],
                [row["snapped_outfall_proxy_lat"], row["snapped_outfall_proxy_lon"]],
            ],
            color="#f97316",
            weight=1,
            opacity=0.55,
        ).add_to(facility_layer)
    facility_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(HYDRO_MAP)


def build_status(features, features_with_context, flowlines, outfall_proxies):
    matched_features = int(features_with_context["watershed_name"].notna().sum()) if not features_with_context.empty else 0
    zip_paths = sorted(HYDROGRAPHY_DIR.glob("NHDPLUS_H_*_HU4_GDB.zip"))
    flowline_status = (
        "loaded_intersecting_flowlines"
        if len(flowlines)
        else "no_intersecting_flowlines_in_local_hu4_packages"
    )
    status = pd.DataFrame([{
        "status": "loaded",
        "dmr_zip_folder": str(DMR_ZIP_DIR),
        "nhdplus_sources": "; ".join(path.name for path in zip_paths),
        "permit_feature_count": int(len(features)),
        "permit_features_matched_to_facility_watershed": matched_features,
        "snapped_outfall_proxy_count": int(len(outfall_proxies)),
        "median_snap_distance_m": round(float(outfall_proxies["snap_distance_m"].median()), 2) if not outfall_proxies.empty else None,
        "flowline_segment_count": int(len(flowlines)),
        "outfall_coordinate_status": "snapped_proxy_generated",
        "outfall_proxy_used": "NJPDES facility point snapped to nearest NHD flowline for matched permit features",
        "flowline_network_status": flowline_status,
        "recommended_hu4_note": "For full NJ coverage, place the relevant NHDPlus HR HU4 FileGDB ZIPs in data/external/hydrography, then rerun Step 21.",
        "map_path": "/maps/hydrography_outfall_context_map.html",
    }])
    return status


def main():
    ensure_dirs()
    log("========== Step 21: Hydrography and DMR Permit Feature Visualization ==========")

    permit_features = read_dmr_permit_features()
    watersheds, facilities = read_base_layers()
    features_with_context, facility_watershed = attach_facility_context(permit_features, watersheds, facilities)
    flowlines = read_flowlines_for_watersheds(watersheds)

    outfall_watershed = summarize_outfall_features(features_with_context)
    hydro_summary = summarize_flowlines(flowlines)
    outfall_proxies = make_snapped_outfall_proxies(features_with_context, facility_watershed, flowlines)
    status = build_status(permit_features, features_with_context, flowlines, outfall_proxies)

    features_with_context.to_csv(OUTFALL_FEATURE_CSV, index=False)
    outfall_watershed.to_csv(OUTFALL_WATERSHED_CSV, index=False)
    hydro_summary.to_csv(HYDRO_WATERSHED_CSV, index=False)
    outfall_proxies.to_csv(OUTFALL_PROXY_CSV, index=False)

    export_json(features_with_context.head(2000), OUTFALL_FEATURE_JSON)
    export_json(outfall_watershed, OUTFALL_WATERSHED_JSON)
    export_json(hydro_summary, HYDRO_WATERSHED_JSON)
    export_json(outfall_proxies, OUTFALL_PROXY_JSON)
    export_json(status, HYDRO_STATUS_JSON)

    make_map(watersheds, flowlines, facility_watershed, features_with_context, outfall_proxies)

    log("")
    log("========== Hydrography / Outfall Status ==========")
    log(status.to_string(index=False))
    log("")
    log(f"[EXPORT] {OUTFALL_FEATURE_CSV}")
    log(f"[EXPORT] {OUTFALL_WATERSHED_CSV}")
    log(f"[EXPORT] {HYDRO_WATERSHED_CSV}")
    log(f"[EXPORT] {OUTFALL_PROXY_CSV}")
    log(f"[EXPORT] {HYDRO_MAP}")
    log("========== Step 21 Complete ==========")


if __name__ == "__main__":
    main()
