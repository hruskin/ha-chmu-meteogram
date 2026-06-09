"""HTTP klient pro data-provider.chmi.cz (JSON meteogram + výstrahy)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import ALERT_URL, ALERT_URL_ALL, METEOGRAM_URL, USER_AGENT

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=20)


@dataclass
class MeteogramPoint:
    time: datetime  # validityTime, UTC
    temperature: float | None  # °C
    humidity: float | None  # %
    precipitation: float | None  # mm/h
    snow: float | None  # mm/h
    wind_speed: float | None  # m/s
    wind_gust: float | None  # m/s
    wind_direction: float | None  # °
    pressure: float | None  # hPa (MSLP)
    clouds: float | None  # %
    icon: int | None  # ČHMÚ ikona

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "MeteogramPoint":
        return cls(
            time=_parse_dt(raw["validityTime"]),
            temperature=_num(raw.get("t2m")),
            humidity=_num(raw.get("rh2m")),
            precipitation=_num(raw.get("prec")),
            snow=_num(raw.get("snow")),
            wind_speed=_num(raw.get("windSpeed")),
            wind_gust=_num(raw.get("windGustSpeed")),
            wind_direction=_num(raw.get("windDirection")),
            pressure=_num(raw.get("mslp")),
            clouds=_num(raw.get("cloudsTot")),
            icon=_int(raw.get("icon")),
        )


@dataclass
class Meteogram:
    points: list[MeteogramPoint]
    elevation_m: int | None
    parameters: dict[str, dict[str, str]]  # raw definitions
    fetched_at: datetime


@dataclass
class Alert:
    is_warning: bool
    description: str
    details: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_warning": self.is_warning,
            "description": self.description,
            "details": self.details,
        }


class ChmuClient:
    """Tenký asynchronní klient pro veřejná JSON data ČHMÚ."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async def fetch_meteogram(self, poi_id: int) -> Meteogram:
        url = METEOGRAM_URL.format(poi_id=poi_id)
        async with self._session.get(url, headers=self._headers, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
        points = [MeteogramPoint.from_api(item) for item in payload.get("data", [])]
        return Meteogram(
            points=points,
            elevation_m=_int(payload.get("z")),
            parameters=payload.get("parameters") or {},
            fetched_at=datetime.now().astimezone(),
        )

    async def fetch_alert(self, poi_id: int) -> Alert:
        # Krátký endpoint: stav výstrah ano/ne + popis
        async with self._session.get(
            ALERT_URL,
            params={"poiId": poi_id},
            headers=self._headers,
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        is_warning = bool(data.get("isWarning"))
        description = data.get("description") or ""

        details: list[dict[str, Any]] = []
        if is_warning:
            # Detail kompletního CAP záznamu (může vrátit i mapový PNG v base64)
            try:
                async with self._session.get(
                    ALERT_URL_ALL,
                    params={"poiId": poi_id},
                    headers=self._headers,
                    timeout=_TIMEOUT,
                ) as resp2:
                    if resp2.status == 200:
                        full = await resp2.json(content_type=None)
                        # ČHMÚ vrací různý formát; pokud najdeme pole "warnings"
                        # nebo "items", uložíme jen textové části (vynecháme base64 obrázek)
                        warns = full.get("warnings") or full.get("items") or []
                        if isinstance(warns, list):
                            details = [_strip_binary(w) for w in warns if isinstance(w, dict)]
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Detail výstrah selhal: %s", err)

        return Alert(is_warning=is_warning, description=description, details=details)


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _strip_binary(d: dict[str, Any]) -> dict[str, Any]:
    """Z odpovědi odstraní pole, která vypadají jako base64 binární data."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > 2000:
            continue
        out[k] = v
    return out
