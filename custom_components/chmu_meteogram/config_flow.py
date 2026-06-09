"""Config flow — jednokrokové nastavení s automatickým výběrem lokality."""
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

from .const import CONF_ALERTS_ENABLED, CONF_LOCATION_ID, DOMAIN
from .locations import all_locations, by_id, nearest


def _location_options() -> list[SelectOptionDict]:
    cat_label = {
        "obec": "obec",
        "vodni-plocha": "vodní plocha",
        "lyzarske-stredisko": "lyžařské středisko",
        "letiste": "letiště",
    }
    return [
        SelectOptionDict(
            value=str(l.id),
            label=f"{l.name} ({cat_label.get(l.category, l.category)})",
        )
        for l in sorted(all_locations(), key=lambda l: (l.name, l.id))
    ]


def _location_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=_location_options(),
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=False,
        )
    )


class ChmuConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        auto = nearest(self.hass.config.latitude, self.hass.config.longitude)

        if user_input is not None:
            chosen = by_id(int(user_input[CONF_LOCATION_ID])) or auto
            return self.async_create_entry(
                title=f"ČHMÚ — {chosen.name}",
                data={
                    CONF_LOCATION_ID: chosen.id,
                    CONF_ALERTS_ENABLED: user_input.get(CONF_ALERTS_ENABLED, True),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_ID, default=str(auto.id)): _location_selector(),
                vol.Required(CONF_ALERTS_ENABLED, default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
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
