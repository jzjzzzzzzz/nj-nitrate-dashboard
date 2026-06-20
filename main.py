from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

PIPELINE_STEPS = [
    "scripts/01_clean_wqp_data.py",
    "scripts/02_extract_nitrate.py",
    "scripts/03_station_summary.py",
    "scripts/04_export_hotspot_map.py",
    "scripts/05_seasonal_analysis.py",
    "scripts/06_moving_average.py",
    "scripts/07_station_detail_export.py",
    "scripts/08_watershed_join.py",
    "scripts/09_watershed_comparison_map.py",
    "scripts/10_land_use_watershed_overlay.py",
    "scripts/11_land_use_nitrate_correlation.py",
    "scripts/12_wastewater_watershed_join.py",
    "scripts/13_facility_nitrate_correlation.py",
    "scripts/14_build_discharge_summary.py",
    "scripts/15_multivariable_regression.py",
    "scripts/16_validate_dashboard_assets.py",
    "scripts/18_robustness_reliability_model.py",
    "scripts/19_station_buffer_land_use.py",
    "scripts/20_additional_factors_hydrology_discharge.py",
    "scripts/21_hydrography_outfall_visualization.py",
    "scripts/17_export_research_proposal.py",
]


def run_step(script: str) -> None:
    path = BASE_DIR / script
    if not path.exists():
        raise FileNotFoundError(f"Pipeline step not found: {path}")
    print(f"\n========== Running {script} ==========")
    subprocess.run([sys.executable, str(path)], cwd=BASE_DIR, check=True)


def step_number(script: str) -> int:
    return int(Path(script).name.split("_", 1)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the nitrate analysis pipeline.")
    parser.add_argument(
        "--from-step",
        dest="from_step",
        help="Start at a script number, for example 18 or 20.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List pipeline scripts without running them.",
    )
    args = parser.parse_args()

    steps = PIPELINE_STEPS
    if args.from_step:
        first_step = int(args.from_step)
        start_index = next(
            (idx for idx, step in enumerate(PIPELINE_STEPS) if step_number(step) == first_step),
            None,
        )
        if start_index is None:
            raise ValueError(f"No pipeline step starts at or after {args.from_step}.")
        steps = PIPELINE_STEPS[start_index:]

    if args.list:
        for step in steps:
            print(step)
        return 0

    for step in steps:
        run_step(step)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
