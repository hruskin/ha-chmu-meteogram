"""Testy parsování meteogram bodu a výběru lokality."""
from datetime import timezone

from chmu_meteogram.chmu_client import MeteogramPoint
from chmu_meteogram.locations import by_id, nearest, target_for_point, target_from_poi


def test_meteogram_point_from_api():
    raw = {
        "validityTime": "2026-07-17T06:00:00+00:00",
        "t2m": 22.2,
        "rh2m": 55.0,
        "prec": 0.0,
        "snow": 0.0,
        "windSpeed": 2.4,
        "windGustSpeed": 5.1,
        "windDirection": 300,
        "mslp": 1012.0,
        "cloudsTot": 57,
        "icon": 60,
    }
    p = MeteogramPoint.from_api(raw)
    assert p.temperature == 22.2
    assert p.humidity == 55.0
    assert p.pressure == 1012.0
    assert p.clouds == 57
    assert p.icon == 60
    assert p.time.tzinfo is not None
    assert p.time.astimezone(timezone.utc).hour == 6


def test_meteogram_point_handles_missing():
    p = MeteogramPoint.from_api({"validityTime": "2026-07-17T06:00:00+00:00"})
    assert p.temperature is None
    assert p.icon is None


def test_nearest_obec_from_home():
    # Brno souřadnice → nejbližší obec Brno
    loc = nearest(49.1951, 16.6068)
    assert loc.category == "obec"
    assert loc.name == "Brno"


def test_target_from_poi_is_not_point():
    tgt = target_from_poi(by_id(25))  # Brno
    assert not tgt.is_point
    assert tgt.poi_id == 25


def test_target_for_point_is_point():
    tgt = target_for_point(49.93, 14.55, "Domov")
    assert tgt.is_point
    assert tgt.poi_id is None
    assert tgt.device_identifier.startswith("point_")
