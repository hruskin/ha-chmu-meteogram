"""Náhled meteoradaru jako obrázek."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .radar import PREVIEW_RINGS_KM
from .radar_coordinator import ChmuRadarCoordinator
from .runtime import ChmuRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ChmuRuntime = hass.data[DOMAIN][entry.entry_id]
    if runtime.radar:
        async_add_entities([ChmuRadarImage(hass, runtime.radar, entry.entry_id)])


class ChmuRadarImage(CoordinatorEntity[ChmuRadarCoordinator], ImageEntity):
    """Výřez radaru kolem lokality se značkou polohy."""

    _attr_has_entity_name = True
    _attr_translation_key = "radar"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ChmuRadarCoordinator,
        entry_id: str,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        tgt = coordinator.target
        self._attr_unique_id = f"{entry_id}_radar_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tgt.device_identifier)},
            name=f"ČHMÚ {tgt.name}",
            manufacturer="ČHMÚ",
            model=tgt.model_label,
            configuration_url=tgt.configuration_url,
        )

    async def async_image(self) -> bytes | None:
        data = self.coordinator.data
        return data.preview_png if data else None

    @property
    def image_last_updated(self) -> datetime | None:
        data = self.coordinator.data
        return data.observed_at if data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "radar_time": data.observed_at.isoformat() if data.observed_at else None,
            "rings_km": list(PREVIEW_RINGS_KM),
            "raining": data.raining,
            "attribution": "Data: ČHMÚ (opendata.chmi.cz), radar CZRAD",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if data and data.observed_at:
            self._attr_image_last_updated = data.observed_at
        super()._handle_coordinator_update()
