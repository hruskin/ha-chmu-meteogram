"""Testy určení ORP z bodu (point-in-polygon nad ČÚZK hranicemi)."""
import pytest

from chmu_meteogram import orp


@pytest.mark.parametrize(
    "lat,lon,name,region",
    [
        (49.1951, 16.6068, "Brno", "CZ064"),
        (50.0880, 14.4260, "Hlavní město Praha", "CZ090"),
        (49.7475, 13.3776, "Plzeň", "CZ032"),
        (49.8209, 18.2625, "Ostrava", "CZ080"),
        (48.9745, 14.4744, "České Budějovice", "CZ031"),
    ],
)
def test_find_known_cities(lat, lon, name, region):
    found = orp.find(lat, lon)
    assert found is not None
    assert found.name == name
    assert found.region == region


def test_praha_is_cz090_not_cz010():
    """RÚIAN má Prahu jako CZ010, ČHMÚ používá CZ090 — musí být přemapováno."""
    found = orp.find(50.0880, 14.4260)
    assert found.region == "CZ090"


def test_small_village_maps_to_orp():
    """Malá obec bez vlastního ORP spadne pod spádové ORP."""
    found = orp.find(49.9310, 14.5483)  # Křížkový Újezdec
    assert found is not None
    assert found.name == "Říčany"
    assert found.region == "CZ020"


def test_outside_cr_returns_none():
    assert orp.find(48.2082, 16.3738) is None  # Vídeň


def test_nearest_fallback_never_none_inside_bbox():
    found = orp.nearest(49.9310, 14.5483)
    assert found is not None


def test_all_206_orps_loaded():
    assert len(orp._shapes()) == 206
