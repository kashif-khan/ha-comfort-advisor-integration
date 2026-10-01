"""Binary sensors: does anything need doing right now?"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ComfortEntity

# key, name, icon, advice attribute
SENSORS = [
    ("jacket_needed", "Jacket needed", "mdi:coat-rack", "jacket_needed"),
    ("moisturizer_needed", "Moisturizer needed", "mdi:lotion-outline", "moisturizer_needed"),
    ("humidifier_needed", "Humidifier needed", "mdi:air-humidifier", "humidifier_needed"),
    ("humidifier_off_suggested", "Humidifier can be turned off", "mdi:air-humidifier-off", "humidifier_off_suggested"),
    ("readings_settling", "Readings settling", "mdi:timer-sand", "pending"),
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    advisor = entry.runtime_data
    async_add_entities([AdviceBinarySensor(advisor, *s) for s in SENSORS])


class AdviceBinarySensor(ComfortEntity, BinarySensorEntity):
    def __init__(self, advisor, key: str, name: str, icon: str, attr: str) -> None:
        super().__init__(advisor, key)
        self._attr_name = name
        self._attr_icon = icon
        self._attr = attr

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.advisor.advice, self._attr))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        advice = self.advisor.advice
        if self._attr == "humidifier_needed":
            return {"humidifiers_to_turn_on": advice.humidifiers_to_turn_on}
        if self._attr == "humidifier_off_suggested":
            return {"humidifiers_to_turn_off": advice.humidifiers_to_turn_off}
        if self._attr == "pending":
            return {"metrics": advice.pending}
        return {}
