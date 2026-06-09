"""Config flow — jednokrokové nastavení s automatickým výběrem lokality."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import CONF_ALERTS_ENABLED, CONF_LOCATION_ID, DOMAIN
from .locations import all_locations, by_id, nearest


class ChmuConfigFlow(ConfigFlow, domain=DOMAIN):
    """První spuštění integrace."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Jen jedna instance — vybíráme automaticky lokalitu nejbližší HA
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        loc = nearest(lat, lon)

        if user_input is not None:
            location_id = user_input.get(CONF_LOCATION_ID, loc.id)
            chosen = by_id(location_id) or loc
            return self.async_create_entry(
                title=f"ČHMÚ Meteogram — {chosen.name}",
                data={
                    CONF_LOCATION_ID: chosen.id,
                    CONF_ALERTS_ENABLED: user_input.get(CONF_ALERTS_ENABLED, True),
                },
            )

        options = {l.id: f"{l.name} (id {l.id})" for l in all_locations()}
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_ID, default=loc.id): vol.In(options),
                vol.Required(CONF_ALERTS_ENABLED, default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "auto_name": loc.name,
                "auto_id": str(loc.id),
            },
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
        options = {l.id: f"{l.name} (id {l.id})" for l in all_locations()}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION_ID,
                    default=current.get(CONF_LOCATION_ID),
                ): vol.In(options),
                vol.Required(
                    CONF_ALERTS_ENABLED,
                    default=current.get(CONF_ALERTS_ENABLED, True),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
