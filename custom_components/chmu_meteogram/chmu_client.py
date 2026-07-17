"""HTTP klient pro data ČHMÚ (JSON meteogram + výstrahy)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from . import orp as orp_lookup
from .const import (
    ALERT_CATEGORY_ICONS,
    ALERT_CATEGORY_LABELS,
    ALERT_FALLBACK_ICON,
    ALERT_REGION_PREFIX,
    ALERT_SKIP_CATEGORIES,
    ALERTS_URL,
    METEOGRAM_URL_POI,
    METEOGRAM_URL_POINT,
    SEVERITY_ORDER,
    USER_AGENT,
)
from .locations import WeatherTarget

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
    icon: int | None

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
    parameters: dict[str, dict[str, str]]
    fetched_at: datetime


@dataclass
class AlertItem:
    category: str      # heat, wind, thunderstorms…
    phenomenon: str
    description: str
    instruction: str
    severity: str      # Minor | Moderate | Severe | Extreme
    certainty: str
    start: datetime | None
    end: datetime | None

    @property
    def label(self) -> str:
        """Čitelný název, např. „Zátěž teplem"."""
        return ALERT_CATEGORY_LABELS.get(self.category) or self.category

    @property
    def icon(self) -> str:
        return ALERT_CATEGORY_ICONS.get(self.category, ALERT_FALLBACK_ICON)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "icon": self.icon,
            "category": self.category,
            "phenomenon": self.phenomenon,
            "description": self.description,
            "instruction": self.instruction,
            "severity": self.severity,
            "certainty": self.certainty,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }


@dataclass
class Alerts:
    items: list[AlertItem] = field(default_factory=list)
    orp: str | None = None     # název ORP, do kterého lokalita spadá
    region: str | None = None  # kód kraje (CZ0xx)
    area: str | None = None    # název kraje z dat ČHMÚ

    @property
    def is_active(self) -> bool:
        return bool(self.items)

    @property
    def worst(self) -> AlertItem | None:
        if not self.items:
            return None
        return min(self.items, key=lambda a: SEVERITY_ORDER.get(a.severity, 99))

    @property
    def worst_severity(self) -> str | None:
        worst = self.worst
        return worst.severity if worst else None


class ChmuClient:
    """Tenký asynchronní klient pro veřejná data ČHMÚ."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async def fetch_meteogram(self, target: WeatherTarget) -> Meteogram:
        if target.is_point:
            url = METEOGRAM_URL_POINT
            params: dict[str, Any] | None = {"x": target.lon, "y": target.lat}
        else:
            url = METEOGRAM_URL_POI.format(poi_id=target.poi_id)
            params = None
        async with self._session.get(
            url, params=params, headers=self._headers, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
        points = [MeteogramPoint.from_api(item) for item in payload.get("data", [])]
        return Meteogram(
            points=points,
            elevation_m=_int(payload.get("z")),
            parameters=payload.get("parameters") or {},
            fetched_at=datetime.now().astimezone(),
        )

    async def fetch_alerts(self, target: WeatherTarget) -> Alerts:
        """Výstrahy platné pro ORP, ve kterém lokalita leží."""
        found = orp_lookup.find_or_nearest(target.lat, target.lon)
        if found is None:
            _LOGGER.debug("Lokalita %s je mimo ČR — výstrahy přeskočeny", target.name)
            return Alerts()

        async with self._session.get(
            ALERTS_URL, headers=self._headers, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)

        return _match_alerts(payload, found)


def _match_alerts(payload: dict[str, Any], found: "orp_lookup.Orp") -> Alerts:
    region_id = ALERT_REGION_PREFIX + found.region
    items: list[AlertItem] = []
    area_name: str | None = None
    now = datetime.now(timezone.utc)

    for group in payload.get("phenomenon_groups") or []:
        category = group.get("phenomenon_category") or ""
        if category in ALERT_SKIP_CATEGORIES:
            continue
        for area_group in group.get("area_groups") or []:
            matched = _match_area(area_group.get("areas") or [], region_id, found.name)
            if matched is None:
                continue
            area_name = matched.get("name") or area_name
            for raw in area_group.get("single_alerts") or []:
                item = _parse_alert(raw, category)
                if item is None:
                    continue
                if item.end and item.end < now:
                    continue  # už skončila
                items.append(item)

    items.sort(
        key=lambda a: (
            SEVERITY_ORDER.get(a.severity, 99),
            a.start.isoformat() if a.start else "",
        )
    )
    return Alerts(items=items, orp=found.name, region=found.region, area=area_name)


def _match_area(
    areas: list[dict[str, Any]], region_id: str, orp_name: str
) -> dict[str, Any] | None:
    """Najde oblast pokrývající náš kraj — buď celý, nebo naše ORP mezi subareas."""
    for area in areas:
        if area.get("id") != region_id:
            continue
        if area.get("whole_area"):
            return area
        subareas = area.get("subareas") or []
        if any(s.get("name") == orp_name for s in subareas):
            return area
    return None


def _parse_alert(raw: dict[str, Any], category: str) -> AlertItem | None:
    if raw.get("is_cancellation"):
        return None
    description = ((raw.get("description") or {}).get("cz") or "").strip()
    severity = raw.get("severity") or "Minor"
    # „Minor bez textu" je klidová hodnota (= žádná výstraha), ne skutečná výstraha
    if not description and severity == "Minor":
        return None
    return AlertItem(
        category=category,
        phenomenon=(raw.get("phenomenon") or "").strip(),
        description=description,
        instruction=((raw.get("instruction") or {}).get("cz") or "").strip(),
        severity=severity,
        certainty=raw.get("certainty") or "",
        start=_parse_dt_opt(raw.get("t_from")),
        end=_parse_dt_opt(raw.get("t_to")),
    )


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_dt_opt(s: Any) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        parsed = _parse_dt(s)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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
