"""End-to-end tests against a real (test) Home Assistant core."""
from datetime import timedelta

from homeassistant.util import dt as dt_util

from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.comfort_advisor.const import DOMAIN


async def _setup(hass, **extra):
    hass.states.async_set("sensor.out_temp", "-3", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.out_hum", "25", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.in_hum", "28", {"unit_of_measurement": "%"})
    hass.states.async_set("humidifier.bedroom", "off", {"friendly_name": "Bedroom humidifier"})
    hass.states.async_set("media_player.kitchen", "idle")
    hass.states.async_set("tts.cloud", "unknown")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Comfort Advisor",
        data={
            "outdoor_temperature": "sensor.out_temp",
            "outdoor_humidity": "sensor.out_hum",
            "indoor_humidity": "sensor.in_hum",
            "humidifiers": ["humidifier.bedroom"],
            "speakers": ["media_player.kitchen"],
            **extra,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _set_stable_minutes(hass, minutes):
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.comfort_advisor_minimum_steady_time_before_advice_changes", "value": minutes},
        blocking=True)


async def _phone(hass, person: str, device_name: str, tracker: str):
    """Register a Companion-app phone owned by a person."""
    entry = MockConfigEntry(domain="mobile_app", title=device_name)
    entry.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("mobile_app", device_name)}, name=device_name
    )
    er.async_get(hass).async_get_or_create(
        "device_tracker", "mobile_app", device_name, suggested_object_id=tracker,
        device_id=dev.id, config_entry=entry,
    )
    hass.states.async_set(f"device_tracker.{tracker}", "home")
    hass.states.async_set(f"person.{person}", "home",
                          {"friendly_name": person.title(), "device_trackers": [f"device_tracker.{tracker}"]})


async def test_entities_and_defaults(hass):
    await _setup(hass)
    assert hass.states.get("sensor.comfort_advisor_jacket_advice").state == "winter_coat"
    assert hass.states.get("binary_sensor.comfort_advisor_moisturizer_needed").state == "on"
    assert hass.states.get("binary_sensor.comfort_advisor_humidifier_needed").attributes[
        "humidifiers_to_turn_on"] == ["Bedroom humidifier"]
    assert float(hass.states.get("number.comfort_advisor_light_jacket_below").state) == 15.0
    assert hass.states.get("switch.comfort_advisor_announce_on_speakers").state == "on"
    assert hass.states.get("switch.comfort_advisor_send_notifications").state == "on"
    assert hass.states.get("time.comfort_advisor_announcement_time").state == "07:30:00"


async def test_threshold_is_editable_and_changes_advice(hass):
    await _setup(hass)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.comfort_advisor_winter_coat_below", "value": -10}, blocking=True)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.comfort_advisor_warm_coat_below", "value": 7}, blocking=True)
    assert hass.states.get("sensor.comfort_advisor_jacket_advice").state == "warm_coat"


async def test_announce_speaks_and_notifies_everyone_by_default(hass):
    speak = async_mock_service(hass, "tts", "speak")
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    bob = async_mock_service(hass, "notify", "mobile_app_bob_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _phone(hass, "bob", "Bob Phone", "bob_phone")
    await _setup(hass)

    await hass.services.async_call(DOMAIN, "announce", {}, blocking=True)
    await hass.async_block_till_done()

    assert len(speak) == 1
    assert speak[0].data["media_player_entity_id"] == ["media_player.kitchen"]
    assert speak[0].data["entity_id"] == "tts.cloud"
    assert "Turn on the Bedroom humidifier" in speak[0].data["message"]
    assert len(alice) == len(bob) == 1
    assert alice[0].data["data"]["car_ui"] is True
    # one opt-in switch per person, on by default
    assert hass.states.get("switch.comfort_advisor_notify_alice").state == "on"
    assert hass.states.get("switch.comfort_advisor_notify_bob").state == "on"


async def test_person_can_opt_out(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    bob = async_mock_service(hass, "notify", "mobile_app_bob_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _phone(hass, "bob", "Bob Phone", "bob_phone")
    await _setup(hass)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.comfort_advisor_notify_bob"}, blocking=True)

    await hass.services.async_call(DOMAIN, "announce", {}, blocking=True)
    await hass.async_block_till_done()
    assert len(alice) == 1 and len(bob) == 0


async def test_android_auto_can_be_disabled(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _setup(hass, android_auto=False)
    await hass.services.async_call(DOMAIN, "announce", {}, blocking=True)
    await hass.async_block_till_done()
    assert "car_ui" not in alice[0].data["data"]


async def test_speaker_and_notification_master_switches(hass):
    speak = async_mock_service(hass, "tts", "speak")
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _setup(hass)
    for ent in ("announce_on_speakers", "send_notifications"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": f"switch.comfort_advisor_{ent}"}, blocking=True)
    await hass.services.async_call(DOMAIN, "announce", {}, blocking=True)
    await hass.async_block_till_done()
    assert not speak and not alice


async def test_announce_script_is_used_when_configured(hass):
    play = async_mock_service(hass, "script", "play_announcement")
    await _setup(hass, announce_script="script.play_announcement")
    await hass.services.async_call(DOMAIN, "announce", {}, blocking=True)
    await hass.async_block_till_done()
    assert play[0].data["speaker"] == "media_player.kitchen"


async def test_scheduled_run_skips_all_clear_when_only_when_needed(hass):
    speak = async_mock_service(hass, "tts", "speak")
    entry = await _setup(hass)
    await _set_stable_minutes(hass, 0)
    hass.states.async_set("sensor.out_temp", "25", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.out_hum", "60", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.in_hum", "45", {"unit_of_measurement": "%"})
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.comfort_advisor_only_announce_when_action_needed"},
        blocking=True)
    await entry.runtime_data.async_announce()
    assert not speak


async def test_options_flow_reloads(hass):
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"outdoor_temperature": "sensor.out_temp", "android_auto": False})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.runtime_data.config.get("humidifiers") is None


async def test_config_flow_minimal(hass):
    hass.states.async_set("sensor.out_temp", "5")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Comfort Advisor", "outdoor_temperature": "sensor.out_temp", "android_auto": True})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.comfort_advisor_jacket_advice").state == "warm_coat"


async def test_default_steady_time_is_ten_minutes(hass):
    await _setup(hass)
    state = hass.states.get("number.comfort_advisor_minimum_steady_time_before_advice_changes")
    assert float(state.state) == 10.0


async def test_spike_is_ignored_and_message_follows_the_stable_value(hass, freezer):
    await _setup(hass)
    jacket = "sensor.comfort_advisor_jacket_advice"
    assert hass.states.get(jacket).state == "winter_coat"

    # A warm spike that ends after 3 minutes never changes the advice.
    hass.states.async_set("sensor.out_temp", "22", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert hass.states.get(jacket).state == "winter_coat"
    assert hass.states.get("binary_sensor.comfort_advisor_readings_settling").state == "on"
    freezer.tick(timedelta(minutes=3))
    async_fire_time_changed(hass)
    hass.states.async_set("sensor.out_temp", "-3", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(jacket).state == "winter_coat"
    assert hass.states.get("binary_sensor.comfort_advisor_readings_settling").state == "off"


async def test_sustained_change_is_accepted_after_the_steady_time(hass, freezer):
    await _setup(hass)
    jacket = "sensor.comfort_advisor_jacket_advice"
    hass.states.async_set("sensor.out_temp", "22", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=9))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(jacket).state == "winter_coat"
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(jacket).state == "none"
    assert "won't need a jacket" in hass.states.get(
        "sensor.comfort_advisor_advice_message").attributes["message"]


async def test_steady_time_is_configurable(hass, freezer):
    await _setup(hass)
    await _set_stable_minutes(hass, 2)
    hass.states.async_set("sensor.out_temp", "22", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.comfort_advisor_jacket_advice").state == "none"


async def test_indoor_temperature_from_sensor_and_thermostat(hass):
    hass.states.async_set("sensor.in_temp", "16", {"unit_of_measurement": "°C"})
    await _setup(hass, indoor_temperature="sensor.in_temp")
    assert hass.states.get("binary_sensor.comfort_advisor_sweater_needed").state == "on"
    assert "put on a sweater" in hass.states.get(
        "sensor.comfort_advisor_advice_message").attributes["message"]
    assert float(hass.states.get("number.comfort_advisor_sweater_when_indoor_temperature_below").state) == 18.0


async def test_climate_entity_is_read_by_current_temperature(hass):
    hass.states.async_set("climate.hall", "heat", {"current_temperature": 21.5})
    await _setup(hass, indoor_temperature="climate.hall")
    assert hass.states.get("binary_sensor.comfort_advisor_sweater_needed").state == "off"
    hass.states.async_set("climate.hall", "heat", {"current_temperature": 15})
    await _set_stable_minutes(hass, 0)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.comfort_advisor_sweater_needed").state == "on"


# -- prayer, gas, car briefing, wipers ----------------------------------------

from homeassistant.core import HomeAssistant  # noqa: E402


def _prayer_states(hass, base):
    for name, delta in (("fajr", -6), ("dhuhr", 1), ("asr", 4), ("isha", 9)):
        hass.states.async_set(
            f"sensor.islamic_prayer_times_{name}", (base + timedelta(hours=delta)).isoformat(),
            {"device_class": "timestamp"})


PRAYERS = [f"sensor.islamic_prayer_times_{n}" for n in ("fajr", "dhuhr", "asr", "isha")]


async def test_next_prayer_sensors_and_alert_at_prayer_time(hass, freezer):
    speak = async_mock_service(hass, "tts", "speak")
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    _prayer_states(hass, dt_util.utcnow())
    await _setup(hass, prayer_sensors=PRAYERS)
    assert hass.states.get("sensor.comfort_advisor_next_prayer").state == "Dhuhr"
    assert not speak and not alice

    freezer.tick(timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert speak[-1].data["message"] == "It is time for Dhuhr prayer."
    assert alice[-1].data["message"] == "It is time for Dhuhr prayer."
    assert alice[-1].data["data"]["car_ui"] is True
    assert alice[-1].data["data"]["tag"] == "comfort-advisor-prayer"
    assert hass.states.get("sensor.comfort_advisor_next_prayer").state == "Asr"


async def test_prayer_alerts_can_be_switched_off(hass, freezer):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    _prayer_states(hass, dt_util.utcnow())
    await _setup(hass, prayer_sensors=PRAYERS)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.comfort_advisor_announce_prayer_times"}, blocking=True)
    freezer.tick(timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not alice
    assert hass.states.get("sensor.comfort_advisor_next_prayer").state == "Asr"


async def test_gas_price_and_fill_up_cost(hass):
    hass.states.async_set("sensor.shell_regular", "3.50", {"friendly_name": "Shell"})
    hass.states.async_set("sensor.car_fuel", "50")
    await _setup(hass, gas_price_entity="sensor.shell_regular", gas_station_name="Costco",
                 fuel_level_entity="sensor.car_fuel")
    assert float(hass.states.get("sensor.comfort_advisor_gas_price").state) == 3.5
    # default tank 14 gal, half full
    assert float(hass.states.get("sensor.comfort_advisor_fill_up_cost").state) == 24.5
    assert hass.states.get("sensor.comfort_advisor_gas_price").attributes["station"] == "Costco"
    assert "Costco" in hass.states.get("sensor.comfort_advisor_car_briefing").attributes["message"]


async def test_car_mode_sends_briefing_to_that_phone_only(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    bob = async_mock_service(hass, "notify", "mobile_app_bob_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _phone(hass, "bob", "Bob Phone", "bob_phone")
    er.async_get(hass).async_get_or_create(
        "binary_sensor", "mobile_app", "alice_car",
        suggested_object_id="alice_phone_car_mode",
        device_id=er.async_get(hass).async_get("device_tracker.alice_phone").device_id,
        config_entry=hass.config_entries.async_entries("mobile_app")[0])
    hass.states.async_set("binary_sensor.alice_phone_car_mode", "off")
    hass.states.async_set("sensor.in_temp", "21", {"unit_of_measurement": "°C"})
    await _setup(hass, indoor_temperature="sensor.in_temp",
                 car_mode_sensors=["binary_sensor.alice_phone_car_mode"])

    hass.states.async_set("binary_sensor.alice_phone_car_mode", "on")
    await hass.async_block_till_done()
    assert len(alice) == 1 and not bob
    assert alice[0].data["title"] == "Car briefing"
    assert "Home is 21 degrees" in alice[0].data["message"]


async def test_car_briefing_service_goes_to_everyone(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    await _setup(hass)
    await hass.services.async_call(DOMAIN, "car_briefing", {}, blocking=True)
    assert len(alice) == 1
    assert "Outside it is -3 degrees" in alice[0].data["message"]


async def test_wiper_reminder_when_car_arrives_home_in_snow(hass):
    speak = async_mock_service(hass, "tts", "speak")
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    hass.states.async_set("weather.home", "snowy", {"temperature": 3})
    hass.states.async_set("device_tracker.car", "not_home")
    await _setup(hass, weather_entity="weather.home", car_tracker="device_tracker.car")
    assert hass.states.get("binary_sensor.comfort_advisor_wipers_service_mode_advised").state == "on"

    hass.states.async_set("device_tracker.car", "home")
    await hass.async_block_till_done()

    assert "service mode" in alice[-1].data["message"] and "snowing" in alice[-1].data["message"]
    assert alice[-1].data["data"]["tag"] == "comfort-advisor-wipers"
    assert "service mode" in speak[-1].data["message"]


async def test_wiper_reminder_when_freezing_without_precipitation(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    hass.states.async_set("device_tracker.car", "not_home")
    await _setup(hass, car_tracker="device_tracker.car")  # outdoor temp is -3 °C
    hass.states.async_set("device_tracker.car", "home")
    await hass.async_block_till_done()
    assert "freeze" in alice[-1].data["message"]


async def test_no_wiper_reminder_in_fair_weather_or_when_disabled(hass):
    alice = async_mock_service(hass, "notify", "mobile_app_alice_phone")
    await _phone(hass, "alice", "Alice Phone", "alice_phone")
    hass.states.async_set("device_tracker.car", "not_home")
    hass.states.async_set("weather.home", "sunny", {"temperature": 20})
    await _setup(hass, outdoor_temperature="weather.home", car_tracker="device_tracker.car")
    hass.states.async_set("device_tracker.car", "home")
    await hass.async_block_till_done()
    assert not alice

    hass.states.async_set("device_tracker.car", "not_home")
    hass.states.async_set("weather.home", "snowy", {"temperature": 20})
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.comfort_advisor_wiper_service_mode_reminder"}, blocking=True)
    await hass.async_block_till_done()
    hass.states.async_set("device_tracker.car", "home")
    await hass.async_block_till_done()
    assert not alice
