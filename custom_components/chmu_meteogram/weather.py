"""Weather entita — meteogram jako hodinový forecast."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_ONE_HOUR = timedelta(hours=1)

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import icons
from .chmu_client import MeteogramPoint
from .const import DOMAIN
from .coordinator import ChmuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmuCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ChmuWeather(coordinator, entry.entry_id)])


class ChmuWeather(CoordinatorEntity[ChmuCoordinator], WeatherEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "weather"
    _attr_attribution = "Data: ČHMÚ (data-provider.chmi.cz), model ALADIN"
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        tgt = coordinator.target
        self._attr_unique_id = f"{entry_id}_weather"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tgt.device_identifier)},
            name=f"ČHMÚ {tgt.name}",
            manufacturer="ČHMÚ",
            model=tgt.model_label,
            configuration_url=tgt.configuration_url,
        )

    # ---- helpers ----

    def _now_point(self) -> MeteogramPoint | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None
        now = datetime.now(timezone.utc)
        return min(m.points, key=lambda p: abs((p.time - now).total_seconds()))

    # ---- state (aktuální hodnoty) ----

    @property
    def condition(self) -> str | None:
        p = self._now_point()
        return _condition(p) if p else None

    @property
    def native_temperature(self) -> float | None:
        p = self._now_point()
        return p.temperature if p else None

    @property
    def native_pressure(self) -> float | None:
        p = self._now_point()
        return p.pressure if p else None

    @property
    def humidity(self) -> float | None:
        p = self._now_point()
        return p.humidity if p else None

    @property
    def native_wind_speed(self) -> float | None:
        p = self._now_point()
        return p.wind_speed if p else None

    @property
    def native_wind_gust_speed(self) -> float | None:
        p = self._now_point()
        return p.wind_gust if p else None

    @property
    def wind_bearing(self) -> float | None:
        p = self._now_point()
        return p.wind_direction if p else None

    @property
    def cloud_coverage(self) -> float | None:
        p = self._now_point()
        return p.clouds if p else None

    # ---- forecast ----

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None
        now = datetime.now(timezone.utc)
        return [
            Forecast(
                datetime=p.time.isoformat(),
                condition=_condition(p),
                native_temperature=p.temperature,
                native_pressure=p.pressure,
                humidity=p.humidity,
                native_wind_speed=p.wind_speed,
                native_wind_gust_speed=p.wind_gust,
                wind_bearing=p.wind_direction,
                native_precipitation=p.precipitation,
                cloud_coverage=p.clouds,
            )
            for p in m.points
            if p.time >= now - _ONE_HOUR
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        # Trigger update of forecast listeners (HA 2024.4+)
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(("hourly",)))


def _condition(p: MeteogramPoint) -> str | None:
    """ČHMÚ icon → HA WeatherCondition (den/noc i typ srážek rozliší kód)."""
    return icons.condition(p.icon, p.precipitation, p.snow)
