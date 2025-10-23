# Normalized Spectral Calculations for TCS34725

# Recent Enhancements (2024)

- **AS7262 Spectral Sensor:** Now uses Gaussian mapping (FWHM 40nm) for each channel, distributing energy realistically across wavelength bins. The total energy is preserved by rescaling after integration.
- **TCS34725 Sensor:** Raw RGB+clear counts are normalized by gain and integration time, then mapped to wavelength bins with proper overlap. This ensures consistent, comparable measurements regardless of sensor settings.
- **TSL2591 Sensor:** Broadband sensor mapped to visible and IR bins for spectral fusion.
- **Energy Preservation:** All sensor mappings are rescaled to preserve total energy, ensuring accurate fusion and comparison across sensor types.
- **Calibration Factor Validation:** Calibration factors (e.g., scaling_factor, lux_calibration) are validated and can be set per sensor for precise adjustment.
- **Histogram Plotting:** Graphical and numerical histograms are generated for each sensor and the combined fusion, aiding in analysis and debugging.

## Overview

The TCS34725 sensor provides raw RGB counts that vary based on:
- **Gain setting** (1x, 4x, 16x, or 60x amplification)
- **Integration time** (2.4ms to 240ms exposure)

To make measurements comparable across different settings, we normalize the raw counts before using them in spectral calculations.

## Normalization Formula

```
normalized_count = raw_count / (gain × integration_time_ms)
```

**Units:** counts per millisecond per unit gain

This gives us a **baseline measurement** that's independent of sensor settings.

## Example Calculation

### Current Sensor Settings:
- Gain: 60x
- Integration time: 240 ms
- Normalization factor: 60 × 240 = **14,400**

### Raw Counts:
- Red: 1,875
- Green: 1,482
- Blue: 1,015
- Clear: 4,358

### Normalized Values:
- Red: 1,875 / 14,400 = **0.1302**
- Green: 1,482 / 14,400 = **0.1029**
- Blue: 1,015 / 14,400 = **0.0705**
- Clear: 4,358 / 14,400 = **0.3026**

## Why Normalization Matters

### Without Normalization:
If the sensor adjusts from 16x gain to 60x gain, raw counts increase by 3.75x even though the light didn't change. This would make:
- Different readings incomparable
- Zone calculations inconsistent
- Scaling factors change with sensor settings

### With Normalization:
The same light will produce the same normalized values regardless of gain/integration settings, making measurements:
- Comparable over time
- Consistent across different sensors
- Properly scalable

### With Gaussian Mapping (AS7262):
Each channel's energy is distributed using a Gaussian curve (FWHM 40nm), then rescaled to preserve total energy. This provides a more realistic spectral spread and enables accurate fusion with other sensor types.

### Calibration Factor Validation:
Calibration factors are checked and can be set per sensor, ensuring that scaling and lux calibration are correct for each device.

## Spectral Bin Distribution

After normalization, these values are distributed to wavelength bins:

```
TCS34725 Channel Mapping:
- Blue (430-490nm):   0.0705 counts/ms/gain
- Green (500-580nm):  0.1029 counts/ms/gain
- Red (600-700nm):    0.1302 counts/ms/gain
- Clear (400-700nm):  0.3026 counts/ms/gain (broadband)
```

Each channel's value is distributed across overlapping 20nm bins based on spectral overlap.

## Zone Calculations

### At Sensor Location (15-6):
```
Distance: 0.1 (minimum)
Attenuation: 1.0 / (0.1² + 1.0) = 0.99

Normalized bins after attenuation:
  [bin values × 0.99 × scaling_factor]

PAR sum (400-700nm): ~0.60 (with scaling_factor = 1.0)
```

### Far from Sensor (0-0):
```
Distance: 16.16
Attenuation: 1.0 / (16.16² + 1.0) = 0.0038

PAR sum: ~0.60 × 0.0038 = 0.0023
```

## Current Output Values

With **scaling_factor = 1.0**:
- Zone 15-6: PPFD ≈ 0.60, Lux ≈ 0.32
- Zone 0-0: PPFD ≈ 0.002, Lux ≈ 0.001

These are **relative values** in normalized units (counts/ms/gain summed over PAR range).

## Converting to Absolute Units (μmol/m²/s)

To convert to actual PPFD in μmol/m²/s, you need a scaling factor determined by:

### Method 1: Reference Sensor Calibration
1. Place a quantum sensor (reference) at a location
2. Note its PPFD reading (e.g., 150 μmol/m²/s)
3. Check the calculated zone value at that location (e.g., 0.45)
4. Calculate: `scaling_factor = 150 / 0.45 = 333.3`

### Method 2: Known Light Source
1. Use manufacturer specs for your grow light
2. Measure at a known distance
3. Compare expected vs calculated values
4. Derive scaling factor

### Method 3: Lux-based Estimation
Since the sensor provides lux (via DN40 algorithm):
```
# Typical conversion for white LEDs
ppfd_estimate = lux × 0.0185  # μmol/m²/s per lux

# For your current reading:
lux = 30  (from sensor)
ppfd ≈ 30 × 0.0185 = 0.56 μmol/m²/s

# Compare to calculated value at sensor
calculated = 0.60
scaling_factor = 0.56 / 0.60 ≈ 0.93
```

## Recommended Next Steps

1. **Verify sensor's lux accuracy** - Compare with a calibrated lux meter
2. **Use lux-based scaling** - Start with scaling_factor ≈ 0.93 based on lux correlation
3. **Refine with reference** - If you have a quantum sensor, use it for precise calibration
4. **Monitor consistency** - Check that values remain stable as sensor auto-adjusts gain/integration

## Notes

- Normalization happens in `control/spectral_fusion.py` → `map_sensor_to_bins()`
- Only raw count channels are normalized (red_raw, green_raw, blue_raw, clear_raw)
- Derived values (lux, color_temp) are not normalized (they're already sensor-computed)
- The sensor will auto-adjust gain/integration based on light levels, but normalized values will remain consistent
