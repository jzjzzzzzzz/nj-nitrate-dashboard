import json
import time
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "data" / "external" / "hydrography"
OUT_GEOJSON = OUT_DIR / "nhd_flowline_nj_arcgis.geojson"
PAGE_DIR = OUT_DIR / "nhd_flowline_nj_arcgis_pages"
LOG_PATH = BASE_DIR / "output" / "logs" / "download_nhd_flowlines_arcgis_log.txt"

NHD_FLOWLINE_SMALL_SCALE_LAYER = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/4/query"
NJ_BBOX = "-75.6,38.8,-73.8,41.4"


def log(message):
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def request_json(params, timeout=120, retries=4):
    session = requests.Session()
    session.trust_env = False
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(
                NHD_FLOWLINE_SMALL_SCALE_LAYER,
                params=params,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_exc = exc
            log(f"[RETRY] attempt {attempt}/{retries} failed: {exc}")
            time.sleep(2 * attempt)
    raise last_exc


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log("========== Download NHD Flowlines from USGS ArcGIS REST ==========")
    count_params = {
        "f": "json",
        "where": "1=1",
        "geometry": NJ_BBOX,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true",
    }
    count_payload = request_json(count_params)
    total = int(count_payload.get("count", 0))
    log(f"Flowline features available in NJ bbox: {total:,}")

    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    page_size = 1000
    features = []
    for offset in range(0, total, page_size):
        page_path = PAGE_DIR / f"offset_{offset:06d}.json"
        if page_path.exists():
            with open(page_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            batch = payload.get("features", [])
            features.extend(batch)
            log(f"Loaded cached page {offset:,}; total {len(features):,}/{total:,}")
            continue

        params = {
            "f": "geojson",
            "where": "1=1",
            "geometry": NJ_BBOX,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OBJECTID,GNIS_NAME,LENGTHKM,FTYPE,FCODE,REACHCODE,COMID,FLOWDIR,RESOLUTION",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "orderByFields": "OBJECTID",
        }
        payload = request_json(params)
        if "error" in payload:
            raise RuntimeError(payload["error"])
        batch = payload.get("features", [])
        with open(page_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        features.extend(batch)
        log(f"Downloaded {len(features):,}/{total:,}")
        time.sleep(0.25)

    collection = {
        "type": "FeatureCollection",
        "name": "USGS_NHD_Flowline_Small_Scale_NJ_BBox",
        "source": "USGS National Hydrography Dataset ArcGIS REST service, layer 4 Flowline - Small Scale",
        "bbox": NJ_BBOX,
        "features": features,
    }
    with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(collection, f)
    log(f"[EXPORT] {OUT_GEOJSON}")
    log("========== Download Complete ==========")


if __name__ == "__main__":
    main()
