from __future__ import annotations

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_m * math.asin(math.sqrt(a))


def maps_url_for_coords(latitude: float, longitude: float) -> str:
    return f"https://www.google.com/maps?q={latitude},{longitude}"


def store_from_gps(
    lat: float | None,
    lon: float | None,
    stores: list[dict],
) -> dict | None:
    if lat is None or lon is None or not stores:
        return None
    best: dict | None = None
    best_distance = float("inf")
    for store in stores:
        radius_m = store.get("match_radius_m", 150)
        distance = haversine_m(lat, lon, store["latitude"], store["longitude"])
        if distance <= radius_m and distance < best_distance:
            best = store
            best_distance = distance
    return best
