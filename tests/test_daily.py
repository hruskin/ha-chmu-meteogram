"""Kdy se dá věřit dennímu souhrnu z meteogramu."""
import pytest

from chmu_meteogram.daily import covers_extremes, use_model_day


def _hours(*ranges):
    out: set[int] = set()
    for start, end in ranges:
        out |= set(range(start, end))
    return out


def test_full_day_covers_extremes():
    assert covers_extremes(_hours((0, 24)))


def test_night_only_does_not():
    """Poslední den meteogramu bývá jen pár nočních hodin."""
    assert not covers_extremes({0, 1, 2})


def test_needs_both_windows():
    assert not covers_extremes(_hours((4, 8)))    # jen ráno
    assert not covers_extremes(_hours((13, 17)))  # jen odpoledne
    assert covers_extremes({5, 14})               # po jedné hodině z každého


def test_day_starting_mid_morning_is_rejected():
    """Od 10:00 chybí ranní minimum, i když hodin je dost."""
    assert not covers_extremes(_hours((10, 24)))


def test_first_day_is_kept_even_when_truncated():
    """Dnešek ukazuje, co ze dne zbývá — bereme ho i osekaný."""
    assert use_model_day(0, {22, 23})
    assert use_model_day(0, set())


def test_later_days_must_cover_extremes():
    assert use_model_day(1, _hours((0, 24)))
    assert not use_model_day(1, {0, 1, 2})
    assert not use_model_day(3, {0, 1, 2})


@pytest.mark.parametrize("hours,expected", [
    (_hours((2, 24)), True),    # meteogram začal ve 2:00 — v pořádku
    (_hours((0, 3)), False),    # jen noc — zahodit
    (_hours((0, 18)), True),    # končí večer, extrémy má
    (_hours((0, 13)), False),   # končí před maximem
])
def test_real_coverage_patterns(hours, expected):
    assert covers_extremes(hours) is expected
