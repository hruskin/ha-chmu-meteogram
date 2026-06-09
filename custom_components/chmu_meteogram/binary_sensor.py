"""Binary sensor — výstrahy ČHMÚ pro POI."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PUBLIC_URL
from .coordinator import ChmuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmuCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChmuAlertsBinarySensor(coordinator, entry.entry_id)])


class ChmuAlertsBinarySensor(CoordinatorEntity[ChmuCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "alerts"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        loc = coordinator.location
        self._attr_unique_id = f"{entry_id}_alerts"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(loc.id))},
            name=f"ČHMÚ {loc.name}",
            manufacturer="ČHMÚ",
            model=f"ALADIN meteogram ({loc.category})",
            configuration_url=PUBLIC_URL.format(poi_id=loc.id, slug=loc.slug),
        )

    @property
    def is_on(self) -> bool:
        alert = self.coordinator.data.alert if self.coordinator.data else None
        return bool(alert and alert.is_warning)

    @property
    def extra_state_attributes(self) -> dict:
        alert = self.coordinator.data.alert if self.coordinator.data else None
        if not alert:
            return {}
        return alert.as_dict()
