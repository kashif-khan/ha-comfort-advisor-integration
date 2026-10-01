"""UI-editable thresholds, restored across restarts."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime

from .const import NUMBERS
from .entity import ComfortEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    advisor = entry.runtime_data
    async_add_entities([ThresholdNumber(advisor, *n) for n in NUMBERS])


class ThresholdNumber(ComfortEntity, RestoreNumber):
    _attr_mode = NumberMode.BOX
    _attr_entity_category = None

    def __init__(self, advisor, key, name, default, minimum, maximum, step, kind) -> None:
        super().__init__(advisor, key)
        self._key = key
        self._attr_name = name
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        if kind == "temperature":
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_icon = "mdi:thermometer"
        elif kind == "duration":
            self._attr_device_class = NumberDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:timer-sand"
        elif kind == "volume":
            self._attr_icon = "mdi:gas-station"
        else:
            self._attr_device_class = NumberDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_icon = "mdi:water-percent"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value is not None:
            self.advisor.restore(self._key, float(last.native_value))
            self.advisor.refresh()

    @property
    def native_value(self) -> float:
        return float(self.advisor.get(self._key))

    async def async_set_native_value(self, value: float) -> None:
        self.advisor.set(self._key, value)
