"""Stáhne kompletní seznam ALADIN POI lokalit z data-provider.chmi.cz.

Zdroj API:
  https://data-provider.chmi.cz/api/poi/data/map/{category}/{level}
  category: obce | vodni-plochy | hory | letiste
  level:    2 | 3 | 4   (level 4 = nejdetailnější, obsahuje vše z 2 a 3)

POI vrací GeoJSON s coords v EPSG:32633 (UTM 33N). Převedeme na WGS84.

Spuštění:
    python tools/scrape_locations.py

Výstup zapíše do custom_components/chmu_meteogram/data/aladin_locations.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests
from pyproj import Transformer

API_BASE = "https://data-provider.chmi.cz/api/poi/data/map"
CATEGORIES = {
    "obce": "obec",
    "voda": "vodni-plocha",
    "lyze": "lyzarske-stredisko",
    "letiste": "letiste",
}
OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "chmu_meteogram"
    / "data"
    / "aladin_locations.json"
)

_TRANSFORMER = Transformer.from_crs("EPSG:32633", "EPSG:4326", always_xy=True)
_URL_RE = re.compile(r"^/meteogram/(\d+)-(.+)$")


def fetch_category(category: str) -> list[dict]:
    url = f"{API_BASE}/{category}/4"  # level 4 = full detail
    print(f"  GET {url}", file=sys.stderr)
    resp = requests.get(url, timeout=20, headers={"User-Agent": "ha-chmu-meteogram-scraper"})
    resp.raise_for_status()
    fc = resp.json()
    out: list[dict] = []
    for feat in fc.get("features", []):
        props = feat.get("properties", {})
        url_attr = props.get("url", "")
        m = _URL_RE.match(url_attr)
        if not m:
            continue
        poi_id = int(m.group(1))
        slug = m.group(2)
        x, y = feat["geometry"]["coordinates"]
        lon, lat = _TRANSFORMER.transform(x, y)
        out.append(
            {
                "id": poi_id,
                "slug": slug,
                "name": props.get("name", slug),
                "category": CATEGORIES[category],
                "lat": round(lat, 5),
                "lon": round(lon, 5),
            }
        )
    return out


def main() -> int:
    print("Stahuji POI z data-provider.chmi.cz ...", file=sys.stderr)
    locations: dict[int, dict] = {}
    for cat in CATEGORIES:
        for loc in fetch_category(cat):
            # POI ID je unikátní napříč kategoriemi; uchováme první výskyt
            locations.setdefault(loc["id"], loc)
    sorted_locs = sorted(locations.values(), key=lambda l: l["id"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "_source": "https://data-provider.chmi.cz/api/poi/data/map/{category}/4",
                "_coord_system": "WGS84 (převedeno z EPSG:32633)",
                "locations": sorted_locs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Zapsáno {len(sorted_locs)} lokalit -> {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
