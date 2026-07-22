"""Weather entita — meteogram jako hodinový i denní forecast."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from homeassistant.util import dt as dt_util

from . import icons
from .chmu_client import MeteogramPoint
from .const import DOMAIN
from .coordinator import ChmuCoordinator

_ONE_HOUR = timedelta(hours=1)


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
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )

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

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Agreguje 73 hodinových bodů na denní souhrny (dle lokální TZ)."""
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None

        # seskup podle lokálního data
        by_day: dict[object, list[tuple[datetime, MeteogramPoint]]] = {}
        for p in m.points:
            local = dt_util.as_local(p.time)
            by_day.setdefault(local.date(), []).append((local, p))

        out: list[Forecast] = []
        for _day, items in sorted(by_day.items()):
            temps = [p.temperature for _, p in items if p.temperature is not None]
            if not temps:
                continue
            # reprezentativní bod = nejblíž 13:00 (denní ikona/vítr)
            mid_local, mid = min(items, key=lambda it: abs(it[0].hour - 13))
            precs = [p.precipitation for _, p in items if p.precipitation is not None]
            winds = [p.wind_speed for _, p in items if p.wind_speed is not None]
            gusts = [p.wind_gust for _, p in items if p.wind_gust is not None]
            out.append(
                Forecast(
                    datetime=dt_util.start_of_local_day(mid_local).isoformat(),
                    condition=_condition(mid),
                    native_temperature=max(temps),
                    native_templow=min(temps),
                    native_precipitation=round(sum(precs), 1) if precs else None,
                    native_wind_speed=round(max(winds), 1) if winds else None,
                    native_wind_gust_speed=round(max(gusts), 1) if gusts else None,
                    wind_bearing=mid.wind_direction,
                    humidity=mid.humidity,
                )
            )
        return out

    @callback
    def _handle_coordinator_update(self) -> None:
        # Přepočítat stav + oznámit odběratelům obou typů předpovědi (HA 2024.4+)
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(("daily", "hourly")))


def _condition(p: MeteogramPoint) -> str | None:
    """ČHMÚ icon → HA WeatherCondition (den/noc i typ srážek rozliší kód)."""
    return icons.condition(p.icon, p.precipitation, p.snow)
