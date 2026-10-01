"""Time of day for the scheduled announcement."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import State
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import ComfortEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([AnnounceTime(entry.runtime_data)])


class AnnounceTime(ComfortEntity, TimeEntity, RestoreEntity):
    _attr_name = "Announcement time"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "announce_time")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last: State | None = await self.async_get_last_state()
        if last and last.state not in ("unknown", "unavailable"):
            try:
                self.advisor.set("announce_time", time.fromisoformat(last.state))
            except ValueError:
                pass

    @property
    def native_value(self) -> time:
        return self.advisor.get("announce_time")

    async def async_set_value(self, value: time) -> None:
        self.advisor.set("announce_time", value.replace(second=0, microsecond=0))
