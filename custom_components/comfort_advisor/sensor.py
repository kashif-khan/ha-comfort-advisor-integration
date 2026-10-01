"""Sensors: jacket level and the full advice message."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .advisor import JACKET_LEVELS
from .const import CONF_GAS_PRICE, CONF_PRAYER_SENSORS
from .entity import ComfortEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    advisor = entry.runtime_data
    entities: list[SensorEntity] = [JacketSensor(advisor), MessageSensor(advisor), BriefingSensor(advisor)]
    if advisor.config.get(CONF_PRAYER_SENSORS):
        entities += [NextPrayerSensor(advisor), NextPrayerTimeSensor(advisor)]
    if advisor.config.get(CONF_GAS_PRICE):
        entities += [GasPriceSensor(advisor), FillUpCostSensor(advisor)]
    async_add_entities(entities)


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


class BriefingSensor(ComfortEntity, SensorEntity):
    """What the car briefing says right now (home, outside, prayer, fuel)."""

    _attr_name = "Car briefing"
    _attr_icon = "mdi:car-info"

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "briefing")

    @property
    def native_value(self) -> str | None:
        return self.advisor.briefing()[:255] or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"message": self.advisor.briefing()}


class NextPrayerSensor(ComfortEntity, SensorEntity):
    _attr_name = "Next prayer"
    _attr_icon = "mdi:mosque"

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "next_prayer")

    @property
    def native_value(self) -> str | None:
        return self.advisor.next_prayer[0] if self.advisor.next_prayer else None


class NextPrayerTimeSensor(ComfortEntity, SensorEntity):
    _attr_name = "Next prayer time"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "next_prayer_time")

    @property
    def native_value(self):
        return self.advisor.next_prayer[1] if self.advisor.next_prayer else None


class _GasSensor(ComfortEntity, SensorEntity):
    _attr_icon = "mdi:gas-station"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _index: int

    @property
    def native_unit_of_measurement(self) -> str:
        return self.advisor.hass.config.currency

    @property
    def native_value(self) -> float | None:
        found = self.advisor.gas()
        return round(found[self._index], 2) if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        found = self.advisor.gas()
        return {"station": found[2]} if found else {}


class GasPriceSensor(_GasSensor):
    _attr_name = "Gas price"
    _index = 0

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "gas_price")


class FillUpCostSensor(_GasSensor):
    _attr_name = "Fill-up cost"
    _attr_icon = "mdi:cash"
    _index = 1

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "fill_up_cost")
