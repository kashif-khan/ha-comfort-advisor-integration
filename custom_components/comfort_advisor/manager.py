"""Runtime manager: reads sensors, computes advice, announces and notifies."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
    EVENT_SERVICE_REGISTERED,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_conversion import TemperatureConverter

from .advisor import Advice, Readings, StabilityTracker, Thresholds, build_advice, jacket_level
from .const import (
    CONF_ANDROID_AUTO,
    CONF_ANNOUNCE_SCRIPT,
    CONF_HUMIDIFIERS,
    CONF_INDOOR_HUMIDITY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_SPEAKERS,
    CONF_TTS_ENTITY,
    DEFAULT_SETTINGS,
    DOMAIN,
    NOTIFY_TAG,
    SUBSCRIPTION_PREFIX,
    THRESHOLD_KEYS,
)

_LOGGER = logging.getLogger(__name__)

_BAD_STATES = (STATE_UNAVAILABLE, STATE_UNKNOWN, "", None)
MOBILE_APP_PREFIX = "mobile_app_"


@dataclass(frozen=True)
class Subscriber:
    """Someone who can receive a notification: a person, or a bare phone."""

    key: str
    name: str
    services: tuple[str, ...]


def discover_subscribers(hass: HomeAssistant) -> dict[str, Subscriber]:
    """Map every Companion-app notify service to a person where possible.

    Persons whose tracker is a mobile_app device get one subscriber covering
    all of their phones. Notify services that belong to nobody get their own
    subscriber so they are still opted in by default.
    """
    services = {
        name
        for name in hass.services.async_services().get("notify", {})
        if name.startswith(MOBILE_APP_PREFIX)
    }
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    claimed: set[str] = set()
    result: dict[str, Subscriber] = {}

    for person in hass.states.async_all("person"):
        found: list[str] = []
        for tracker in person.attributes.get("device_trackers") or []:
            entry = ent_reg.async_get(tracker)
            if not entry or entry.platform != "mobile_app" or not entry.device_id:
                continue
            device = dev_reg.async_get(entry.device_id)
            if not device or not device.name:
                continue
            svc = f"{MOBILE_APP_PREFIX}{slugify(device.name)}"
            if svc in services and svc not in found:
                found.append(svc)
        if found:
            claimed.update(found)
            key = person.entity_id.split(".", 1)[1]
            result[key] = Subscriber(
                key, person.attributes.get("friendly_name") or key, tuple(found)
            )

    for svc in sorted(services - claimed):
        pretty = svc[len(MOBILE_APP_PREFIX):].replace("_", " ").title()
        result[svc] = Subscriber(svc, pretty, (svc,))
    return result


class ComfortAdvisor:
    """Holds the settings and drives announcements for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.advice: Advice = Advice()
        self.signal = f"{DOMAIN}_update_{entry.entry_id}"
        self._unsubs: list[Callable[[], None]] = []
        self._unsub_timer: Callable[[], None] | None = None
        self._rescan_listeners: list[Callable[[], None]] = []
        self._trackers = {
            "outdoor temperature": StabilityTracker(),
            "outdoor humidity": StabilityTracker(),
            "indoor humidity": StabilityTracker(),
        }
        self._unsub_settle: Callable[[], None] | None = None

    @property
    def config(self) -> dict[str, Any]:
        # The options flow saves the full set of fields, so once it has run it
        # fully replaces the original setup data (that is how a field gets cleared).
        return dict(self.entry.options or self.entry.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    @callback
    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        if key == "announce_time":
            self._schedule()
        self.refresh()

    @callback
    def restore(self, key: str, value: Any) -> None:
        """Load a restored value without triggering side effects twice."""
        self.settings[key] = value

    @callback
    def refresh(self) -> None:
        self.advice = self.compute()
        self._manage_settle_timer()
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def _manage_settle_timer(self) -> None:
        """While a reading is waiting to prove itself, re-check every 30 seconds."""
        if self.advice.pending and self._unsub_settle is None:
            self._unsub_settle = async_track_time_interval(
                self.hass, self._settle_tick, timedelta(seconds=30)
            )
        elif not self.advice.pending and self._unsub_settle is not None:
            self._unsub_settle()
            self._unsub_settle = None

    @callback
    def _settle_tick(self, _now: datetime) -> None:
        self.refresh()

    # -- lifecycle ---------------------------------------------------------

    async def async_start(self) -> None:
        cfg = self.config
        watched = [
            cfg.get(k)
            for k in (CONF_OUTDOOR_TEMPERATURE, CONF_OUTDOOR_HUMIDITY, CONF_INDOOR_HUMIDITY)
            if cfg.get(k)
        ] + list(cfg.get(CONF_HUMIDIFIERS) or [])
        if watched:
            self._unsubs.append(
                async_track_state_change_event(self.hass, watched, self._source_changed)
            )
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_SERVICE_REGISTERED, self._service_registered)
        )
        self._schedule()
        self.refresh()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_settle:
            self._unsub_settle()
            self._unsub_settle = None

    @callback
    def _source_changed(self, _event: Event) -> None:
        self.refresh()

    @callback
    def _service_registered(self, event: Event) -> None:
        if event.data.get("domain") == "notify":
            self.rescan()

    @callback
    def add_rescan_listener(self, listener: Callable[[], None]) -> None:
        self._rescan_listeners.append(listener)

    @callback
    def rescan(self) -> None:
        for listener in self._rescan_listeners:
            listener()

    @callback
    def _schedule(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
        at = self.get("announce_time")
        self._unsub_timer = async_track_time_change(
            self.hass, self._timer_fired, hour=at.hour, minute=at.minute, second=0
        )

    @callback
    def _timer_fired(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_announce())

    # -- reading sensors ---------------------------------------------------

    def _read(self, entity_id: str | None, weather_attr: str) -> tuple[float, str | None] | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _BAD_STATES:
            return None
        if state.domain == "weather":
            raw = state.attributes.get(weather_attr)
            unit = state.attributes.get(f"{weather_attr}_unit")
        else:
            raw = state.state
            unit = state.attributes.get("unit_of_measurement")
        try:
            return float(raw), unit
        except (TypeError, ValueError):
            return None

    def _read_temp_c(self, entity_id: str | None) -> float | None:
        got = self._read(entity_id, "temperature")
        if got is None:
            return None
        value, unit = got
        unit = unit or self.hass.config.units.temperature_unit
        try:
            return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        except HomeAssistantError:
            return value

    def _read_humidity(self, entity_id: str | None) -> float | None:
        got = self._read(entity_id, "humidity")
        return got[0] if got else None

    def compute(self) -> Advice:
        cfg = self.config
        humidifiers = list(cfg.get(CONF_HUMIDIFIERS) or [])
        off, on = [], []
        for entity_id in humidifiers:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in _BAD_STATES:
                continue
            name = state.attributes.get("friendly_name") or entity_id
            (on if state.state == "on" else off).append(name)

        thresholds = Thresholds(**{k: float(self.get(k)) for k in THRESHOLD_KEYS})
        raw = {
            "outdoor temperature": self._read_temp_c(cfg.get(CONF_OUTDOOR_TEMPERATURE)),
            "outdoor humidity": self._read_humidity(cfg.get(CONF_OUTDOOR_HUMIDITY)),
            "indoor humidity": self._read_humidity(cfg.get(CONF_INDOOR_HUMIDITY)),
        }
        # What advice a reading would trigger; a reading is only trusted once
        # it has stayed in the same band for the configured steady time.
        bands = {
            "outdoor temperature": lambda v: jacket_level(v, thresholds),
            "outdoor humidity": lambda v: v < thresholds.moisturizer_below,
            "indoor humidity": lambda v: (
                v < thresholds.humidifier_on_below,
                v > thresholds.humidifier_off_above,
                v < thresholds.moisturizer_below,
            ),
        }
        now = dt_util.utcnow().timestamp()
        window = float(self.get("stable_minutes")) * 60
        stable: dict[str, float | None] = {}
        for name, tracker in self._trackers.items():
            tracker.record(now, raw[name])
            stable[name] = tracker.evaluate(now, window, bands[name])

        advice = build_advice(
            Readings(
                outdoor_temp_c=stable["outdoor temperature"],
                outdoor_humidity=stable["outdoor humidity"],
                indoor_humidity=stable["indoor humidity"],
            ),
            thresholds,
            hour=dt_util.now().hour,
            fahrenheit=self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT,
            humidifiers_off=off,
            humidifiers_on=on,
            humidifiers_configured=bool(humidifiers),
        )
        advice.pending = [n for n, t in self._trackers.items() if t.pending]
        return advice

    # -- delivering --------------------------------------------------------

    def _anyone_home(self) -> bool:
        persons = self.hass.states.async_all("person")
        return not persons or any(p.state == "home" for p in persons)

    async def async_announce(self, manual: bool = False) -> None:
        """Speak and notify. ``manual`` skips presence and all-clear filtering."""
        self.rescan()
        self.refresh()
        advice = self.advice
        if not advice.message:
            _LOGGER.debug("No sensor data available, nothing to announce")
            return
        if not manual and self.get("only_when_needed") and not advice.action_needed:
            return

        if self.get("speaker_enabled") and (manual or self._anyone_home()):
            await self._speak(advice.message)
        if self.get("notify_enabled"):
            await self._notify(advice.message)

    async def _speak(self, message: str) -> None:
        cfg = self.config
        speakers = list(cfg.get(CONF_SPEAKERS) or [])
        if not speakers:
            return
        try:
            script = cfg.get(CONF_ANNOUNCE_SCRIPT)
            if script:
                # Existing shared announcer (e.g. script.play_announcement).
                name = script.split(".", 1)[1]
                for speaker in speakers:
                    await self.hass.services.async_call(
                        "script", name, {"message": message, "speaker": speaker}
                    )
                return
            tts = cfg.get(CONF_TTS_ENTITY)
            if not tts:
                found = self.hass.states.async_entity_ids("tts")
                tts = found[0] if found else None
            if not tts:
                _LOGGER.warning("No TTS entity configured or found, cannot announce")
                return
            await self.hass.services.async_call(
                "tts",
                "speak",
                {"entity_id": tts, "media_player_entity_id": speakers, "message": message},
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Speaker announcement failed: %s", err)

    async def _notify(self, message: str) -> None:
        data: dict[str, Any] = {
            "tag": NOTIFY_TAG,
            "group": NOTIFY_TAG,
            "channel": "Comfort Advisor",
            "importance": "high",
        }
        if self.config.get(CONF_ANDROID_AUTO, True):
            data["car_ui"] = True

        for key, sub in discover_subscribers(self.hass).items():
            if not self.get(f"{SUBSCRIPTION_PREFIX}{key}", True):
                continue
            for service in sub.services:
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service,
                        {"title": "Comfort Advisor", "message": message, "data": data},
                    )
                except HomeAssistantError as err:
                    _LOGGER.warning("Notification to %s failed: %s", service, err)
