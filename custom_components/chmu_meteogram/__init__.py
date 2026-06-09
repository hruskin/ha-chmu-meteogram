"""Integrace Počasí ČHMÚ — meteogram a výstrahy z data-provider.chmi.cz."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .chmu_client import ChmuClient
from .const import (
    CONF_ALERTS_ENABLED,
    CONF_LOCATION_ID,
    CONF_MODE,
    DOMAIN,
    MODE_HOME,
    MODE_POI,
    PLATFORMS,
)
from .coordinator import ChmuCoordinator
from .locations import by_id, target_for_point, target_from_poi

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """v1 entries had only location_id; map them to MODE_POI."""
    if entry.version >= 2:
        return True
    new_data = dict(entry.data)
    if CONF_LOCATION_ID in new_data:
        new_data.setdefault(CONF_MODE, MODE_POI)
    else:
        new_data.setdefault(CONF_MODE, MODE_HOME)
    hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    _LOGGER.info("Migrated config entry %s to v2 (mode=%s)", entry.entry_id, new_data[CONF_MODE])
    return True


def _build_target(hass: HomeAssistant, entry: ConfigEntry):
    data = {**entry.data, **entry.options}
    mode = data.get(CONF_MODE, MODE_HOME)
    if mode == MODE_POI and data.get(CONF_LOCATION_ID):
        loc = by_id(int(data[CONF_LOCATION_ID]))
        if loc:
            return target_from_poi(loc)
        _LOGGER.warning(
            "POI id %s not found, falling back to home coords",
            data[CONF_LOCATION_ID],
        )
    # MODE_HOME nebo fallback
    name = hass.config.location_name or "Domov"
    return target_for_point(hass.config.latitude, hass.config.longitude, name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    target = _build_target(hass, entry)
    data = {**entry.data, **entry.options}

    session = async_get_clientsession(hass)
    client = ChmuClient(session)
    coordinator = ChmuCoordinator(
        hass=hass,
        client=client,
        target=target,
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
