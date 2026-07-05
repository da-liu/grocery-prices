from __future__ import annotations

from grocery_extract.exif import normalize_client_exif


def test_normalize_client_exif_accepts_gps_and_datetime():
    result = normalize_client_exif(
        {
            "GPSLatitude": 43.6532,
            "GPSLongitude": -79.3832,
            "DateTimeOriginal": "2026:07:04 18:30:00",
        }
    )
    assert result == {
        "GPSLatitude": 43.6532,
        "GPSLongitude": -79.3832,
        "DateTimeOriginal": "2026:07:04 18:30:00",
    }


def test_normalize_client_exif_accepts_datetime_only():
    result = normalize_client_exif({"DateTimeOriginal": "2026-07-04T18:30:00"})
    assert result == {"DateTimeOriginal": "2026:07:04 18:30:00"}


def test_normalize_client_exif_rejects_invalid_gps():
    result = normalize_client_exif(
        {
            "GPSLatitude": 120,
            "GPSLongitude": 0,
            "DateTimeOriginal": "2026:07:04 18:30:00",
        }
    )
    assert result == {"DateTimeOriginal": "2026:07:04 18:30:00"}


def test_normalize_client_exif_returns_none_for_empty():
    assert normalize_client_exif(None) is None
    assert normalize_client_exif({}) is None
