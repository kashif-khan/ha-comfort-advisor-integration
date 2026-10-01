# Changelog

## 1.3.0
- **Prayer times:** pick the prayer sensors (e.g. from Islamic Prayer Times). At each prayer time it
  announces on the speakers and sends a car notification. Adds *Next prayer* / *Next prayer time* sensors
  and the *Announce prayer times* switch.
- **Gas:** pick your favorite station's price sensor (e.g. GasBuddy), its name, an optional car fuel level
  sensor and a *Fuel tank size* number. Adds *Gas price* and *Fill-up cost* sensors.
- **Car briefing:** home temperature and humidity, jacket / moisturizer, next prayer, gas price and
  fill-up cost in one Android Auto notification. Sent when a car-mode sensor turns on (to that phone), from
  the *Send car briefing* button or the `comfort_advisor.car_briefing` service.
- **Wipers:** when the car tracker arrives home and it is snowing, raining, hailing or colder than the new
  *Wiper service mode when outdoor temperature below* threshold, you get a reminder to put the wipers in
  service mode. Adds the *Wipers service mode advised* binary sensor and a switch to turn the reminder off.

## 1.2.0
- Optional indoor temperature (sensor or thermostat). When it is below the new *Sweater when indoor
  temperature below* threshold (default 18 °C) the message suggests a sweater or more heating. It is
  spike-filtered like the other readings. Adds the *Sweater needed* binary sensor.

## 1.1.0
- Spike filtering: advice only changes once a reading has stayed in the same advice band for a
  configurable minimum steady time (default 10 minutes). Adds the *Readings settling* binary sensor.

## 1.0.0
- Jacket, moisturizer and humidifier advice by speaker announcement and phone / Android Auto notification.
- UI-editable thresholds, announcement time and per-person notification opt-in.
