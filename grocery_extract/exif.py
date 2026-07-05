from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

_TOOL_SEARCH_PATH = os.pathsep.join(
    [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
)


def _find_tool(name: str) -> str:
    path = os.environ.get("PATH", _TOOL_SEARCH_PATH)
    found = shutil.which(name, path=path)
    if found:
        return found
    for directory in _TOOL_SEARCH_PATH.split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        f"{name} not found on PATH (launchd services need Homebrew in PATH or install to /usr/local/bin)"
    )


def tool_path(name: str) -> str:
    return _find_tool(name)


def date_folder_from_exif(raw_dt: str | None) -> str | None:
    if not raw_dt:
        return None
    return raw_dt[:10].replace(":", "_")


def captured_at_from_exif(raw_dt: str | None) -> str | None:
    if not raw_dt:
        return None
    return raw_dt.replace(":", "-", 2).replace(" ", "T", 1)


def extract_exif(image_path: Path) -> dict:
    cmd = [
        _find_tool("exiftool"),
        "-n",
        "-json",
        "-GPSLatitude",
        "-GPSLongitude",
        "-DateTimeOriginal",
        str(image_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    rows = json.loads(out)
    return rows[0] if rows else {}


def _normalize_datetime_original(raw_dt: str) -> str | None:
    cleaned = raw_dt.strip().replace("T", " ", 1).split(".", 1)[0]
    if len(cleaned) < 19:
        return None
    if cleaned[4] == "-" and cleaned[7] == "-":
        cleaned = cleaned.replace("-", ":", 2)
    if cleaned[4] == ":" and cleaned[7] == ":":
        return cleaned
    return None


def normalize_client_exif(raw: dict | None) -> dict | None:
    """Validate EXIF sent from the browser before ingest."""
    if not raw or not isinstance(raw, dict):
        return None

    result: dict[str, float | str] = {}

    lat = raw.get("GPSLatitude")
    lon = raw.get("GPSLongitude")
    if lat is not None and lon is not None:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            pass
        else:
            if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                result["GPSLatitude"] = lat_f
                result["GPSLongitude"] = lon_f

    raw_dt = raw.get("DateTimeOriginal")
    if isinstance(raw_dt, str):
        cleaned = _normalize_datetime_original(raw_dt)
        if cleaned:
            result["DateTimeOriginal"] = cleaned

    return result or None


def convert_heic_to_jpg(heic_path: Path, jpg_path: Path) -> None:
    jpg_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_find_tool("sips"), "-s", "format", "jpeg", str(heic_path), "--out", str(jpg_path)],
        check=True,
        capture_output=True,
    )
