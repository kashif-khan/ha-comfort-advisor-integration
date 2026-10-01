"""Comfort Advisor: jacket, moisturizer and humidifier advice by voice and phone."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import ComfortAdvisor

PLATFORMS = ["binary_sensor", "button", "number", "sensor", "switch", "time"]

type ComfortConfigEntry = ConfigEntry[ComfortAdvisor]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def handle_announce(_call: ServiceCall) -> None:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            await entry.runtime_data.async_announce(manual=True)

    hass.services.async_register(DOMAIN, "announce", handle_announce)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ComfortConfigEntry) -> bool:
    advisor = ComfortAdvisor(hass, entry)
    entry.runtime_data = advisor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await advisor.async_start()
    entry.async_on_unload(entry.add_update_listener(_reload_on_change))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ComfortConfigEntry) -> bool:
    entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload_on_change(hass: HomeAssistant, entry: ComfortConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
