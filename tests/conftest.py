"""Test setup — umožní importovat moduly integrace bez instalace Home Assistantu.

Balíček `chmu_meteogram/__init__.py` importuje homeassistant, což v prostém
pytestu není. Zaregistrujeme proto stub balíček, který ukazuje na složku
integrace, ale nespouští její __init__.py. Relativní importy uvnitř modulů
(`from . import orp`) pak fungují a čistě-logické moduly (icons, orp,
locations, chmu_client parsing) jde testovat izolovaně.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "chmu_meteogram"

if "chmu_meteogram" not in sys.modules:
    pkg = types.ModuleType("chmu_meteogram")
    pkg.__path__ = [str(_PKG_DIR)]
    sys.modules["chmu_meteogram"] = pkg
