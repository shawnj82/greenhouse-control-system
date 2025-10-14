# Hardware Testing Guide

This guide provides a practical checklist to verify hardware in the greenhouse-control-system. It focuses on quick bring-up, sanity checks, and known caveats. Use it when wiring new sensors, validating a bench setup, or diagnosing issues.

## What you’ll need
- Linux host with the repo and services (web + scheduler) installed
- Python virtual environment (see repository README)
- I2C enabled and accessible (e.g., /dev/i2c-1)
- Multimeter and jumpers

## General procedure
1) Power and wiring
- Verify 3.3V/5V, GND continuity, and correct pull-ups if required
- Double-check sensor addresses against your config (data/light_sensors.json)

2) I2C scan (optional but recommended)
- Use i2c-tools to confirm device presence on the expected bus

3) Service sanity
- Restart services to pick up changes
- Watch logs for initialization warnings/errors

4) Web/API checks
- Open /api/light-sensors to confirm readings are present
- Optional: /api/light-sensors/debug performs direct hardware probes (bypasses cache)
- Inspect data/sensor_readings.json for structured values and timestamps

---

## Light Sensors
This system supports both dedicated lux sensors and color/spectral devices. Support varies by model:
- BH1750, TSL2561, VEML7700, TSL2591: report lux directly
- TCS34725 (RGB color): primarily a color sensor; we derive lux and approximate PPFD
- AS7341 (11-channel spectral): reports spectral bands; higher fidelity

### Quick checks
- Verify the sensor address in data/light_sensors.json
- Hit /api/light-sensors and confirm an entry appears for your sensor
- Shine a flashlight or toggle a grow light to see values change
- Ensure lux values are non-negative (any negatives are clamped to 0.0 with a warning logged)

---

## TCS34725 Notes and Limitations
The TCS34725 is an RGB color sensor. It isn’t a dedicated lux or PAR meter, but it can provide rudimentary ambient light data when needed.

### Key limitations
- Negative lux edge case: The vendor DN40 algorithm (used by the Adafruit driver) can yield negative lux under some spectral conditions (e.g., heavy blue content with IR correction). We now clamp any negative lux to 0.0 and emit a warning in logs to avoid UI/API issues.
- Onboard LED must be disabled: For ambient readings, the white LED on many TCS34725 breakouts must be disabled. Jumper the LED pin to GND so it never illuminates your scene during measurement.
- Spectral coverage: Only RGB(+clear); UV, far-red, and NIR are not measured. We interpolate some bands for display but they’re not direct measurements.
- PPFD is approximate: We estimate PPFD from RGB ratios and sensor gain/integration settings. Treat as relative guidance, not a calibrated PAR measurement.

### Wiring tips
- Power: 3.3V or 5V (check your breakout), GND common with the controller
- I2C: SDA to SDA, SCL to SCL; include pull-up resistors if your board doesn’t provide them
- LED: Tie the LED enable pin to GND to keep it off during reads

### Testing steps
1) Confirm device address with an I2C scan (default 0x29)
2) Configure sensor in data/light_sensors.json (type: "TCS34725")
3) Restart scheduler and web services
4) Check /api/light-sensors and watch logs for any clamping warnings
5) Change illumination (flashlight or toggle grow light) and verify:
   - lux increases (never negative; 0 if very dim)
   - color_temperature_k moves sensibly with warm vs. cool sources
   - PPFD (calculated) tracks relative intensity changes

### When to prefer another sensor
- If you need accurate lux across varied spectra → BH1750, VEML7700, or TSL2591
- If you need spectral/plant-weighted analysis → AS7341 or a dedicated PAR meter

---

## Troubleshooting checklist
- No readings: Check wiring, address, and /api/light-sensors debug endpoint
- Stuck or slow updates: Confirm the scheduler service is running and writing data/sensor_readings.json
- Implausible numbers: For TCS34725, verify LED is grounded and watch for clamped negatives; for other sensors, check gain/integration or ambient IR sources

---

## Related docs
- docs/TCS34725_SETUP_GUIDE.md: full setup and wiring reference
- docs/INTELLIGENT_LIGHT_DECISIONS.md: how light data is used by the control engine
- docs/ADAPTIVE_CALIBRATION_SUMMARY.md: calibration strategy and data flows
