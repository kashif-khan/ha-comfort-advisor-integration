"""Constants for Comfort Advisor."""
from __future__ import annotations

from datetime import time

DOMAIN = "comfort_advisor"

CONF_OUTDOOR_TEMPERATURE = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_INDOOR_TEMPERATURE = "indoor_temperature"
CONF_INDOOR_HUMIDITY = "indoor_humidity"
CONF_HUMIDIFIERS = "humidifiers"
CONF_SPEAKERS = "speakers"
CONF_TTS_ENTITY = "tts_entity"
CONF_ANNOUNCE_SCRIPT = "announce_script"
CONF_ANDROID_AUTO = "android_auto"

# Number entities: key, name, default, min, max, step, kind
NUMBERS = [
    ("jacket_below", "Light jacket below", 15.0, -40.0, 40.0, 0.5, "temperature"),
    ("coat_below", "Warm coat below", 7.0, -40.0, 40.0, 0.5, "temperature"),
    ("winter_below", "Winter coat below", 0.0, -40.0, 40.0, 0.5, "temperature"),
    ("moisturizer_below", "Moisturizer when humidity below", 40.0, 0.0, 100.0, 1.0, "humidity"),
    ("humidifier_on_below", "Humidifier on when indoor humidity below", 35.0, 0.0, 100.0, 1.0, "humidity"),
    ("humidifier_off_above", "Humidifier off when indoor humidity above", 50.0, 0.0, 100.0, 1.0, "humidity"),
    ("indoor_cool_below", "Sweater when indoor temperature below", 18.0, 5.0, 30.0, 0.5, "temperature"),
    ("stable_minutes", "Minimum steady time before advice changes", 10.0, 0.0, 240.0, 1.0, "duration"),
]
THRESHOLD_KEYS = [n[0] for n in NUMBERS if n[6] != "duration"]

# Master switches. All on/off defaults are opt-in except "only when needed".
SWITCHES = [
    ("speaker_enabled", "Announce on speakers", True),
    ("notify_enabled", "Send notifications", True),
    ("only_when_needed", "Only announce when action needed", False),
]

DEFAULT_ANNOUNCE_TIME = time(7, 30)

DEFAULT_SETTINGS = {
    **{n[0]: n[2] for n in NUMBERS},
    **{s[0]: s[2] for s in SWITCHES},
    "announce_time": DEFAULT_ANNOUNCE_TIME,
}

SUBSCRIPTION_PREFIX = "sub_"
NOTIFY_TAG = "comfort-advisor"
