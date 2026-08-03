"""Koordinátor desetidenního výhledu — obnovuje se po hodině."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_OUTLOOK_SCAN_INTERVAL, DOMAIN
from .outlook import OutlookClient, OutlookDay

_LOGGER = logging.getLogger(__name__)


class ChmuOutlookCoordinator(DataUpdateCoordinator[list[OutlookDay]]):
    def __init__(self, hass: HomeAssistant, client: OutlookClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_outlook",
            update_interval=DEFAULT_OUTLOOK_SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> list[OutlookDay]:
        try:
            return await self._client.fetch()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Výhled: {err}") from err
