"""Binary sensor — výstrahy ČHMÚ pro lokalitu."""
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

from .const import DOMAIN
from .coordinator import ChmuCoordinator

# MeteoalarmCard očekává awareness_level jako "N; barva; text"
_MET_LEVEL = {
    "Minor": "2; yellow; Minor",
    "Moderate": "3; orange; Moderate",
    "Severe": "4; red; Severe",
    "Extreme": "5; violet; Extreme",
}


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
        tgt = coordinator.target
        self._attr_unique_id = f"{entry_id}_alerts"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tgt.device_identifier)},
            name=f"ČHMÚ {tgt.name}",
            manufacturer="ČHMÚ",
            model=tgt.model_label,
            configuration_url=tgt.configuration_url,
        )

    @property
    def is_on(self) -> bool:
        alerts = self.coordinator.data.alerts if self.coordinator.data else None
        return bool(alerts and alerts.is_active)

    @property
    def extra_state_attributes(self) -> dict:
        alerts = self.coordinator.data.alerts if self.coordinator.data else None
        if not alerts:
            return {}

        items = [a.as_dict() for a in alerts.items]
        worst = alerts.worst_severity
        headline = "; ".join(
            a.phenomenon or a.category for a in alerts.items if a.phenomenon or a.category
        )
        return {
            "alert_count": len(items),
            "severity": worst,
            "headline": headline or None,
            # celý text první (nejzávažnější) výstrahy — pohodlné pro šablony
            "description": alerts.items[0].description if alerts.items else None,
            "instruction": alerts.items[0].instruction if alerts.items else None,
            "alerts": items,
            "orp": alerts.orp,
            "region": alerts.region,
            "area": alerts.area,
            # MeteoalarmCard kompatibilita
            "awareness_level": _MET_LEVEL.get(worst) if worst else None,
            "attribution": "Data: ČHMÚ (vystrahy-cr.chmi.cz)",
        }
