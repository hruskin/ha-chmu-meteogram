"""DataUpdateCoordinator pro integraci Počasí ČHMÚ."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .chmu_client import Alert, ChmuClient, Meteogram
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .locations import WeatherTarget

_LOGGER = logging.getLogger(__name__)


@dataclass
class ChmuData:
    meteogram: Meteogram | None
    alert: Alert | None


class ChmuCoordinator(DataUpdateCoordinator[ChmuData]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: ChmuClient,
        target: WeatherTarget,
        alerts_enabled: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{target.device_identifier}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client
        self.target = target
        self._alerts_enabled = alerts_enabled

    async def _async_update_data(self) -> ChmuData:
        try:
            meteogram = await self._client.fetch_meteogram(self.target)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Meteogram: {err}") from err

        alert: Alert | None = None
        if self._alerts_enabled:
            try:
                alert = await self._client.fetch_alert(self.target)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Výstrahy ČHMÚ: %s", err)

        return ChmuData(meteogram=meteogram, alert=alert)
