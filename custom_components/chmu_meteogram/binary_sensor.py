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

from .const import ALERT_FALLBACK_ICON, DOMAIN, SEVERITY_COLORS
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
    def icon(self) -> str | None:
        """Ikona nejzávažnější výstrahy — ať karta nemusí mapovat kategorie."""
        alerts = self.coordinator.data.alerts if self.coordinator.data else None
        worst = alerts.worst if alerts else None
        if worst is None:
            return "mdi:shield-check"
        return worst.icon

    @property
    def extra_state_attributes(self) -> dict:
        alerts = self.coordinator.data.alerts if self.coordinator.data else None
        if not alerts:
            return {}

        items = [a.as_dict() for a in alerts.items]
        worst = alerts.worst
        severity = worst.severity if worst else None
        labels = [a.label for a in alerts.items]
        return {
            "alert_count": len(items),
            "severity": severity,
            "color": SEVERITY_COLORS.get(severity) if severity else None,
            # „Zátěž teplem · Bouřky" — rovnou do secondary v kartě
            "headline": " · ".join(labels) if labels else None,
            "labels": labels,
            # nejzávažnější výstraha rozbalená — pohodlné pro jednoduché šablony
            "label": worst.label if worst else None,
            "alert_icon": worst.icon if worst else ALERT_FALLBACK_ICON,
            "description": worst.description if worst else None,
            "instruction": worst.instruction if worst else None,
            "alerts": items,
            "orp": alerts.orp,
            "region": alerts.region,
            "area": alerts.area,
            # MeteoalarmCard kompatibilita
            "awareness_level": _MET_LEVEL.get(severity) if severity else None,
            "attribution": "Data: ČHMÚ (vystrahy-cr.chmi.cz)",
        }
