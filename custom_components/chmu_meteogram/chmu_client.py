"""HTTP klient pro chmi.cz (meteogram PNG, výstrahy CAP)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

from .const import (
    ALADIN_PUBLISH_DELAY_HOURS,
    ALADIN_RUN_HOURS,
    ALERTS_URL,
    METEOGRAM_BASE_URL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=20)
_CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


@dataclass
class MeteogramImage:
    data: bytes
    content_type: str
    run_time: datetime  # běh ALADIN modelu (UTC)
    fetched_at: datetime


@dataclass
class Alert:
    identifier: str
    sent: datetime | None
    event: str
    severity: str
    urgency: str
    certainty: str
    headline: str
    description: str
    areas: list[str] = field(default_factory=list)
    onset: datetime | None = None
    expires: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "sent": self.sent.isoformat() if self.sent else None,
            "event": self.event,
            "severity": self.severity,
            "urgency": self.urgency,
            "certainty": self.certainty,
            "headline": self.headline,
            "description": self.description,
            "areas": self.areas,
            "onset": self.onset.isoformat() if self.onset else None,
            "expires": self.expires.isoformat() if self.expires else None,
        }


class ChmuClient:
    """Tenký asynchronní klient pro veřejná data ČHMÚ."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {"User-Agent": USER_AGENT}

    # ---------- Meteogram ----------

    @staticmethod
    def _candidate_runs(now_utc: datetime, max_back: int = 4) -> list[datetime]:
        """Vrátí kandidátní časy běhů modelu od nejnovějšího po starší."""
        cutoff = now_utc - timedelta(hours=ALADIN_PUBLISH_DELAY_HOURS)
        # Najdi nejbližší předchozí běh (00/06/12/18) k cutoff
        run = cutoff.replace(minute=0, second=0, microsecond=0)
        while run.hour not in ALADIN_RUN_HOURS:
            run -= timedelta(hours=1)
        return [run - timedelta(hours=6 * i) for i in range(max_back)]

    @staticmethod
    def _meteogram_url(run_time: datetime, location_id: int) -> str:
        stamp = run_time.strftime("%Y%m%d%H")
        return f"{METEOGRAM_BASE_URL}/{stamp}/{location_id}.png"

    async def fetch_meteogram(self, location_id: int) -> MeteogramImage:
        """Stáhne nejnovější dostupný meteogram pro lokalitu."""
        now = datetime.now(timezone.utc)
        last_err: Exception | None = None
        for run in self._candidate_runs(now):
            url = self._meteogram_url(run, location_id)
            try:
                async with self._session.get(
                    url, headers=self._headers, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 404:
                        _LOGGER.debug("Meteogram %s: 404, zkusím starší běh", url)
                        continue
                    resp.raise_for_status()
                    data = await resp.read()
                    content_type = resp.headers.get("Content-Type", "image/png")
                    return MeteogramImage(
                        data=data,
                        content_type=content_type,
                        run_time=run,
                        fetched_at=now,
                    )
            except ClientResponseError as err:
                last_err = err
                _LOGGER.debug("Meteogram %s: %s", url, err)
                continue
        raise RuntimeError(
            f"Nepodařilo se stáhnout meteogram pro lokalitu {location_id}: {last_err}"
        )

    # ---------- Výstrahy (CAP 1.2) ----------

    async def fetch_alerts(self) -> list[Alert]:
        async with self._session.get(
            ALERTS_URL, headers=self._headers, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()
        return self._parse_cap(text)

    @staticmethod
    def _parse_cap(xml_text: str) -> list[Alert]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as err:
            raise RuntimeError(f"Nelze parsovat CAP XML: {err}") from err

        identifier = _text(root, "cap:identifier") or ""
        sent = _datetime(root, "cap:sent")

        alerts: list[Alert] = []
        for info in root.findall("cap:info", _CAP_NS):
            # ČHMÚ posílá více jazyků; bereme český, jinak první
            lang = info.findtext("cap:language", default="", namespaces=_CAP_NS)
            if lang and not lang.startswith("cs"):
                continue
            areas = [
                a.findtext("cap:areaDesc", default="", namespaces=_CAP_NS) or ""
                for a in info.findall("cap:area", _CAP_NS)
            ]
            alerts.append(
                Alert(
                    identifier=identifier,
                    sent=sent,
                    event=_text(info, "cap:event") or "",
                    severity=_text(info, "cap:severity") or "Unknown",
                    urgency=_text(info, "cap:urgency") or "Unknown",
                    certainty=_text(info, "cap:certainty") or "Unknown",
                    headline=_text(info, "cap:headline") or "",
                    description=_text(info, "cap:description") or "",
                    areas=areas,
                    onset=_datetime(info, "cap:onset"),
                    expires=_datetime(info, "cap:expires"),
                )
            )
        return alerts


def _text(elem: ET.Element, tag: str) -> str | None:
    found = elem.find(tag, _CAP_NS)
    return found.text if found is not None else None


def _datetime(elem: ET.Element, tag: str) -> datetime | None:
    raw = _text(elem, tag)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
