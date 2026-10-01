# Changelog

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
