"""Kdy se dá věřit dennímu souhrnu z meteogramu."""
import pytest

from chmu_meteogram.daily import MIN_MODEL_HOURS, use_model_day


def _hours(start: int, end: int) -> set[int]:
    return set(range(start, end))


@pytest.mark.parametrize("length,expected", [
    (3, False),   # vydání ve 02:00 — jen noc
    (9, False),   # vydání v 08:00 — chybí odpoledne
    (15, False),  # vydání ve 14:00 — končí před denním maximem
    (21, True),   # vydání ve 20:00
])
def test_real_last_day_shapes(length, expected):
    """Poslední den je oříznutý zezadu; model se vydává 4x denně."""
    assert use_model_day(1, _hours(0, length)) is expected


def test_full_day_is_used():
    assert use_model_day(1, _hours(0, 24))


def test_first_day_is_kept_even_when_truncated():
    """Dnešek ukazuje, co ze dne zbývá — bereme ho i osekaný."""
    assert use_model_day(0, {22, 23})
    assert use_model_day(0, set())


def test_threshold_boundary():
    assert not use_model_day(1, _hours(0, MIN_MODEL_HOURS - 1))
    assert use_model_day(1, _hours(0, MIN_MODEL_HOURS))


def test_applies_to_every_later_day():
    for index in (1, 2, 3):
        assert not use_model_day(index, {0, 1, 2})
