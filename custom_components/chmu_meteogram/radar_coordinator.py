"""Koordinátor meteoradaru — vlastní, protože se obnovuje po 5 min."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_RADAR_SCAN_INTERVAL, DOMAIN
from .locations import WeatherTarget
from .radar import DEFAULT_RADIUS_KM, RadarClient, RadarData

_LOGGER = logging.getLogger(__name__)


class ChmuRadarCoordinator(DataUpdateCoordinator[RadarData]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: RadarClient,
        target: WeatherTarget,
        radius_km: float = DEFAULT_RADIUS_KM,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_radar_{target.device_identifier}",
            update_interval=DEFAULT_RADAR_SCAN_INTERVAL,
        )
        self._client = client
        self.target = target
        self.radius_km = radius_km

    async def _async_update_data(self) -> RadarData:
        try:
            return await self._client.fetch(
                self.target.lat, self.target.lon, radius_km=self.radius_km
            )
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Radar: {err}") from err
