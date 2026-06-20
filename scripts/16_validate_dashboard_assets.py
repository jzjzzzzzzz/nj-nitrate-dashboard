import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
LOG_PATH = OUTPUT_DIR / "logs" / "16_validate_dashboard_assets_log.txt"


def log(message):
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(str(message) + "\n")


def extract_paths():
    patterns = [
        r'["\'](/maps/[^"\']+)["\']',
        r'["\'](/figures/[^"\']+)["\']',
        r'["\'](/proposal-output/[^"\']+)["\']',
    ]
    paths = set()
    for template in TEMPLATE_DIR.glob("*.html"):
        text = template.read_text(encoding="utf-8")
        for pattern in patterns:
            paths.update(match.group(1) for match in re.finditer(pattern, text))
    return sorted(paths)


def local_path(route_path):
    if route_path.startswith("/maps/"):
        return OUTPUT_DIR / "maps" / route_path.removeprefix("/maps/")
    if route_path.startswith("/figures/"):
        return OUTPUT_DIR / "figures" / route_path.removeprefix("/figures/")
    if route_path.startswith("/proposal-output/"):
        return OUTPUT_DIR / "proposal" / route_path.removeprefix("/proposal-output/")
    raise ValueError(f"Unsupported route path: {route_path}")


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    log("========== Step 16: Validate Dashboard Assets ==========")
    missing = []
    for route_path in extract_paths():
        path = local_path(route_path)
        if path.exists():
            log(f"OK {route_path}")
        else:
            missing.append((route_path, path))
            log(f"MISSING {route_path} -> {path}")

    if missing:
        raise FileNotFoundError(
            "Missing dashboard assets:\n"
            + "\n".join(f"{route} -> {path}" for route, path in missing)
        )

    log("All referenced dashboard assets exist.")
    log("========== Step 16 Complete ==========")


if __name__ == "__main__":
    main()
