"""Pravidla pro sestavení denní předpovědi.

Meteogram končí uprostřed dne, takže jeho poslední den bývá jen pár hodin —
z nich by denní minimum a maximum vyšlo úplně mimo. Tady je rozhodnutí, kdy
se dá dni z modelu věřit; drží se stranou od Home Assistantu, aby šlo
testovat samostatně.
"""
from __future__ import annotations

# Hodiny, ve kterých denní extrémy nastávají. Bez nich není z čeho počítat.
MIN_WINDOW = frozenset(range(4, 8))    # ranní minimum
MAX_WINDOW = frozenset(range(13, 17))  # odpolední maximum


def covers_extremes(hours: set[int]) -> bool:
    """Obsahuje den hodiny, ze kterých lze určit minimum i maximum?"""
    return bool(hours & MIN_WINDOW) and bool(hours & MAX_WINDOW)


def use_model_day(index: int, hours: set[int]) -> bool:
    """Má se pro tento den použít meteogram, nebo ho přenechat výhledu?

    První den bereme i osekaný — ukazuje, co ze dne ještě zbývá, a to je
    užitečnější než celodenní průměr odjinud.
    """
    return index == 0 or covers_extremes(hours)
