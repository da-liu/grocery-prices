from __future__ import annotations


def date_folder_from_exif(raw_dt: str | None) -> str | None:
    if not raw_dt:
        return None
    return raw_dt[:10].replace(":", "_")


def captured_at_from_exif(raw_dt: str | None) -> str | None:
    if not raw_dt:
        return None
    return raw_dt.replace(":", "-", 2).replace(" ", "T", 1)


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
