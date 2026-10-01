"""Pure-logic tests; no Home Assistant needed."""
import pytest

from custom_components.comfort_advisor.advisor import (
    JACKET_LIGHT,
    JACKET_NONE,
    JACKET_WARM,
    JACKET_WINTER,
    Readings,
    Thresholds,
    build_advice,
    jacket_level,
)

T = Thresholds()


@pytest.mark.parametrize(
    "temp,level",
    [(25, JACKET_NONE), (15, JACKET_NONE), (14.9, JACKET_LIGHT), (7, JACKET_LIGHT),
     (6.9, JACKET_WARM), (0, JACKET_WARM), (-0.1, JACKET_WINTER), (-20, JACKET_WINTER)],
)
def test_jacket_levels(temp, level):
    assert jacket_level(temp, T) == level


def test_no_data_means_no_message():
    assert build_advice(Readings(), T, hour=8).message == ""


def test_warm_humid_day_is_all_clear():
    a = build_advice(Readings(22, 60, 45), T, hour=8, humidifiers_off=["Bedroom"], humidifiers_configured=True)
    assert not a.action_needed
    assert "won't need a jacket" in a.message
    assert a.message.startswith("Good morning.")


def test_cold_dry_day_names_the_humidifiers_to_turn_on():
    a = build_advice(
        Readings(-5, 25, 28), T, hour=7,
        humidifiers_off=["Bedroom humidifier", "Office humidifier"], humidifiers_configured=True,
    )
    assert a.jacket_level == JACKET_WINTER and a.moisturizer_needed and a.humidifier_needed
    assert "Turn on the Bedroom humidifier and Office humidifier." in a.message
    assert "apply moisturizer" in a.message


def test_humidifier_already_running_is_not_nagged():
    a = build_advice(Readings(10, 50, 20), T, hour=7, humidifiers_off=[], humidifiers_on=["Bedroom"],
                     humidifiers_configured=True)
    assert not a.humidifier_needed and "Turn on" not in a.message


def test_no_humidifier_configured_still_suggests_one():
    a = build_advice(Readings(10, 50, 20), T, hour=7)
    assert a.humidifier_needed and "Consider running a humidifier" in a.message


def test_humid_room_suggests_turning_off_running_humidifier():
    a = build_advice(Readings(18, 60, 60), T, hour=7, humidifiers_on=["Bedroom"], humidifiers_configured=True)
    assert a.humidifier_off_suggested and "turn off the Bedroom" in a.message


def test_moisturizer_falls_back_to_indoor_humidity():
    a = build_advice(Readings(None, None, 30), T, hour=7)
    assert a.moisturizer_needed


def test_fahrenheit_speech_only():
    a = build_advice(Readings(0, None, None), T, hour=14, fahrenheit=True)
    assert "32 degrees" in a.message and a.message.startswith("Good afternoon.")


def test_custom_thresholds_are_respected():
    a = build_advice(Readings(12, None, None), Thresholds(jacket_below=10), hour=7)
    assert a.jacket_level == JACKET_NONE


# -- spike filtering -------------------------------------------------------

from custom_components.comfort_advisor.advisor import StabilityTracker

MIN = 60.0


def _band(v):
    return v < 15


def _tracker(start=20.0):
    t = StabilityTracker()
    t.record(0, start)
    t.evaluate(0, 10 * MIN, _band)
    return t


def test_first_reading_is_accepted_immediately():
    assert _tracker().stable == 20.0


def test_change_is_ignored_until_it_has_held_for_the_window():
    t = _tracker()
    t.record(60 * MIN, 5.0)
    assert t.evaluate(60 * MIN, 10 * MIN, _band) == 20.0 and t.pending
    assert t.evaluate(69 * MIN, 10 * MIN, _band) == 20.0 and t.pending
    assert t.evaluate(70 * MIN + 1, 10 * MIN, _band) == 5.0 and not t.pending


def test_short_spike_never_becomes_stable():
    t = _tracker()
    t.record(60 * MIN, 5.0)
    t.evaluate(60 * MIN, 10 * MIN, _band)
    t.record(63 * MIN, 20.0)  # spike over after 3 minutes
    for minute in (63, 70, 74, 90):
        assert t.evaluate(minute * MIN, 10 * MIN, _band) == 20.0
    assert not t.pending


def test_flapping_around_a_threshold_never_settles():
    t = _tracker()
    for i, v in enumerate([5, 20, 5, 20, 5]):
        t.record((60 + i * 2) * MIN, float(v))
        assert t.evaluate((60 + i * 2) * MIN, 10 * MIN, _band) == 20.0


def test_movement_inside_one_band_updates_immediately():
    t = _tracker()
    t.record(60 * MIN, 18.5)
    assert t.evaluate(60 * MIN, 10 * MIN, _band) == 18.5


def test_zero_window_disables_filtering():
    t = _tracker()
    t.record(60 * MIN, 5.0)
    assert t.evaluate(60 * MIN, 0, _band) == 5.0


def test_unavailable_readings_keep_last_stable_value():
    t = _tracker()
    t.record(60 * MIN, None)
    assert t.evaluate(60 * MIN, 10 * MIN, _band) == 20.0 and not t.pending


def test_cool_house_suggests_a_sweater():
    a = build_advice(Readings(20, None, None, 16.0), T, hour=7)
    assert a.sweater_needed and a.action_needed
    assert "16 degrees indoors" in a.message and "sweater" in a.message


def test_comfortable_house_says_nothing_about_indoor_temperature():
    a = build_advice(Readings(20, None, None, 21.0), T, hour=7)
    assert not a.sweater_needed and "indoors" not in a.message


def test_indoor_temperature_alone_is_enough_to_speak():
    assert "sweater" in build_advice(Readings(indoor_temp_c=15.0), T, hour=7).message


def test_sweater_threshold_is_configurable():
    a = build_advice(Readings(indoor_temp_c=17.0), Thresholds(indoor_cool_below=16.0), hour=7)
    assert not a.sweater_needed
