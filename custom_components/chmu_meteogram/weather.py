"""Weather entity — hodinový meteogram a denní předpověď.

Jsou dvě, protože každá stojí na jiných datech a odpovídá na jinou otázku:

* meteogram — 73 hodin z modelu ALADIN, počítané pro zadaný bod
* předpověď — dny; první tři z téhož modelu, zbytek z desetidenního výhledu
  ČHMÚ, který platí pro celou republiku
"""
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
from .runtime import ChmuRuntime

_ONE_HOUR = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ChmuRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ChmuMeteogramWeather(runtime.coordinator, entry.entry_id),
            ChmuForecastWeather(runtime.coordinator, entry.entry_id, runtime.outlook),
        ]
    )


class _ChmuWeatherBase(CoordinatorEntity[ChmuCoordinator], WeatherEntity):
    """Společný základ — aktuální podmínky jsou pro obě entity stejné."""

    _attr_has_entity_name = True
    _attr_attribution = "Data: ČHMÚ, model ALADIN"

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str, key: str) -> None:
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

    # ---- aktuální stav ----

    def _now_point(self) -> MeteogramPoint | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None
        now = datetime.now(timezone.utc)
        return min(m.points, key=lambda p: abs((p.time - now).total_seconds()))

    @property
    def condition(self) -> str | None:
        p = self._now_point()
        return icons.condition(p.icon, p.precipitation, p.snow) if p else None

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


class ChmuMeteogramWeather(_ChmuWeatherBase):
    """Hodinová předpověď na tři dny pro konkrétní bod."""

    _attr_translation_key = "meteogram"
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "weather_hourly")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return None
        now = datetime.now(timezone.utc)
        return [
            Forecast(
                datetime=p.time.isoformat(),
                condition=icons.condition(p.icon, p.precipitation, p.snow),
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
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(("hourly",)))


class ChmuForecastWeather(_ChmuWeatherBase):
    """Denní předpověď — tři dny pro lokalitu, dál celostátní výhled."""

    _attr_translation_key = "forecast"
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, coordinator: ChmuCoordinator, entry_id: str, outlook) -> None:
        super().__init__(coordinator, entry_id, "weather")
        self._outlook = outlook

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._outlook:
            # výhled má vlastní interval, ale mění stejnou předpověď
            self.async_on_remove(
                self._outlook.async_add_listener(self._handle_outlook_update)
            )

    @callback
    def _handle_outlook_update(self) -> None:
        self.async_write_ha_state()
        self.hass.async_create_task(self.async_update_listeners(("daily",)))

    def _aladin_days(self) -> list[Forecast]:
        m = self.coordinator.data.meteogram if self.coordinator.data else None
        if not m or not m.points:
            return []
        by_day: dict[object, list[tuple[datetime, MeteogramPoint]]] = {}
        for p in m.points:
            local = dt_util.as_local(p.time)
            by_day.setdefault(local.date(), []).append((local, p))

        out: list[Forecast] = []
        for _day, items in sorted(by_day.items()):
            temps = [p.temperature for _, p in items if p.temperature is not None]
            if not temps:
                continue
            mid_local, mid = min(items, key=lambda it: abs(it[0].hour - 13))
            precs = [p.precipitation for _, p in items if p.precipitation is not None]
            winds = [p.wind_speed for _, p in items if p.wind_speed is not None]
            gusts = [p.wind_gust for _, p in items if p.wind_gust is not None]
            out.append(
                Forecast(
                    datetime=dt_util.start_of_local_day(mid_local).isoformat(),
                    condition=icons.condition(mid.icon, mid.precipitation, mid.snow),
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

    async def async_forecast_daily(self) -> list[Forecast] | None:
        days = self._aladin_days()
        outlook = self._outlook.data if self._outlook else None
        if not outlook:
            return days or None

        # Navážeme až za posledním dnem z modelu — ten je pro lokalitu přesnější.
        last = None
        if days:
            last = dt_util.parse_datetime(days[-1]["datetime"])
        for day in outlook:
            if last and day.day <= last.date():
                continue
            days.append(
                Forecast(
                    datetime=dt_util.start_of_local_day(
                        datetime.combine(day.day, datetime.min.time())
                    ).isoformat(),
                    condition=day.condition,
                    native_temperature=day.temp_max,
                    native_templow=day.temp_min,
                )
            )
        return days or None

    @property
    def extra_state_attributes(self) -> dict:
        days = len(self._aladin_days())
        outlook = self._outlook.data if self._outlook else None
        attrs = {
            "local_forecast_days": days,
            "attribution": "Data: ČHMÚ — model ALADIN a výhled pro ČR",
        }
        if outlook:
            attrs["outlook_days"] = max(0, len(outlook) - days)
            released = next((d.released_at for d in outlook if d.released_at), None)
            if released:
                attrs["outlook_released_at"] = released.isoformat()
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(("daily",)))
