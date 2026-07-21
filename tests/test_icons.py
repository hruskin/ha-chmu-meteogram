"""Testy dekódování ČHMÚ ikonového kódu na HA condition."""
import pytest

from chmu_meteogram import icons


@pytest.mark.parametrize(
    "icon,prec,snow,expected",
    [
        # potvrzeno na živých datech (Brno) — viz README
        (110, 0, 0, "clear-night"),   # jasná noc
        (10, 0, 0, "sunny"),          # jasno den
        (20, 0, 0, "partlycloudy"),   # skoro jasno
        (40, 0, 0, "partlycloudy"),   # polojasno
        (60, 0, 0, "cloudy"),         # oblačno
        (70, 0, 0, "cloudy"),         # skoro zataženo
        (80, 0, 0, "cloudy"),         # zataženo
        (120, 0, 0, "partlycloudy"),  # noční skoro jasno
        (160, 0, 0, "cloudy"),        # noční oblačno
        # srážky
        (81, 2.6, 0, "pouring"),      # zataženo + vydatný déšť
        (171, 0.2, 0, "rainy"),       # noční skoro zataženo + slabý déšť
        (41, 0.5, 0, "rainy"),        # polojasno + déšť
        # sníh a břečka
        (81, 0.1, 0.1, "snowy"),      # sníh
        (81, 1.0, 0.1, "snowy-rainy"),  # břečka (prec > 2*snow)
        # bouřky
        (90, 0, 0, "lightning"),
        (91, 5.0, 0, "lightning-rainy"),
        (190, 0, 0, "lightning"),     # noční bouřka
    ],
)
def test_condition(icon, prec, snow, expected):
    assert icons.condition(icon, prec, snow) == expected


def test_condition_none():
    assert icons.condition(None) is None


def test_pouring_threshold():
    assert icons.condition(81, 1.9, 0) == "rainy"
    assert icons.condition(81, 2.0, 0) == "pouring"


def test_label_czech():
    assert icons.label(110) == "Jasná noc"
    assert icons.label(90) == "Bouřky"
    assert icons.label(None) is None
