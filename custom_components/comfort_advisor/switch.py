"""Master toggles plus one opt-in/out switch per person (or bare phone)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import SUBSCRIPTION_PREFIX, SWITCHES
from .entity import ComfortEntity
from .manager import ComfortAdvisor, discover_subscribers


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    advisor: ComfortAdvisor = entry.runtime_data
    async_add_entities([SettingSwitch(advisor, *s) for s in SWITCHES])

    known: set[str] = set()

    @callback
    def add_new_subscribers() -> None:
        new = [
            SubscriberSwitch(advisor, sub.key, sub.name, sub.services)
            for key, sub in discover_subscribers(hass).items()
            if key not in known
        ]
        known.update(s.sub_key for s in new)
        if new:
            async_add_entities(new)

    add_new_subscribers()
    advisor.add_rescan_listener(add_new_subscribers)


class _RestoredSwitch(ComfortEntity, SwitchEntity, RestoreEntity):
    _setting_key: str

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in ("on", "off"):
            self.advisor.restore(self._setting_key, last.state == "on")
            self.advisor.refresh()

    @property
    def is_on(self) -> bool:
        return bool(self.advisor.get(self._setting_key, True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.advisor.set(self._setting_key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.advisor.set(self._setting_key, False)


class SettingSwitch(_RestoredSwitch):
    def __init__(self, advisor, key: str, name: str, default: bool) -> None:
        super().__init__(advisor, key)
        self._setting_key = key
        self._attr_name = name
        self._attr_icon = "mdi:speaker-message" if key == "speaker_enabled" else "mdi:bell-ring"


class SubscriberSwitch(_RestoredSwitch):
    """Defaults to on: everyone is opted in until they turn it off."""

    def __init__(self, advisor, sub_key: str, name: str, services: tuple[str, ...]) -> None:
        super().__init__(advisor, f"{SUBSCRIPTION_PREFIX}{sub_key}")
        self.sub_key = sub_key
        self._setting_key = f"{SUBSCRIPTION_PREFIX}{sub_key}"
        self._services = services
        self._attr_name = f"Notify {name}"
        self._attr_icon = "mdi:cellphone-message"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"notify_services": [f"notify.{s}" for s in self._services]}
