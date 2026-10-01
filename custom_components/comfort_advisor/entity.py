"""Shared base entity."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import ComfortAdvisor


class ComfortEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, advisor: ComfortAdvisor, key: str) -> None:
        self.advisor = advisor
        self._attr_unique_id = f"{advisor.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, advisor.entry.entry_id)},
            name=advisor.entry.title,
            manufacturer="Comfort Advisor",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.advisor.signal, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
