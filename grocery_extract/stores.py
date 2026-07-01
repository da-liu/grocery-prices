from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES_PATH = ROOT / "data" / "stores.json"


def load_stores() -> tuple[list[dict], dict[str, dict]]:
    with STORES_PATH.open() as f:
        stores = json.load(f)
    return stores, {store["id"]: store for store in stores}


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


def anchor_points(store: dict) -> list[tuple[float, float]]:
    if anchors := store.get("anchors"):
        return [(a["latitude"], a["longitude"]) for a in anchors]
    return [(store["latitude"], store["longitude"])]


def store_from_gps(lat: float, lon: float, stores: list[dict] | None = None) -> dict | None:
    stores = stores or load_stores()[0]
    best: dict | None = None
    best_distance = float("inf")
    for store in stores:
        radius_m = store.get("match_radius_m", 150)
        for anchor_lat, anchor_lon in anchor_points(store):
            distance = haversine_m(lat, lon, anchor_lat, anchor_lon)
            if distance <= radius_m and distance < best_distance:
                best = store
                best_distance = distance
    return best
