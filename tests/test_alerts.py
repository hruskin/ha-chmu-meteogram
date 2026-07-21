"""Testy párování výstrah na ORP/kraj a filtrů (nad syntetickou fixture)."""
import json
from pathlib import Path

import pytest

from chmu_meteogram.chmu_client import _match_alerts
from chmu_meteogram.orp import Orp

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "alerts_sample.json").read_text(encoding="utf-8")
)


def _match(orp_name: str, region: str):
    return _match_alerts(_FIXTURE, Orp(name=orp_name, region=region))


def test_brno_gets_heat_and_thunderstorm():
    result = _match("Brno", "CZ064")
    cats = {a.category for a in result.items}
    assert "heat" in cats          # subarea match (Brno je v subareas)
    assert "thunderstorms" in cats  # whole_area match
    assert result.area == "Jihomoravský kraj"


def test_severity_sorting_worst_first():
    result = _match("Brno", "CZ064")
    # Severe (thunderstorms) musí být před Moderate (heat)
    assert result.items[0].severity == "Severe"
    assert result.worst_severity == "Severe"


def test_praha_only_thunderstorm_not_heat():
    """Praha není v subareas heat výstrahy → dostane jen celokrajskou bouřku."""
    result = _match("Hlavní město Praha", "CZ090")
    cats = {a.category for a in result.items}
    assert cats == {"thunderstorms"}


def test_orp_not_in_subareas_skips_heat():
    """ORP ve správném kraji, ale ne v subareas heat → heat nedostane."""
    result = _match("Boskovice", "CZ064")  # není v subareas [Blansko, Brno]
    cats = {a.category for a in result.items}
    assert "heat" not in cats
    assert "thunderstorms" in cats  # whole_area platí pro celý kraj


def test_minor_without_text_filtered():
    result = _match("Brno", "CZ064")
    assert all(a.category != "wind" for a in result.items)


def test_expired_alert_filtered():
    result = _match("Brno", "CZ064")
    assert all(a.category != "rain" for a in result.items)


def test_cancellation_filtered():
    result = _match("Brno", "CZ064")
    assert all(a.category != "snow" for a in result.items)


def test_air_quality_and_outlook_skipped():
    result = _match("Brno", "CZ064")
    cats = {a.category for a in result.items}
    assert "ozone" not in cats
    assert "outlook" not in cats


def test_other_region_gets_nothing():
    result = _match("Cheb", "CZ041")
    assert result.items == []
    assert not result.is_active


def test_labels_and_icons_present():
    result = _match("Brno", "CZ064")
    thunder = next(a for a in result.items if a.category == "thunderstorms")
    assert thunder.label == "Bouřky"
    assert thunder.icon == "mdi:weather-lightning"
