"""Jednorázový scraper seznamu ALADIN meteogram lokalit z chmi.cz.

Použití:
    python tools/scrape_locations.py > custom_components/chmu_meteogram/data/aladin_locations.json

TODO: implementace — projít stránky:
  - https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/obce
  - https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/hory
  - https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/vodni-plochy
  - https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/letiste
a vyextrahovat (id, název, lat, lon). Souřadnice pravděpodobně chybí v HTML
a bude třeba je doplnit reverzním geocodingem (Nominatim, offline gazetteer).
"""
from __future__ import annotations

import sys


def main() -> int:
    print("scraper neimplementován — viz docstring", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
