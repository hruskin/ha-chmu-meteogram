"""Desetidenní výhled ČHMÚ.

Model ALADIN počítá jen na tři dny. Delší výhled vydává ČHMÚ zvlášť — pro
celou republiku, jako min/max teplotu a slovní popis počasí. Bere se ze
serveru, který obsluhuje mobilní aplikaci Počasí ČHMÚ; přístup je anonymní,
token se vydá na požádání bez jakýchkoli údajů o uživateli.

Není to oficiálně dokumentované rozhraní, takže se s ním zachází opatrně:
výpadek nesmí ovlivnit zbytek integrace a data se berou jen jako doplněk
k prvním třem přesným dnům.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from aiohttp import ClientSession, ClientTimeout

from .const import USER_AGENT
from .net import read_limited

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=20)

BASE = "https://chmu.rails.cz/api/v1/"
_LOGIN_URL = BASE + "jwt/login"
_OUTLOOK_URL = BASE + "weather_bulletins/cr"

# Token vydrží řádově týdny; obnovujeme dřív a při 401 okamžitě.
_TOKEN_TTL = timedelta(days=7)


@dataclass
class OutlookDay:
    """Jeden den výhledu. Kromě teplot a stavu bývá zbytek prázdný."""

    day: date
    temp_min: float | None
    temp_max: float | None
    condition: str | None
    cloudiness: str | None  # „Oblačno"
    phenomenon: str | None  # „Déšť"
    released_at: datetime | None


# Jev má přednost před oblačností — „Oblačno + Bouřka" je bouřka.
_PHENOMENON_MAP = {
    "bouřka": "lightning-rainy",
    "bouřky": "lightning-rainy",
    "déšť": "rainy",
    "dešť": "rainy",
    "přeháňky": "rainy",
    "přeháňka": "rainy",
    "mrholení": "rainy",
    "sníh": "snowy",
    "sněžení": "snowy",
    "sněhové přeháňky": "snowy",
    "smíšené srážky": "snowy-rainy",
    "déšť se sněhem": "snowy-rainy",
    "mlha": "fog",
    "mlhy": "fog",
}

_CLOUDINESS_MAP = {
    "jasno": "sunny",
    "skoro jasno": "sunny",
    "polojasno": "partlycloudy",
    "oblačno": "cloudy",
    "skoro zataženo": "cloudy",
    "zataženo": "cloudy",
    "zataženo nízkou oblačností": "cloudy",
}


def _condition(cloudiness: str | None, phenomenon: str | None) -> str | None:
    """Slovní popis ČHMÚ → stav počasí v Home Assistantu."""
    if phenomenon:
        key = phenomenon.strip().lower()
        if key in _PHENOMENON_MAP:
            return _PHENOMENON_MAP[key]
        # popisy bývají složené („Déšť nebo přeháňky") — zkusíme podřetězce
        for word, cond in _PHENOMENON_MAP.items():
            if word in key:
                return cond
    if cloudiness:
        key = cloudiness.strip().lower()
        if key in _CLOUDINESS_MAP:
            return _CLOUDINESS_MAP[key]
        for word, cond in _CLOUDINESS_MAP.items():
            if word in key:
                return cond
    return None


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_day(raw: dict) -> OutlookDay | None:
    try:
        day = date.fromisoformat(str(raw["date_at"])[:10])
    except (KeyError, ValueError):
        return None
    released = None
    if raw.get("time_released"):
        try:
            released = datetime.fromisoformat(str(raw["time_released"]))
        except ValueError:
            pass
    cloudiness = raw.get("cloudiness_value") or None
    phenomenon = raw.get("phenomenon_value") or None
    return OutlookDay(
        day=day,
        temp_min=_num(raw.get("temperature_min")),
        temp_max=_num(raw.get("temperature_max")),
        condition=_condition(cloudiness, phenomenon),
        cloudiness=cloudiness,
        phenomenon=phenomenon,
        released_at=released,
    )


class OutlookClient:
    """Stahuje desetidenní výhled; sám si obstará a obnovuje token."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        self._token: str | None = None
        self._token_valid_until: datetime | None = None

    async def _login(self) -> str:
        body = {
            # Server chce identifikaci zařízení, ale nekontroluje ji — posíláme
            # náhodné id, žádné údaje o uživateli ani instalaci.
            "device": {"device_token": str(uuid.uuid4()), "platform": "android"}
        }
        async with self._session.post(
            _LOGIN_URL,
            json=body,
            headers={**self._headers, "Content-Type": "application/json"},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            payload = json.loads(await read_limited(resp))
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("přihlášení nevrátilo token")
        self._token = token
        self._token_valid_until = datetime.now() + _TOKEN_TTL
        return token

    async def _token_or_login(self) -> str:
        if self._token and self._token_valid_until and datetime.now() < self._token_valid_until:
            return self._token
        return await self._login()

    async def _fetch_raw(self, token: str) -> list | None:
        async with self._session.get(
            _OUTLOOK_URL,
            headers={**self._headers, "Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status == 401:
                return None  # token propadl
            resp.raise_for_status()
            return json.loads(await read_limited(resp))

    async def fetch(self) -> list[OutlookDay]:
        raw = await self._fetch_raw(await self._token_or_login())
        if raw is None:  # vypršel token — jednou zopakujeme s novým
            self._token = None
            raw = await self._fetch_raw(await self._login())
        if not isinstance(raw, list):
            raise RuntimeError("neočekávaný formát výhledu")
        days = [d for d in (_parse_day(item) for item in raw if isinstance(item, dict)) if d]
        days.sort(key=lambda d: d.day)
        return days
