"""Sensory — aktuální hodnota meteogramu (první bod = nejbližší hodina)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .chmu_client import MeteogramPoint
from .const import DOMAIN, PUBLIC_URL
from .coordinator import ChmuCoordinator


@dataclass(frozen=True, kw_only=True)
class ChmuSensorDescription(SensorEntityDescription):
    value_fn: Callable[[MeteogramPoint], float | int | None]


SENSORS: tuple[ChmuSensorDescription, ...] = (
    ChmuSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda p: p.temperature,
    ),
    ChmuSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda p: p.humidity,
    ),
    ChmuSensorDescription(
        key="precipitation",
        translation_key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda p: p.precipitation,
    ),
    ChmuSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        value_fn=lambda p: p.pressure,
    ),
    ChmuSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda p: p.wind_speed,
    ),
    ChmuSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda p: p.wind_gust,
    ),
    ChmuSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda p: p.wind_direction,
    ),
    ChmuSensorDescription(
        key="cloud_coverage",
        translation_key="cloud_coverage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda p: p.clouds,
    ),
    ChmuSensorDescription(
        key="snow",
        translation_key="snow",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda p: p.snow,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmuCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ChmuSensor(coordinator, desc, entry.entry_id) for desc in SENSORS
    )


class ChmuSensor(CoordinatorEntity[ChmuCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: ChmuSensorDescription

    def __init__(
        self,
        coordinator: ChmuCoordinator,
        description: ChmuSensorDescription,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        loc = coordinator.location
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(loc.id))},
            name=f"ČHMÚ {loc.name}",
            manufacturer="ČHMÚ",
            model=f"ALADIN meteogram ({loc.category})",
            configuration_url=PUBLIC_URL.format(poi_id=loc.id, slug=loc.slug),
        )

    @property
    def native_value(self) -> float | int | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None
        return self.entity_description.value_fn(m.points[0])

    @property
    def extra_state_attributes(self) -> dict:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return {}
        first = m.points[0]
        return {
            "validity_time": first.time.isoformat(),
            "forecast_points": len(m.points),
            "elevation_m": m.elevation_m,
        }
