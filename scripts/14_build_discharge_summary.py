import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DISCHARGE_DIR = BASE_DIR / "data" / "external" / "discharge"
ZIP_DIR = DISCHARGE_DIR / "npdes_dmr_limits_by_fy"
OUT_CSV = DISCHARGE_DIR / "nj_npdes_dmr_flow_load_summary.csv"
OUT_META = DISCHARGE_DIR / "nj_npdes_dmr_flow_load_summary_metadata.json"
LOG_PATH = BASE_DIR / "output" / "logs" / "14_build_discharge_summary_log.txt"


FLOW_KEYWORDS = ("flow",)
LOAD_KEYWORDS = ("load", "nitrogen", "nitrate", "nitrite", "ammonia")


def log(message):
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def is_relevant_parameter(description):
    desc = str(description).lower()
    return any(key in desc for key in FLOW_KEYWORDS + LOAD_KEYWORDS)


def safe_float(value):
    try:
        if value in (None, ""):
            return None
        result = float(value)
        if np.isfinite(result):
            return result
    except (TypeError, ValueError):
        return None
    return None


def update_metric(metrics, key, value):
    if value is None:
        return
    bucket = metrics[key]
    bucket["count"] += 1
    bucket["sum"] += value


def summarize_dmrs():
    if not ZIP_DIR.exists():
        raise FileNotFoundError(f"Missing EPA DMR ZIP directory: {ZIP_DIR}")

    permit_metrics = defaultdict(lambda: defaultdict(lambda: {"count": 0, "sum": 0.0}))
    param_counts = defaultdict(int)
    files_read = []
    rows_read = 0
    relevant_rows = 0

    for zip_path in sorted(ZIP_DIR.glob("NJ_FY*_NPDES_DMRS_LIMITS.zip")):
        log(f"Reading {zip_path.name}")
        files_read.append(zip_path.name)
        with zipfile.ZipFile(zip_path) as zf:
            dmr_names = [name for name in zf.namelist() if "DMRS" in name.upper()]
            if not dmr_names:
                continue
            with zf.open(dmr_names[0]) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
                reader = csv.DictReader(text)
                for row in reader:
                    rows_read += 1
                    permit = str(row.get("EXTERNAL_PERMIT_NMBR", "")).upper().strip()
                    description = row.get("PARAMETER_DESC", "")
                    if not permit or not is_relevant_parameter(description):
                        continue

                    value = safe_float(row.get("DMR_VALUE_STANDARD_UNITS"))
                    if value is None:
                        value = safe_float(row.get("DMR_VALUE_NMBR"))
                    if value is None:
                        continue

                    relevant_rows += 1
                    desc_lower = str(description).lower()
                    unit = str(row.get("STANDARD_UNIT_DESC") or row.get("DMR_UNIT_DESC") or "").lower()
                    param_counts[description] += 1

                    if "flow" in desc_lower and "mgd" in unit:
                        update_metric(permit_metrics[permit], "flow_mgd", value)
                    elif any(key in desc_lower for key in LOAD_KEYWORDS) and unit in {"kg/d", "lb/d"}:
                        update_metric(permit_metrics[permit], "nitrogen_load", value)
                    elif any(key in desc_lower for key in LOAD_KEYWORDS) and unit in {"mg/l", "ug/l"}:
                        update_metric(permit_metrics[permit], "nitrogen_concentration", value)

    rows = []
    for permit, metrics in sorted(permit_metrics.items()):
        flow = metrics["flow_mgd"]
        load = metrics["nitrogen_load"]
        conc = metrics["nitrogen_concentration"]
        rows.append({
            "npdes_permit_id": permit,
            "dmr_flow_record_count": flow["count"],
            "mean_dmr_flow_mgd": flow["sum"] / flow["count"] if flow["count"] else None,
            "total_dmr_flow_mgd": flow["sum"] if flow["count"] else None,
            "dmr_nitrogen_load_record_count": load["count"],
            "mean_dmr_nitrogen_load": load["sum"] / load["count"] if load["count"] else None,
            "total_dmr_nitrogen_load": load["sum"] if load["count"] else None,
            "dmr_nitrogen_concentration_record_count": conc["count"],
            "mean_dmr_nitrogen_concentration": conc["sum"] / conc["count"] if conc["count"] else None,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)

    metadata = {
        "source": "EPA ECHO ICIS-NPDES DMR and Limit Data Set",
        "source_url": "https://echo.epa.gov/tools/data-downloads/icis-npdes-dmr-and-limit-data-set",
        "zip_directory": str(ZIP_DIR),
        "files_read": files_read,
        "rows_read": rows_read,
        "relevant_rows": relevant_rows,
        "permit_count": int(len(df)),
        "top_parameters": dict(sorted(param_counts.items(), key=lambda item: item[1], reverse=True)[:25]),
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    log(f"Rows read: {rows_read:,}")
    log(f"Relevant DMR rows: {relevant_rows:,}")
    log(f"Permits summarized: {len(df):,}")
    log(f"[EXPORT] {OUT_CSV}")
    log(f"[EXPORT] {OUT_META}")


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    log("========== Step 14: Build EPA DMR Flow/Load Summary ==========")
    summarize_dmrs()
    log("========== Step 14 Complete ==========")


if __name__ == "__main__":
    main()
