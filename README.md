<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/dark_logo.svg">
    <img src="assets/logo.svg" alt="Comfort Advisor" height="96">
  </picture>
</p>

# Comfort Advisor

A Home Assistant custom integration (HACS-ready) that looks at the temperature and
humidity and tells you, by **speaker announcement** and **phone / Android Auto
notification**:

- whether you need a **jacket** outside, or a **sweater** when it is cool indoors, (light jacket, warm coat or winter coat),
- whether to apply **moisturizer** (dry air),
- which **humidifiers** to turn on (indoor air too dry) or off (too humid).

> "Good morning. It is 4 degrees outside. Wear a warm coat. The air is dry at 32
> percent humidity, so apply moisturizer. Indoor humidity is low at 28 percent.
> Turn on the Bedroom humidifier."

Everything has a sensible default and every value is editable in the UI.

## Install (HACS)

HACS needs `custom_components/` at the root of a repo, so publish this folder as its
own repository (`kashif-khan/ha-comfort-advisor-integration`, named per [`NAMING.md`](../../NAMING.md)). Then in
HACS: **⋮ → Custom repositories →** add the repo URL, category **Integration →
Download**, restart Home Assistant.

Without HACS, copy `custom_components/comfort_advisor` into your HA `config/custom_components/`.

## Set up

**Settings → Devices & services → Add integration → Comfort Advisor.**
Only the outdoor temperature is required:

| Field | Required | Notes |
|---|---|---|
| Outdoor temperature | yes | A sensor, or a `weather` entity (any unit, converted automatically) |
| Outdoor humidity | no | Sensor or `weather` entity. Drives the moisturizer advice |
| Indoor temperature | no | A sensor or a `climate` thermostat. Triggers the sweater advice when the house is cool |
| Indoor humidity | no | Drives humidifier advice (and moisturizer if there is no outdoor humidity) |
| Humidifiers | no | Named in the message when they need turning on or off |
| Speakers | no | Skip for notifications only |
| TTS entity | no | Auto-detected if empty |
| Announcement script | no | Route speech through an existing script that takes `message` and `speaker` (e.g. this repo's `script.play_announcement`) instead of calling `tts.speak` |
| Android Auto | yes (on) | Adds `car_ui: true` so notifications appear in the car |

Change any of these later with the integration's **Configure** button.

## Android Auto: prayer, car briefing, gas and wipers

All optional; set them in the same setup / **Configure** form. Everything below is delivered as a
notification with `car_ui: true`, so it shows (and can be read aloud) on Android Auto. Turn off
*Show notifications on Android Auto* to keep them phone-only.

| What | Setup fields | Result |
|---|---|---|
| **Prayer time** | *Prayer time sensors*: the timestamp sensors of the core Islamic Prayer Times integration (Fajr, Dhuhr, Asr, Maghrib, Isha). Leave out Sunrise/Midnight unless you want an alert for them | "It is time for Asr prayer." on speakers and in the car at the prayer time, plus *Next prayer* and *Next prayer time* sensors |
| **Home climate and what to wear** | Indoor temperature / humidity and outdoor temperature / humidity (above) | The car briefing: "Home is 21 degrees and 45 percent humidity. Outside it is 4 degrees. Wear a warm coat. The air is dry, so apply moisturizer." |
| **Gas** | *Favorite station gas price sensor* (e.g. a [GasBuddy](https://github.com/firstof9/ha-gasbuddy) station sensor), *Favorite station name*, optional *Car fuel level sensor* (%) and the *Fuel tank size* number | "Gas at Costco is $3.45 per gallon. Filling up would cost about $48.30." With a fuel level sensor it prices only what is missing from the tank. *Gas price* and *Fill-up cost* sensors too |
| **Wipers** | *Car location* (device tracker or person), optionally a *Weather entity* | When the car arrives home and it is snowing, sleeting, hailing, raining or below *Wiper service mode when outdoor temperature below* (default 2 °C), a reminder to put the wipers in service mode. Spoken on the home speakers too |

**When the briefing is sent:** when a *car mode sensor* turns on (the Companion app's *Car mode*
binary sensor for your phone, which is on while connected to Android Auto; it goes to that phone only),
or on demand with the *Send car briefing* button / `comfort_advisor.car_briefing` service. The
*Car briefing* sensor always holds the current text. The Companion app's own Android Auto screen can
also list these entities if you add them to its favorites.

The wiper reminder uses the current outdoor temperature (spike-filtered) and the weather condition
at the moment the car arrives. Rain counts as well as snow and freezing, so turn the *Wiper service mode
reminder* switch off or lower the threshold if rain alone shouldn't nag you.

## Entities (the device page is your settings screen)

**Thresholds** (`number`, defaults shown, shown in your unit system, kept across restarts):

| Entity | Default |
|---|---|
| Light jacket below | 15 °C |
| Warm coat below | 7 °C |
| Winter coat below | 0 °C |
| Moisturizer when humidity below | 40 % |
| Sweater when indoor temperature below | 18 °C |
| Wiper service mode when outdoor temperature below | 2 °C |
| Fuel tank size (gallons or liters, same unit as the price) | 14 |
| Humidifier on when indoor humidity below | 35 % |
| Humidifier off when indoor humidity above | 50 % |
| Minimum steady time before advice changes | 10 min (`0` turns spike filtering off) |

**Switches**

| Entity | Default | Purpose |
|---|---|---|
| Announce on speakers | on | Master speaker toggle |
| Send notifications | on | Master notification toggle |
| Only announce when action needed | off | Skip the all-clear message |
| Announce prayer times | on | Prayer-time speaker and car alerts |
| Send car briefing | on | Briefing when a car mode sensor turns on |
| Wiper service mode reminder | on | Arrive-home wiper reminder |
| **Notify \<person\>** | **on** | One per person with the Companion app. Turn off to opt out. Phones that aren't linked to a person get their own switch |

New phones and people are opted in automatically; their switch appears the next time the
integration scans (when a notify service registers, or at each announcement).

**Other:** `time` *Announcement time* (default 07:30), `button` *Announce now*,
`sensor` *Jacket advice* / *Advice message*, and `binary_sensor`s *Jacket needed*, *Sweater needed*,
*Moisturizer needed*, *Humidifier needed*, *Humidifier can be turned off*, *Readings settling* for your own
automations and dashboards. The service `comfort_advisor.announce` does the same as the button.

## Spike filtering (minimum steady time)

A door opening, a shower or a passing cloud shouldn't change what you're told. Each metric
(outdoor temperature, outdoor humidity, indoor humidity) is only trusted once its advice has
**held steady for the minimum steady time** (default 10 minutes, set it with the *Minimum steady
time before advice changes* number).

- "Steady" means every reading in that window falls in the same advice band, e.g. the same
  jacket level, or on the same side of a humidity threshold. Small movement *within* a band
  updates straight away.
- Until a new reading has proved itself, the **previous stable value** drives the message,
  sensors and announcements. A spike that ends before the time is up never gets through, and a
  reading that keeps flapping across a threshold never settles.
- While a reading is waiting, the *Readings settling* binary sensor is on and the
  *Advice message* sensor lists the metrics in its `settling` attribute.
- The first reading after a restart is accepted immediately so there is always something to say.
- Unavailable/unknown readings are ignored and the last stable value is kept.

## Behaviour

- Announced daily at the announcement time, and on demand.
- Speakers only talk when someone is home (no `person` entities = always). *Announce now* ignores that.
- Notifications go to every opted-in person, whether home or not.
- Humidifiers already in the right state are not mentioned.
- Humidifiers are advised, not switched. Use the binary sensors in an automation if you want that.

## Dashboard example

```yaml
type: entities
title: Comfort Advisor
entities:
  - sensor.comfort_advisor_advice_message
  - button.comfort_advisor_announce_now
  - time.comfort_advisor_announcement_time
  - switch.comfort_advisor_notify_alice
  - switch.comfort_advisor_notify_bob
  - number.comfort_advisor_light_jacket_below
  - number.comfort_advisor_moisturizer_when_humidity_below
```

## Tests

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r tests/requirements.txt
pytest
```
