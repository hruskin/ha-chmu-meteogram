"""Vyhledávač nejbližší ALADIN POI lokality."""
from __future__ import annotations

import json
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "aladin_locations.json"


@dataclass(frozen=True)
class AladinLocation:
    id: int
    slug: str
    name: str
    category: str  # obec | vodni-plocha | lyzarske-stredisko | letiste
    lat: float
    lon: float


def _load() -> list[AladinLocation]:
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return [AladinLocation(**loc) for loc in raw["locations"]]


_LOCATIONS: list[AladinLocation] = _load()


def all_locations() -> list[AladinLocation]:
    return list(_LOCATIONS)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest(lat: float, lon: float, category: str = "obec") -> AladinLocation:
    """Najde nejbližší POI dané kategorie. Defaultně obec."""
    pool = [l for l in _LOCATIONS if l.category == category] or _LOCATIONS
    return min(pool, key=lambda loc: _haversine_km(lat, lon, loc.lat, loc.lon))


def by_id(location_id: int) -> AladinLocation | None:
    for loc in _LOCATIONS:
        if loc.id == location_id:
            return loc
    return None
