"""Stáhne hranice ORP z ČÚZK a vyrobí kompaktní JSON pro integraci.

Zdroj: https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip (RÚIAN, celý stát,
S-JTSK / Krovak East North = EPSG:5514). Licence CC-BY 4.0.
Bereme jen vrstvu ORP_P (206 správních obvodů ORP).

Výstup: custom_components/chmu_meteogram/data/orp_boundaries.json
  {
    "_source": ..., "_license": ...,
    "orps": [
      {"name": "Brno", "region": "CZ064", "bbox": [minlon, minlat, maxlon, maxlat],
       "rings": [[lon, lat, lon, lat, ...], ...]},
      ...
    ]
  }

Souřadnice: WGS84, zaokrouhlené na 4 desetinná místa (~11 m).
Polygony zjednodušené Douglas-Peuckerem — pro výstrahy stačí hrubá přesnost.

Závislosti (jen pro tento skript, integrace je bez requirements):
    pip install pyshp pyproj

Spuštění:
    python tools/fetch_orp_boundaries.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import shapefile
from pyproj import Transformer

CUZK_URL = "https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip"
SHP_PREFIX = "1/ORP_P"
SHP_PARTS = (".shp", ".shx", ".dbf", ".prj", ".cpg")

OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "chmu_meteogram"
    / "data"
    / "orp_boundaries.json"
)

# ČHMÚ používá pro Prahu CZ090, zatímco RÚIAN/NUTS3 má CZ010.
REGION_FIXUP = {"CZ010": "CZ090"}

# Tolerance zjednodušení ve stupních (~0.002° ≈ 200 m). Výstrahy jsou regionální,
# takže i několikasetmetrová nepřesnost hranice je bez dopadu.
SIMPLIFY_TOLERANCE = 0.002
COORD_PRECISION = 4

_TRANSFORMER = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)


def _download(dest: Path) -> Path:
    zip_path = dest / "cuzk_stat.zip"
    if zip_path.exists():
        print(f"  (používám cache {zip_path})", file=sys.stderr)
        return zip_path
    print(f"  stahuji {CUZK_URL} (~240 MB, chvíli to trvá) ...", file=sys.stderr)
    req = urllib.request.Request(CUZK_URL, headers={"User-Agent": "ha-chmu-meteogram-scraper"})
    with urllib.request.urlopen(req, timeout=600) as resp, zip_path.open("wb") as f:
        shutil.copyfileobj(resp, f)
    print(f"  staženo: {zip_path.stat().st_size / 1024 / 1024:.0f} MB", file=sys.stderr)
    return zip_path


def _extract(zip_path: Path, dest: Path) -> Path:
    with zipfile.ZipFile(zip_path) as z:
        for ext in SHP_PARTS:
            name = SHP_PREFIX + ext
            try:
                with z.open(name) as src, (dest / f"ORP_P{ext}").open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            except KeyError:
                if ext in (".shp", ".shx", ".dbf"):
                    raise
    return dest / "ORP_P"


def _perp_distance(pt, a, b) -> float:
    """Kolmá vzdálenost bodu pt od úsečky a-b (v rovině stupňů — pro DP stačí)."""
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _douglas_peucker(points: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Iterativní Douglas-Peucker (bez rekurze — prstence mají desítky tisíc bodů)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        far_i, far_d = -1, 0.0
        a, b = points[lo], points[hi]
        for i in range(lo + 1, hi):
            d = _perp_distance(points[i], a, b)
            if d > far_d:
                far_i, far_d = i, d
        if far_d > tol:
            keep[far_i] = True
            stack.append((lo, far_i))
            stack.append((far_i, hi))
    return [p for p, k in zip(points, keep) if k]


def _rings(shape) -> list[list[tuple[float, float]]]:
    """Rozdělí shapefile geometrii na prstence (vnější i díry)."""
    parts = list(shape.parts) + [len(shape.points)]
    out = []
    for i in range(len(parts) - 1):
        ring = shape.points[parts[i] : parts[i + 1]]
        if len(ring) >= 4:
            out.append(ring)
    return out


def main() -> int:
    tmp = Path(tempfile.gettempdir()) / "ha-chmu-orp"
    tmp.mkdir(parents=True, exist_ok=True)

    print("ORP hranice z ČÚZK", file=sys.stderr)
    zip_path = _download(tmp)
    shp_base = _extract(zip_path, tmp)

    reader = shapefile.Reader(str(shp_base), encoding="cp1250")
    fields = [f[0] for f in reader.fields[1:]]
    print(f"  ORP ve vrstvě: {len(reader)}", file=sys.stderr)

    orps = []
    pts_before = pts_after = 0
    for i in range(len(reader)):
        rec = dict(zip(fields, reader.record(i)))
        shape = reader.shape(i)
        region = REGION_FIXUP.get(rec["NUTS3_KOD"], rec["NUTS3_KOD"])

        rings_out: list[list[float]] = []
        min_lon = min_lat = 1e9
        max_lon = max_lat = -1e9
        for ring in _rings(shape):
            wgs = [_TRANSFORMER.transform(x, y) for x, y in ring]
            pts_before += len(wgs)
            simple = _douglas_peucker(wgs, SIMPLIFY_TOLERANCE)
            if len(simple) < 4:
                continue
            pts_after += len(simple)
            flat: list[float] = []
            for lon, lat in simple:
                lon = round(lon, COORD_PRECISION)
                lat = round(lat, COORD_PRECISION)
                flat.extend((lon, lat))
                min_lon, max_lon = min(min_lon, lon), max(max_lon, lon)
                min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)
            rings_out.append(flat)

        if not rings_out:
            print(f"  ! {rec['NAZEV']}: žádný prstenec po zjednodušení", file=sys.stderr)
            continue

        orps.append(
            {
                "name": rec["NAZEV"],
                "region": region,
                "bbox": [min_lon, min_lat, max_lon, max_lat],
                "rings": rings_out,
            }
        )

    orps.sort(key=lambda o: o["name"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "_source": CUZK_URL,
                "_layer": "ORP_P (RÚIAN, správní obvody ORP)",
                "_license": "CC-BY 4.0, © ČÚZK",
                "_note": (
                    "Zjednodušeno Douglas-Peuckerem, tolerance "
                    f"{SIMPLIFY_TOLERANCE}° (~200 m). Praha přemapována z NUTS3 "
                    "CZ010 na ČHMÚ CZ090. Souřadnice WGS84."
                ),
                "orps": orps,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(
        f"  body: {pts_before} → {pts_after} "
        f"({100 * pts_after / max(pts_before, 1):.1f} %)",
        file=sys.stderr,
    )
    print(f"Zapsáno {len(orps)} ORP → {OUT_PATH} ({size_kb:.0f} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
