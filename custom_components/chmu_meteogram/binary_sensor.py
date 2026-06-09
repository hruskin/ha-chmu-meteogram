"""Binary sensor — výstrahy ČHMÚ pro danou oblast."""
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmuCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChmuAlertsBinarySensor(coordinator, entry.entry_id)])


class ChmuAlertsBinarySensor(CoordinatorEntity[ChmuCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Výstrahy ČHMÚ"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        loc = coordinator.location
        self._attr_unique_id = f"{entry_id}_alerts"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(loc.id))},
            name=f"ČHMÚ {loc.name}",
            manufacturer="ČHMÚ",
            model="ALADIN meteogram",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.alerts)

    @property
    def extra_state_attributes(self) -> dict:
        alerts = self.coordinator.data.alerts if self.coordinator.data else []
        # MeteoalarmCard kompatibilní atributy (zjednodušená první iterace)
        first = alerts[0] if alerts else None
        return {
            "alert_count": len(alerts),
            "alerts": [a.as_dict() for a in alerts],
            "headline": first.headline if first else None,
            "event": first.event if first else None,
            "severity": first.severity if first else None,
            "awareness_level": _severity_to_meteoalarm(first.severity) if first else None,
        }


def _severity_to_meteoalarm(severity: str) -> str:
    # MeteoalarmCard očekává čísla 1–4 jako string
    mapping = {
        "Minor": "2",
        "Moderate": "3",
        "Severe": "4",
        "Extreme": "5",
    }
    return mapping.get(severity, "1")
