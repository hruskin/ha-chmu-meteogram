"""Integrace Počasí ČHMÚ — meteogram a výstrahy z data-provider.chmi.cz."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .chmu_client import ChmuClient
from .const import CONF_ALERTS_ENABLED, CONF_LOCATION_ID, DOMAIN, PLATFORMS
from .coordinator import ChmuCoordinator
from .locations import by_id, nearest

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    location = None
    location_id = data.get(CONF_LOCATION_ID)
    if location_id:
        location = by_id(int(location_id))
    if location is None:
        location = nearest(hass.config.latitude, hass.config.longitude)
        _LOGGER.info(
            "Auto-vybrána ALADIN lokalita: %s (id=%s)", location.name, location.id
        )

    session = async_get_clientsession(hass)
    client = ChmuClient(session)
    coordinator = ChmuCoordinator(
        hass=hass,
        client=client,
        location=location,
        alerts_enabled=data.get(CONF_ALERTS_ENABLED, True),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
