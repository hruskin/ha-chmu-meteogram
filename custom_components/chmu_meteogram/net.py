"""Bezpečnostní pojistky pro stahování dat.

Data ČHMÚ jsou důvěryhodná a chodí přes HTTPS, ale integrace je parsuje
vlastními parsery (PNG, tar). Kdyby server odpověděl něčím nečekaně velkým
(chyba na jejich straně, přesměrování jinam, kompromitace), neomezené čtení
do paměti by mohlo shodit celý Home Assistant. Proto se všechno stahuje
s limitem.
"""
from __future__ import annotations

from aiohttp import ClientResponse

# Reálné velikosti: meteogram JSON ~15 kB, alerts.json ~110 kB,
# radarový snímek ~25 kB, tar s předpovědí ~100 kB. Limit je řádově výš.
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024


class ResponseTooLarge(ValueError):
    """Odpověď překročila povolenou velikost."""


_CHUNK = 64 * 1024


async def read_limited(
    resp: ClientResponse, max_bytes: int = MAX_DOWNLOAD_BYTES
) -> bytes:
    """Načte celé tělo odpovědi, ale nikdy víc než `max_bytes`.

    Čte po blocích a průběžně kontroluje součet — deklarovaná délka slouží
    jen jako rychlá zkratka, spoléhat se na ni nelze. (Pozor: jedno volání
    `content.read(n)` vrátí jen právě dostupný blok, ne celých `n` bajtů.)
    """
    declared = resp.content_length
    if declared is not None and declared > max_bytes:
        raise ResponseTooLarge(
            f"{resp.url}: deklarováno {declared} B, limit {max_bytes} B"
        )
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.content.iter_chunked(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLarge(f"{resp.url}: přes {max_bytes} B")
        chunks.append(chunk)
    return b"".join(chunks)
