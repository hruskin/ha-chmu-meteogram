"""Překlad ČHMÚ ikonového kódu na Home Assistant weather condition.

Číselník ČHMÚ (odvozeno empiricky z dat ALADIN meteogramu):
  desítky = oblačnost: 1 jasno, 2 skoro jasno, 4 polojasno,
            6 oblačno, 7 skoro zataženo, 8 zataženo, 9 bouřky
  jednotky = srážky: 0 beze srážek, ≥1 srážky (typ podle prec/snow)
  +100     = noční varianta

HA condition slugs viz https://www.home-assistant.io/integrations/weather/
"""
from __future__ import annotations

# práh mm/h, nad kterým je z „rainy" „pouring"
_POURING_MM = 2.0
# minimální množství sněhu, aby se srážka počítala jako sníh / břečka
_SNOW_MIN = 0.02


def _precip_kind(prec: float, snow: float) -> str:
    """rain | snow | sleet z množství srážek a sněhu."""
    if snow > _SNOW_MIN and prec > snow * 2:
        return "sleet"
    if snow > _SNOW_MIN:
        return "snow"
    return "rain"


def condition(icon: int | None, prec: float | None = None, snow: float | None = None) -> str | None:
    """Vrátí HA weather condition, nebo None když ikona chybí."""
    if icon is None:
        return None
    prec = prec or 0.0
    snow = snow or 0.0

    night = icon >= 100
    base = icon % 100
    tens = base // 10
    wet = base % 10 >= 1

    # bouřky mají přednost
    if tens == 9:
        return "lightning-rainy" if wet else "lightning"

    if wet:
        kind = _precip_kind(prec, snow)
        if kind == "snow":
            return "snowy"
        if kind == "sleet":
            return "snowy-rainy"
        return "pouring" if prec >= _POURING_MM else "rainy"

    # beze srážek — jen oblačnost
    if tens <= 1:
        return "clear-night" if night else "sunny"
    if tens <= 4:
        return "partlycloudy"
    return "cloudy"


# Český popisek pro atributy / karty
_LABELS = {
    "sunny": "Jasno",
    "clear-night": "Jasná noc",
    "partlycloudy": "Polojasno",
    "cloudy": "Oblačno",
    "rainy": "Déšť",
    "pouring": "Vydatný déšť",
    "snowy": "Sněžení",
    "snowy-rainy": "Smíšené srážky",
    "lightning": "Bouřky",
    "lightning-rainy": "Bouřky s deštěm",
    "fog": "Mlha",
}


def label(icon: int | None, prec: float | None = None, snow: float | None = None) -> str | None:
    cond = condition(icon, prec, snow)
    return _LABELS.get(cond) if cond else None
