# For downloading everything


import os
import csv
import zipfile
import requests
from datetime import date, timedelta
from urllib.parse import urlencode


# ============================================================
# Project paths
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")

RAW_ZIP_DIR = os.path.join(DATA_DIR, "raw_wqp_zips")
RAW_CSV_DIR = os.path.join(DATA_DIR, "raw_wqp_csv_parts")
COMBINED_DIR = os.path.join(DATA_DIR, "combined")
LOG_DIR = os.path.join(DATA_DIR, "logs")

FINAL_CSV = os.path.join(COMBINED_DIR, "wqp_nj_2000_2026_combined.csv")
LOG_FILE = os.path.join(LOG_DIR, "download_log.txt")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAW_ZIP_DIR, exist_ok=True)
os.makedirs(RAW_CSV_DIR, exist_ok=True)
os.makedirs(COMBINED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# WQP settings
# ============================================================

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"

LAT = 40.34221993024599
LONG = -74.69798626716586
WITHIN_MILES = 200

# 修改点 1：
# 现在下载完整的 2000 到 2026 数据
START_DATE = date(2000, 1, 1)
END_DATE = date(2026, 5, 29)

PROVIDERS = ["NWIS", "STORET"]

DATA_PROFILE = "resultPhysChem"

TIMEOUT = 600
CHUNK_SIZE = 1024 * 1024


# ============================================================
# Helper functions
# ============================================================

def write_log(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def format_wqp_date(d):
    return d.strftime("%m-%d-%Y")


def month_ranges(start, end):
    current = start

    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)

        period_end = min(next_month - timedelta(days=1), end)

        yield current, period_end

        current = period_end + timedelta(days=1)


def build_wqp_url(provider, start, end):
    params = {
        "countrycode": "US",
        "statecode": "US:34",
        "within": str(WITHIN_MILES),
        "lat": str(LAT),
        "long": str(LONG),
        "startDateLo": format_wqp_date(start),
        "startDateHi": format_wqp_date(end),
        "mimeType": "csv",
        "zip": "yes",
        "sorted": "no",
        "dataProfile": DATA_PROFILE,
        "providers": provider,
    }

    return BASE_URL + "?" + urlencode(params)


# ============================================================
# Download functions
# ============================================================

def download_zip(url, output_path):
    temp_path = output_path + ".part"

    headers = {
        "User-Agent": "Python WQP downloader for NJ water quality research"
    }

    with requests.get(url, stream=True, timeout=TIMEOUT, headers=headers) as response:
        write_log(f"HTTP status: {response.status_code}")

        if response.status_code != 200:
            write_log("Failed URL:")
            write_log(url)
            write_log(response.text[:1000])
            response.raise_for_status()

        total_downloaded = 0

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    total_downloaded += len(chunk)

        write_log(f"Downloaded size: {total_downloaded / 1024 / 1024:.2f} MB")

    os.replace(temp_path, output_path)


def extract_zip(zip_path, csv_path):
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()

        if not names:
            raise ValueError(f"Empty zip file: {zip_path}")

        target_file = None

        for name in names:
            lower_name = name.lower()
            if lower_name.endswith(".csv") or lower_name.endswith(".txt"):
                target_file = name
                break

        if target_file is None:
            target_file = names[0]

        with z.open(target_file, "r") as source:
            with open(csv_path, "wb") as target:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    target.write(chunk)


def download_all_parts():
    write_log("")
    write_log("========== Start WQP Download ==========")
    write_log("Target period: 2000-01-01 to 2026-05-29")
    write_log("All downloaded files will be saved inside data/.")
    write_log("The output/ folder will NOT be touched.")

    for provider in PROVIDERS:
        for start, end in month_ranges(START_DATE, END_DATE):
            label = f"{provider}_{start.isoformat()}_{end.isoformat()}"

            zip_path = os.path.join(RAW_ZIP_DIR, label + ".zip")
            csv_path = os.path.join(RAW_CSV_DIR, label + ".csv")

            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                write_log(f"[SKIP] Already extracted: {label}")
                continue

            if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                url = build_wqp_url(provider, start, end)

                write_log("")
                write_log(f"[DOWNLOAD] {label}")
                write_log(url)

                try:
                    download_zip(url, zip_path)
                except Exception as e:
                    write_log(f"[ERROR] Download failed: {label}")
                    write_log(str(e))
                    continue
            else:
                write_log(f"[SKIP] Zip already exists: {label}")

            try:
                extract_zip(zip_path, csv_path)
                write_log(f"[OK] Extracted CSV: {csv_path}")
            except Exception as e:
                write_log(f"[ERROR] Extraction failed: {label}")
                write_log(str(e))

    write_log("========== Download Finished ==========")


# ============================================================
# Merge functions
# ============================================================

def merge_csv_files():
    write_log("")
    write_log("========== Start Merging CSV Files ==========")

    csv_files = []

    for file_name in sorted(os.listdir(RAW_CSV_DIR)):
        if file_name.lower().endswith(".csv"):
            csv_files.append(os.path.join(RAW_CSV_DIR, file_name))

    if not csv_files:
        write_log("[ERROR] No CSV files found.")
        return

    wrote_header = False
    total_rows = 0
    total_files = 0

    with open(FINAL_CSV, "w", newline="", encoding="utf-8") as output_file:
        writer = None

        for csv_path in csv_files:
            write_log(f"[MERGE] {csv_path}")

            try:
                with open(csv_path, "r", newline="", encoding="utf-8", errors="replace") as input_file:
                    reader = csv.reader(input_file)

                    try:
                        file_header = next(reader)
                    except StopIteration:
                        continue

                    if not wrote_header:
                        writer = csv.writer(output_file)
                        writer.writerow(file_header)
                        wrote_header = True

                    for row in reader:
                        writer.writerow(row)
                        total_rows += 1

                total_files += 1

            except Exception as e:
                write_log(f"[ERROR] Failed to merge: {csv_path}")
                write_log(str(e))

    write_log("========== Merge Finished ==========")
    write_log(f"Files merged: {total_files}")
    write_log(f"Rows merged: {total_rows}")
    write_log(f"Final CSV saved to: {FINAL_CSV}")


# ============================================================
# Main
# ============================================================

def main():
    download_all_parts()
    merge_csv_files()


if __name__ == "__main__":
    main()