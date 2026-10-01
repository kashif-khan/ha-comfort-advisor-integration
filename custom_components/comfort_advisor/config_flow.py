"""Config and options flow: pick entities, everything else has a default."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ANDROID_AUTO,
    CONF_ANNOUNCE_SCRIPT,
    CONF_HUMIDIFIERS,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMPERATURE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_SPEAKERS,
    CONF_TTS_ENTITY,
    DOMAIN,
)


def _entity(domain: str | list[str], multiple: bool = False) -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain=domain, multiple=multiple))


def _schema(values: Mapping[str, Any], with_name: bool = False) -> vol.Schema:
    def suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": values[key]} if values.get(key) not in (None, "", []) else {}

    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required("name", default="Comfort Advisor")] = TextSelector()
    fields.update(
        {
            vol.Required(CONF_OUTDOOR_TEMPERATURE, description=suggested(CONF_OUTDOOR_TEMPERATURE)): _entity(["sensor", "weather"]),
            vol.Optional(CONF_OUTDOOR_HUMIDITY, description=suggested(CONF_OUTDOOR_HUMIDITY)): _entity(["sensor", "weather"]),
            vol.Optional(CONF_INDOOR_TEMPERATURE, description=suggested(CONF_INDOOR_TEMPERATURE)): _entity(["sensor", "climate"]),
            vol.Optional(CONF_INDOOR_HUMIDITY, description=suggested(CONF_INDOOR_HUMIDITY)): _entity("sensor"),
            vol.Optional(CONF_HUMIDIFIERS, description=suggested(CONF_HUMIDIFIERS)): _entity("humidifier", True),
            vol.Optional(CONF_SPEAKERS, description=suggested(CONF_SPEAKERS)): _entity("media_player", True),
            vol.Optional(CONF_TTS_ENTITY, description=suggested(CONF_TTS_ENTITY)): _entity("tts"),
            vol.Optional(CONF_ANNOUNCE_SCRIPT, description=suggested(CONF_ANNOUNCE_SCRIPT)): _entity("script"),
            vol.Required(CONF_ANDROID_AUTO, default=values.get(CONF_ANDROID_AUTO, True)): BooleanSelector(),
        }
    )
    return vol.Schema(fields)


class ComfortAdvisorConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input.pop("name")
            return self.async_create_entry(title=name, data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}, with_name=True))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ComfortAdvisorOptionsFlow()


class ComfortAdvisorOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # Replaces the old options wholesale so cleared fields stay cleared.
            return self.async_create_entry(data=user_input)
        current = dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(step_id="init", data_schema=_schema(current))
