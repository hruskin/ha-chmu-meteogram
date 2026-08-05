"""Pravidla pro sestavení denní předpovědi.

Meteogram je řada 73 hodin od svého vydání, takže krajní dny jsou neúplné:

* **první** je oříznutý zepředu — začíná hodinou vydání
* **poslední** je oříznutý zezadu — začíná o půlnoci a končí předčasně

Model se vydává čtyřikrát denně, takže poslední den vyjde na 3, 9, 15 nebo
21 hodin. Denní maximum nastává odpoledne, obvykle mezi 14. a 16. hodinou,
takže i patnáctihodinový den (do 14:00) by ho podcenil. Bereme proto jen dny
prakticky celé.

Rozhodnutí drží stranou od Home Assistantu, aby šlo testovat samostatně.
"""
from __future__ import annotations

# Kolik hodin musí den mít, aby se z něj daly počítat denní extrémy.
# Odpovídá poslednímu dni při vydání ve 20:00 (00:00–20:00).
MIN_MODEL_HOURS = 21


def use_model_day(index: int, hours: set[int]) -> bool:
    """Má se pro tento den použít meteogram, nebo ho přenechat výhledu?

    První den bereme i osekaný — ukazuje, co ze dne ještě zbývá, a to je
    užitečnější než celodenní hodnota odjinud.
    """
    return index == 0 or len(hours) >= MIN_MODEL_HOURS
