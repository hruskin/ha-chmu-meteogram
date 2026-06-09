"""DataUpdateCoordinator pro integraci Počasí ČHMÚ."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .chmu_client import Alert, ChmuClient, MeteogramImage
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .locations import AladinLocation

_LOGGER = logging.getLogger(__name__)


@dataclass
class ChmuData:
    meteogram: MeteogramImage | None
    alerts: list[Alert]


class ChmuCoordinator(DataUpdateCoordinator[ChmuData]):
    """Koordinátor — jedno volání získá meteogram i výstrahy a sdílí je entitám."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ChmuClient,
        location: AladinLocation,
        alerts_enabled: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{location.id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client
        self.location = location
        self._alerts_enabled = alerts_enabled

    async def _async_update_data(self) -> ChmuData:
        try:
            meteogram = await self._client.fetch_meteogram(self.location.id)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Meteogram: {err}") from err

        alerts: list[Alert] = []
        if self._alerts_enabled:
            try:
                alerts = await self._client.fetch_alerts()
            except Exception as err:  # noqa: BLE001
                # Selhání výstrah nemá shodit celou integraci
                _LOGGER.warning("Nelze stáhnout výstrahy ČHMÚ: %s", err)

        return ChmuData(meteogram=meteogram, alerts=alerts)
