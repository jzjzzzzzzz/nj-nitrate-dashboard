import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "data" / "external" / "hydrography"
LOG_PATH = BASE_DIR / "output" / "logs" / "download_nhdplus_hu4_log.txt"

# USGS The National Map staged products. Add or replace URLs here if USGS changes
# product paths or if a narrower HU4 set is preferred.
CANDIDATE_URLS = [
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/VPU/HighResolution/GDB/NHDPLUS_H_0203_HU4_GDB.zip",
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/VPU/HighResolution/GDB/NHDPLUS_H_0204_HU4_GDB.zip",
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/VPU/HighResolution/GDB/NHDPLUS_H_0205_HU4_GDB.zip",
]


def log(message):
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def download(url):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    output_path = OUT_DIR / filename
    if output_path.exists() and output_path.stat().st_size > 0:
        log(f"[SKIP] {filename} already exists.")
        return

    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()

    log(f"[DOWNLOAD] {url}")
    try:
        with urllib.request.urlopen(url, timeout=90) as response:
            with open(temp_path, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        temp_path.replace(output_path)
        log(f"[OK] {output_path} ({output_path.stat().st_size:,} bytes)")
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        log(f"[FAILED] {url}: {exc}")


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    log("========== Download NHDPlus HR HU4 ZIPs ==========")
    for url in CANDIDATE_URLS:
        download(url)
    log("========== Download Attempt Complete ==========")


if __name__ == "__main__":
    main()
