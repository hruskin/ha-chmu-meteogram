"""Testy desetidenního výhledu — mapování stavu a parsování dne."""
from datetime import date

import pytest

from chmu_meteogram.outlook import OutlookDay, _condition, _parse_day


@pytest.mark.parametrize(
    "cloudiness,phenomenon,expected",
    [
        # kombinace ověřené na živých datech
        ("Polojasno", None, "partlycloudy"),
        ("Oblačno", None, "cloudy"),
        ("Polojasno", "Déšť", "rainy"),
        ("Oblačno", "Déšť", "rainy"),
        ("Oblačno", "Bouřka", "lightning-rainy"),
        # jev má přednost před oblačností
        ("Jasno", "Bouřka", "lightning-rainy"),
        ("Zataženo", "Sníh", "snowy"),
        # samotná oblačnost
        ("Jasno", None, "sunny"),
        ("Zataženo", None, "cloudy"),
    ],
)
def test_condition_mapping(cloudiness, phenomenon, expected):
    assert _condition(cloudiness, phenomenon) == expected


def test_condition_matches_composite_wording():
    """ČHMÚ píše i složené popisy — musí se poznat podle podřetězce."""
    assert _condition("Oblačno", "Déšť nebo přeháňky") == "rainy"
    assert _condition("Skoro zataženo, místy mlhy", None) == "cloudy"


def test_condition_unknown_is_none():
    assert _condition(None, None) is None
    assert _condition("Něco neznámého", "Také neznámé") is None


def test_parse_day_full():
    day = _parse_day(
        {
            "date_at": "2026-08-07",
            "temperature_min": 17.0,
            "temperature_max": 27.0,
            "cloudiness_value": "Oblačno",
            "phenomenon_value": "Déšť",
            "time_released": "2026-08-02T12:00:00+02:00",
        }
    )
    assert day == OutlookDay(
        day=date(2026, 8, 7),
        temp_min=17.0,
        temp_max=27.0,
        condition="rainy",
        cloudiness="Oblačno",
        phenomenon="Déšť",
        released_at=day.released_at,
    )
    assert day.released_at.year == 2026


def test_parse_day_tolerates_missing_fields():
    """Vítr, srážky ani pocitová teplota ve výhledu většinou nejsou."""
    day = _parse_day({"date_at": "2026-08-07", "temperature_max": 20})
    assert day is not None
    assert day.temp_min is None
    assert day.temp_max == 20.0
    assert day.condition is None


def test_parse_day_rejects_broken_input():
    assert _parse_day({}) is None
    assert _parse_day({"date_at": "nesmysl"}) is None


def test_parse_day_survives_bad_release_time():
    day = _parse_day({"date_at": "2026-08-07", "time_released": "rozbité"})
    assert day is not None
    assert day.released_at is None
