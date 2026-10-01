"""Button to announce right now."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import ComfortEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([AnnounceButton(entry.runtime_data)])


class AnnounceButton(ComfortEntity, ButtonEntity):
    _attr_name = "Announce now"
    _attr_icon = "mdi:bullhorn"

    def __init__(self, advisor) -> None:
        super().__init__(advisor, "announce_now")

    async def async_press(self) -> None:
        await self.advisor.async_announce(manual=True)
