from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

SPATIAL_STEPS = [
    "scripts/08_watershed_join.py",
    "scripts/09_watershed_comparison_map.py",
    "scripts/10_land_use_watershed_overlay.py",
    "scripts/12_wastewater_watershed_join.py",
    "scripts/19_station_buffer_land_use.py",
    "scripts/20_additional_factors_hydrology_discharge.py",
]


def main() -> int:
    for script in SPATIAL_STEPS:
        path = BASE_DIR / script
        if not path.exists():
            raise FileNotFoundError(f"Spatial analysis step not found: {path}")
        print(f"\n========== Running {script} ==========")
        subprocess.run([sys.executable, str(path)], cwd=BASE_DIR, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
