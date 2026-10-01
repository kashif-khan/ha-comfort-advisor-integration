"""Pure advice logic for Comfort Advisor.

Nothing in this module imports Home Assistant, so it can be unit tested on its
own. All temperatures are in degrees Celsius internally; ``fahrenheit`` only
changes how the temperature is spoken.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

JACKET_NONE = "none"
JACKET_LIGHT = "light_jacket"
JACKET_WARM = "warm_coat"
JACKET_WINTER = "winter_coat"
JACKET_LEVELS = [JACKET_NONE, JACKET_LIGHT, JACKET_WARM, JACKET_WINTER]

JACKET_TEXT = {
    JACKET_NONE: "You won't need a jacket.",
    JACKET_LIGHT: "Wear a light jacket.",
    JACKET_WARM: "Wear a warm coat.",
    JACKET_WINTER: "Bundle up with a winter coat, hat and gloves.",
}


@dataclass(frozen=True)
class Thresholds:
    jacket_below: float = 15.0
    coat_below: float = 7.0
    winter_below: float = 0.0
    moisturizer_below: float = 40.0
    humidifier_on_below: float = 35.0
    humidifier_off_above: float = 50.0
    indoor_cool_below: float = 18.0


@dataclass(frozen=True)
class Readings:
    outdoor_temp_c: float | None = None
    outdoor_humidity: float | None = None
    indoor_humidity: float | None = None
    indoor_temp_c: float | None = None


@dataclass
class Advice:
    jacket_level: str | None = None
    jacket_needed: bool = False
    sweater_needed: bool = False
    moisturizer_needed: bool = False
    humidifier_needed: bool = False
    humidifier_off_suggested: bool = False
    humidifiers_to_turn_on: list[str] = field(default_factory=list)
    humidifiers_to_turn_off: list[str] = field(default_factory=list)
    # Metrics whose latest reading hasn't held steady long enough yet.
    pending: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def action_needed(self) -> bool:
        return (
            self.jacket_needed
            or self.sweater_needed
            or self.moisturizer_needed
            or self.humidifier_needed
            or self.humidifier_off_suggested
        )


class StabilityTracker:
    """Ignore short spikes: only trust a reading once its advice band has held.

    ``band_fn`` maps a value to whatever advice category it falls in. A new
    reading becomes the *stable* value only when every sample in the last
    ``window`` seconds falls in the same band; until then the previous stable
    value keeps being used and ``pending`` is True. The very first reading is
    accepted straight away so there is something to announce after a restart.
    """

    def __init__(self) -> None:
        self._samples: list[tuple[float, float | None]] = []
        self.stable: float | None = None
        self.pending = False

    def record(self, ts: float, value: float | None) -> None:
        if not self._samples or self._samples[-1][1] != value:
            self._samples.append((ts, value))

    def evaluate(self, now: float, window: float, band_fn: Callable[[float], Hashable]) -> float | None:
        start = now - window
        # Keep one sample from before the window: it is the value in effect at its start.
        while len(self._samples) > 1 and self._samples[1][0] <= start:
            self._samples.pop(0)
        values = [v for _, v in self._samples if v is not None]
        if not values:
            self.pending = False
            return self.stable
        latest = values[-1]
        if self.stable is None or window <= 0 or len({band_fn(v) for v in values}) == 1:
            self.stable = latest
            self.pending = False
        else:
            self.pending = band_fn(latest) != band_fn(self.stable)
        return self.stable


def jacket_level(temp_c: float, t: Thresholds) -> str:
    """Coldest matching level wins, so overlapping thresholds stay sane."""
    if temp_c < t.winter_below:
        return JACKET_WINTER
    if temp_c < t.coat_below:
        return JACKET_WARM
    if temp_c < t.jacket_below:
        return JACKET_LIGHT
    return JACKET_NONE


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning."
    if hour < 18:
        return "Good afternoon."
    return "Good evening."


def build_advice(
    readings: Readings,
    thresholds: Thresholds,
    *,
    hour: int,
    fahrenheit: bool = False,
    humidifiers_off: list[str] | None = None,
    humidifiers_on: list[str] | None = None,
    humidifiers_configured: bool = False,
) -> Advice:
    """Work out what to wear/apply/switch on and phrase it for speech."""
    advice = Advice()
    parts: list[str] = []

    temp = readings.outdoor_temp_c
    if temp is not None:
        advice.jacket_level = jacket_level(temp, thresholds)
        advice.jacket_needed = advice.jacket_level != JACKET_NONE
        shown = temp * 9 / 5 + 32 if fahrenheit else temp
        parts.append(f"It is {round(shown)} degrees outside.")
        parts.append(JACKET_TEXT[advice.jacket_level])

    indoor_temp = readings.indoor_temp_c
    if indoor_temp is not None and indoor_temp < thresholds.indoor_cool_below:
        advice.sweater_needed = True
        shown = indoor_temp * 9 / 5 + 32 if fahrenheit else indoor_temp
        parts.append(
            f"It is only {round(shown)} degrees indoors, so put on a sweater "
            "or turn up the heating."
        )

    # Skin dries out with the air around you outdoors; fall back to indoors.
    skin_humidity = (
        readings.outdoor_humidity
        if readings.outdoor_humidity is not None
        else readings.indoor_humidity
    )
    if skin_humidity is not None and skin_humidity < thresholds.moisturizer_below:
        advice.moisturizer_needed = True
        parts.append(
            f"The air is dry at {round(skin_humidity)} percent humidity, "
            "so apply moisturizer."
        )

    indoor = readings.indoor_humidity
    if indoor is not None:
        if indoor < thresholds.humidifier_on_below:
            advice.humidifier_needed = True
            advice.humidifiers_to_turn_on = list(humidifiers_off or [])
            if advice.humidifiers_to_turn_on:
                parts.append(
                    f"Indoor humidity is low at {round(indoor)} percent. "
                    f"Turn on the {_join(advice.humidifiers_to_turn_on)}."
                )
            elif not humidifiers_configured:
                parts.append(
                    f"Indoor humidity is low at {round(indoor)} percent. "
                    "Consider running a humidifier."
                )
            else:
                # Every humidifier is already running, nothing to ask for.
                advice.humidifier_needed = False
        elif indoor > thresholds.humidifier_off_above and humidifiers_on:
            advice.humidifier_off_suggested = True
            advice.humidifiers_to_turn_off = list(humidifiers_on)
            parts.append(
                f"Indoor humidity is {round(indoor)} percent. "
                f"You can turn off the {_join(advice.humidifiers_to_turn_off)}."
            )

    if parts:
        advice.message = " ".join([greeting(hour), *parts])
    return advice
