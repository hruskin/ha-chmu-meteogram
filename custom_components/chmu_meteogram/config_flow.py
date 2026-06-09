"""Config flow — výběr Home coords (default) vs POI ze seznamu."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ALERTS_ENABLED,
    CONF_LOCATION_ID,
    CONF_MODE,
    DOMAIN,
    MODE_HOME,
    MODE_POI,
)
from .locations import all_locations, by_id, nearest


def _mode_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=MODE_HOME, label="Home (přesné souřadnice HA)"),
                SelectOptionDict(value=MODE_POI, label="POI ze seznamu"),
            ],
            mode=SelectSelectorMode.LIST,
        )
    )


def _location_selector() -> SelectSelector:
    cat = {
        "obec": "obec",
        "vodni-plocha": "vodní plocha",
        "lyzarske-stredisko": "lyžařské středisko",
        "letiste": "letiště",
    }
    options = [
        SelectOptionDict(value=str(l.id), label=f"{l.name} ({cat.get(l.category, l.category)})")
        for l in sorted(all_locations(), key=lambda l: (l.name, l.id))
    ]
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


class ChmuConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._mode: str = MODE_HOME
        self._alerts: bool = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            self._alerts = user_input.get(CONF_ALERTS_ENABLED, True)
            if self._mode == MODE_HOME:
                name = self.hass.config.location_name or "Domov"
                return self.async_create_entry(
                    title=f"ČHMÚ — {name}",
                    data={
                        CONF_MODE: MODE_HOME,
                        CONF_ALERTS_ENABLED: self._alerts,
                    },
                )
            return await self.async_step_poi()

        schema = vol.Schema(
            {
                vol.Required(CONF_MODE, default=MODE_HOME): _mode_selector(),
                vol.Required(CONF_ALERTS_ENABLED, default=True): bool,
            }
        )
        home_name = self.hass.config.location_name or "Domov"
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"home": home_name},
        )

    async def async_step_poi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        auto = nearest(self.hass.config.latitude, self.hass.config.longitude)
        if user_input is not None:
            chosen = by_id(int(user_input[CONF_LOCATION_ID])) or auto
            return self.async_create_entry(
                title=f"ČHMÚ — {chosen.name}",
                data={
                    CONF_MODE: MODE_POI,
                    CONF_LOCATION_ID: chosen.id,
                    CONF_ALERTS_ENABLED: self._alerts,
                },
            )
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_ID, default=str(auto.id)): _location_selector(),
            }
        )
        return self.async_show_form(
            step_id="poi",
            data_schema=schema,
            description_placeholders={"auto_name": auto.name, "auto_id": str(auto.id)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return ChmuOptionsFlow(config_entry)


class ChmuOptionsFlow(OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MODE, default=current.get(CONF_MODE, MODE_HOME)
                ): _mode_selector(),
                vol.Optional(
                    CONF_LOCATION_ID,
                    default=str(current.get(CONF_LOCATION_ID, "")),
                ): _location_selector(),
                vol.Required(
                    CONF_ALERTS_ENABLED,
                    default=current.get(CONF_ALERTS_ENABLED, True),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
