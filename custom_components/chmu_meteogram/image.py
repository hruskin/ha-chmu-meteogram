"""Image entita — meteogram PNG."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChmuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmuCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChmuMeteogramImage(hass, coordinator, entry.entry_id)])


class ChmuMeteogramImage(CoordinatorEntity[ChmuCoordinator], ImageEntity):
    _attr_has_entity_name = True
    _attr_name = "Meteogram"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ChmuCoordinator,
        entry_id: str,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        loc = coordinator.location
        self._attr_unique_id = f"{entry_id}_meteogram"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(loc.id))},
            name=f"ČHMÚ {loc.name}",
            manufacturer="ČHMÚ",
            model="ALADIN meteogram",
            configuration_url="https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/obce",
        )

    @property
    def extra_state_attributes(self) -> dict:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        loc = self.coordinator.location
        attrs = {
            "location_id": loc.id,
            "location_name": loc.name,
            "latitude": loc.lat,
            "longitude": loc.lon,
        }
        if m:
            attrs["run_time"] = m.run_time.isoformat()
        return attrs

    async def async_image(self) -> bytes | None:
        if not self.coordinator.data or not self.coordinator.data.meteogram:
            return None
        return self.coordinator.data.meteogram.data

    @callback
    def _handle_coordinator_update(self) -> None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if m is not None:
            self._attr_image_last_updated = m.fetched_at
            self._attr_content_type = m.content_type
        super()._handle_coordinator_update()

    @property
    def image_last_updated(self) -> datetime | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        return m.fetched_at if m else None
