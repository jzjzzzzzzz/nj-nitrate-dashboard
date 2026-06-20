import os
import shutil
from datetime import datetime


# ============================================================
# Project root
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)


# ============================================================
# Main folders
# ============================================================

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")


# ============================================================
# Data folders
# ============================================================

RAW_ZIP_DIR = os.path.join(DATA_DIR, "raw_wqp_zips")
RAW_CSV_DIR = os.path.join(DATA_DIR, "raw_wqp_csv_parts")
COMBINED_DIR = os.path.join(DATA_DIR, "combined")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
EXTERNAL_DIR = os.path.join(DATA_DIR, "external")

EXTERNAL_SUBDIRS = [
    "watershed",
    "agriculture",
    "industry",
    "wastewater",
    "land_use",
]


# ============================================================
# Output folders
# ============================================================

OUTPUT_SUBDIRS = [
    "dashboard",
    "maps",
    "charts",
    "tables",
    "reports",
    "logs",
]


# ============================================================
# Helper functions
# ============================================================

def make_dir(path):
    os.makedirs(path, exist_ok=True)
    print(f"[OK] Folder ready: {path}")


def backup_old_output():
    if not os.path.exists(OUTPUT_DIR):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BASE_DIR, f"output_backup_{timestamp}")

    shutil.move(OUTPUT_DIR, backup_dir)
    print(f"[BACKUP] Old output moved to: {backup_dir}")


def reset_processed_folder():
    if os.path.exists(PROCESSED_DIR):
        shutil.rmtree(PROCESSED_DIR)
        print(f"[RESET] Removed old processed folder: {PROCESSED_DIR}")

    make_dir(PROCESSED_DIR)


def create_data_structure():
    make_dir(DATA_DIR)

    # Keep raw and combined folders.
    make_dir(RAW_ZIP_DIR)
    make_dir(RAW_CSV_DIR)
    make_dir(COMBINED_DIR)

    # Recreate processed.
    reset_processed_folder()

    # External data folders.
    make_dir(EXTERNAL_DIR)

    for subdir in EXTERNAL_SUBDIRS:
        make_dir(os.path.join(EXTERNAL_DIR, subdir))


def create_output_structure():
    backup_old_output()

    make_dir(OUTPUT_DIR)

    for subdir in OUTPUT_SUBDIRS:
        make_dir(os.path.join(OUTPUT_DIR, subdir))


def create_scripts_structure():
    make_dir(SCRIPTS_DIR)


def write_readme_files():
    data_readme = os.path.join(DATA_DIR, "README.txt")
    output_readme = os.path.join(OUTPUT_DIR, "README.txt")

    with open(data_readme, "w", encoding="utf-8") as f:
        f.write(
            "DATA FOLDER\n"
            "===========\n\n"
            "This folder stores raw, combined, processed, and external water quality data.\n\n"
            "raw_wqp_zips/       = original downloaded WQP zip files\n"
            "raw_wqp_csv_parts/  = extracted WQP CSV parts\n"
            "combined/           = large combined WQP CSV files\n"
            "processed/          = cleaned and analysis-ready CSV files\n"
            "external/           = watershed, agriculture, industry, wastewater, and land-use data\n"
        )

    with open(output_readme, "w", encoding="utf-8") as f:
        f.write(
            "OUTPUT FOLDER\n"
            "=============\n\n"
            "This folder stores final website-ready files.\n\n"
            "dashboard/ = JSON files for website dashboard\n"
            "maps/      = interactive HTML maps\n"
            "charts/    = exported chart data or images\n"
            "tables/    = website-ready summary tables\n"
            "reports/   = generated research reports\n"
            "logs/      = pipeline logs\n"
        )

    print(f"[OK] README written: {data_readme}")
    print(f"[OK] README written: {output_readme}")


# ============================================================
# Main
# ============================================================

def main():
    print("========== Reset Project Structure ==========")

    create_scripts_structure()
    create_data_structure()
    create_output_structure()
    write_readme_files()

    print("========== Done ==========")
    print("")
    print("Important:")
    print("Raw download files are kept.")
    print("Old output folder is backed up, not deleted.")
    print("New output folder is now ready for the rebuilt website pipeline.")


if __name__ == "__main__":
    main()