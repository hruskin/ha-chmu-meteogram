"""Určení ORP (správního obvodu obce s rozšířenou působností) pro bod.

Výstrahy ČHMÚ jsou členěné po krajích a ORP, takže pro spárování výstrahy
s lokalitou potřebujeme vědět, ve kterém ORP bod leží.

Hranice pocházejí z RÚIAN (ČÚZK, CC-BY 4.0) a jsou přibalené zjednodušené
v `data/orp_boundaries.json` — viz `tools/fetch_orp_boundaries.py`.

Point-in-polygon je čistě v Pythonu (ray casting, even-odd), aby integrace
neměla žádné závislosti navíc.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "orp_boundaries.json"


@dataclass(frozen=True)
class Orp:
    name: str      # název ORP, např. "Brno" (shoduje se s názvy v alerts.json)
    region: str    # kód kraje dle ČHMÚ, např. "CZ064" (Praha je CZ090)


@dataclass(frozen=True)
class _OrpShape:
    name: str
    region: str
    bbox: tuple[float, float, float, float]  # minlon, minlat, maxlon, maxlat
    rings: tuple[tuple[float, ...], ...]     # ploché [lon, lat, lon, lat, ...]


@lru_cache(maxsize=1)
def _shapes() -> tuple[_OrpShape, ...]:
    """Načte a nakešuje hranice. Volá se až při první potřebě (~0,5 MB JSON)."""
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return tuple(
        _OrpShape(
            name=o["name"],
            region=o["region"],
            bbox=tuple(o["bbox"]),
            rings=tuple(tuple(r) for r in o["rings"]),
        )
        for o in raw["orps"]
    )


def _ring_crossings(ring: tuple[float, ...], lon: float, lat: float) -> int:
    """Počet průsečíků paprsku (směr +lon) s prstencem."""
    crossings = 0
    n = len(ring) // 2
    j = n - 1
    for i in range(n):
        xi, yi = ring[2 * i], ring[2 * i + 1]
        xj, yj = ring[2 * j], ring[2 * j + 1]
        if (yi > lat) != (yj > lat):
            x_at = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at:
                crossings += 1
        j = i
    return crossings


def _contains(shape: _OrpShape, lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = shape.bbox
    if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
        return False
    # even-odd napříč všemi prstenci — správně řeší i díry a exklávy
    total = sum(_ring_crossings(r, lon, lat) for r in shape.rings)
    return total % 2 == 1


def find(lat: float, lon: float) -> Orp | None:
    """Vrátí ORP, ve kterém bod leží, nebo None (mimo ČR)."""
    for s in _shapes():
        if _contains(s, lon, lat):
            return Orp(name=s.name, region=s.region)
    return None


def nearest(lat: float, lon: float) -> Orp | None:
    """Nejbližší ORP podle středu bbox — fallback pro body těsně za hranicí.

    Zjednodušené polygony mohou u hranic o stovky metrů „ukrojit", takže
    když `find` nic nenajde, nabídneme nejbližší ORP.
    """
    shapes = _shapes()
    if not shapes:
        return None
    best = min(
        shapes,
        key=lambda s: ((s.bbox[0] + s.bbox[2]) / 2 - lon) ** 2
        + ((s.bbox[1] + s.bbox[3]) / 2 - lat) ** 2,
    )
    return Orp(name=best.name, region=best.region)


def find_or_nearest(lat: float, lon: float) -> Orp | None:
    return find(lat, lon) or nearest(lat, lon)
