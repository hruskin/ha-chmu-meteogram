"""Targety meteogramu — buď pojmenovaný POI nebo libovolný bod."""
from __future__ import annotations

import json
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from .const import PUBLIC_URL_POI, PUBLIC_URL_POINT

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
    pool = [l for l in _LOCATIONS if l.category == category] or _LOCATIONS
    return min(pool, key=lambda loc: _haversine_km(lat, lon, loc.lat, loc.lon))


def by_id(location_id: int) -> AladinLocation | None:
    for loc in _LOCATIONS:
        if loc.id == location_id:
            return loc
    return None


# ----------------------------------------------------------------------
# WeatherTarget — abstrakce nad POI vs. bodový dotaz
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class WeatherTarget:
    """Cíl, pro který stahujeme meteogram. Buď ALADIN POI nebo bod (lat/lon)."""

    name: str          # zobrazované jméno
    lat: float
    lon: float
    poi_id: int | None  # None ⇒ bodový dotaz
    slug: str | None = None
    category: str | None = None  # jen pro POI

    @property
    def is_point(self) -> bool:
        return self.poi_id is None

    @property
    def device_identifier(self) -> str:
        """Stabilní string pro DeviceInfo.identifiers."""
        if self.poi_id is not None:
            return f"poi_{self.poi_id}"
        return f"point_{self.lat:.4f}_{self.lon:.4f}"

    @property
    def configuration_url(self) -> str:
        if self.poi_id is not None and self.slug:
            return PUBLIC_URL_POI.format(poi_id=self.poi_id, slug=self.slug)
        return PUBLIC_URL_POINT

    @property
    def model_label(self) -> str:
        if self.poi_id is not None:
            return f"ALADIN meteogram ({self.category or 'POI'})"
        return "ALADIN meteogram (point)"


def target_from_poi(loc: AladinLocation) -> WeatherTarget:
    return WeatherTarget(
        name=loc.name,
        lat=loc.lat,
        lon=loc.lon,
        poi_id=loc.id,
        slug=loc.slug,
        category=loc.category,
    )


def target_for_point(lat: float, lon: float, name: str) -> WeatherTarget:
    return WeatherTarget(name=name, lat=lat, lon=lon, poi_id=None)
