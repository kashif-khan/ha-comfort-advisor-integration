"""Sensors: jacket level and the full advice message."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .advisor import JACKET_LEVELS
from .entity import ComfortEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    advisor = entry.runtime_data
    async_add_entities([JacketSensor(advisor), MessageSensor(advisor)])


class JacketSensor(ComfortEntity, SensorEntity):
    _attr_name = "Jacket advice"
    _attr_icon = "mdi:coat-rack"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = JACKET_LEVELS

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "jacket")

    @property
    def native_value(self) -> str | None:
        return self.advisor.advice.jacket_level


class MessageSensor(ComfortEntity, SensorEntity):
    _attr_name = "Advice message"
    _attr_icon = "mdi:message-text"

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "message")

    @property
    def native_value(self) -> str | None:
        # State is capped at 255 characters; the full text is an attribute.
        return (self.advisor.advice.message or None) and self.advisor.advice.message[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "message": self.advisor.advice.message,
            "settling": self.advisor.advice.pending,
        }
