"""Sensory — aktuální hodnota meteogramu (první bod = nejbližší hodina)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

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
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .chmu_client import MeteogramPoint
from .const import DOMAIN
from .coordinator import ChmuCoordinator
from .radar_coordinator import ChmuRadarCoordinator
from .runtime import ChmuRuntime


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
    runtime: ChmuRuntime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        ChmuSensor(runtime.coordinator, desc, entry.entry_id) for desc in SENSORS
    ]
    if runtime.radar:
        entities += [
            ChmuRainStartsSensor(runtime.radar, entry.entry_id),
            ChmuRadarIntensitySensor(runtime.radar, entry.entry_id),
        ]
    async_add_entities(entities)


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
        tgt = coordinator.target
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tgt.device_identifier)},
            name=f"ČHMÚ {tgt.name}",
            manufacturer="ČHMÚ",
            model=tgt.model_label,
            configuration_url=tgt.configuration_url,
        )

    def _current_point(self):
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None, None
        now = datetime.now(timezone.utc)
        # Bod nejbližší k "teď" — preferuje budoucí body (zaokrouhlené nahoru
        # na nejbližší hodinu, jak je v meteogramu data publikována)
        current = min(m.points, key=lambda p: abs((p.time - now).total_seconds()))
        return m, current

    @property
    def native_value(self) -> float | int | None:
        _, current = self._current_point()
        if current is None:
            return None
        return self.entity_description.value_fn(current)

    @property
    def extra_state_attributes(self) -> dict:
        m, current = self._current_point()
        if not m or not current:
            return {}
        age = (datetime.now(timezone.utc) - current.time).total_seconds()
        return {
            "validity_time": current.time.isoformat(),
            "data_age_minutes": round(age / 60, 1),
            "forecast_first": m.points[0].time.isoformat(),
            "forecast_last": m.points[-1].time.isoformat(),
            "forecast_points": len(m.points),
            "elevation_m": m.elevation_m,
            "fetched_at": m.fetched_at.isoformat(),
        }


class _RadarEntity(CoordinatorEntity[ChmuRadarCoordinator], SensorEntity):
    """Společný základ pro radarové sensory."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ChmuRadarCoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        tgt = coordinator.target
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tgt.device_identifier)},
            name=f"ČHMÚ {tgt.name}",
            manufacturer="ČHMÚ",
            model=tgt.model_label,
            configuration_url=tgt.configuration_url,
        )

    @property
    def _radar(self):
        return self.coordinator.data


class ChmuRainStartsSensor(_RadarEntity):
    """Za kolik minut podle radaru začne pršet (0 = prší, None = nečeká se)."""

    _attr_translation_key = "rain_starts_in"
    _attr_icon = "mdi:weather-rainy"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: ChmuRadarCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "rain_starts_in")

    @property
    def native_value(self) -> int | None:
        d = self._radar
        return d.starts_in if d else None

    @property
    def extra_state_attributes(self) -> dict:
        d = self._radar
        if not d:
            return {}
        return {
            "radar_time": d.observed_at.isoformat() if d.observed_at else None,
            "raining_now": d.raining,
            "threshold_dbz": d.forecast_threshold_dbz,
            "forecast": {
                f"+{minutes}min": {
                    "dbz": s.max_dbz,
                    "mm_h": s.rate_mm_h,
                    "coverage": round(s.coverage, 2),
                }
                for minutes, s in d.forecast
            },
            "radius_km": self.coordinator.radius_km,
            "attribution": "Data: ČHMÚ (opendata.chmi.cz), radar CZRAD",
        }


class ChmuRadarIntensitySensor(_RadarEntity):
    """Aktuální intenzita srážek podle radaru."""

    _attr_translation_key = "radar_intensity"
    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "mm/h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ChmuRadarCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "radar_intensity")

    @property
    def native_value(self) -> float | None:
        d = self._radar
        if not d or not d.now:
            return None
        return d.now.rate_mm_h if d.now.has_echo else 0.0

    @property
    def extra_state_attributes(self) -> dict:
        d = self._radar
        if not d or not d.now:
            return {}
        return {
            "dbz": d.now.max_dbz,
            "coverage": round(d.now.coverage, 2),
            "radar_time": d.observed_at.isoformat() if d.observed_at else None,
            "radius_km": self.coordinator.radius_km,
            "attribution": "Data: ČHMÚ (opendata.chmi.cz), radar CZRAD",
        }
