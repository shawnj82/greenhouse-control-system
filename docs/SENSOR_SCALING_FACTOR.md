# Sensor Scaling Factor Configuration

## Overview

Each sensor in your greenhouse control system can now have a **scaling factor** that converts the relative intensity values from the spectral fusion calculations into absolute measurements (e.g., μmol/m²/s for PPFD or lux).

## How It Works

1. **Backend Processing:**
   - The scheduler reads sensor data and maps it to spectrum bins
   - For each zone, it calculates attenuated intensities based on distance from the sensor
   - The scaling factor is applied: `final_intensity = base_intensity × attenuation × scaling_factor`
   - PPFD and lux are then calculated from these scaled intensities

2. **Configuration:**
   - Each sensor can have a `scaling_factor` field in `data/light_sensors.json`
   - Default value is `1.0` if not specified
   - You can configure this in the web UI under the "Lights" page

## Determining the Scaling Factor

To calibrate your sensor for absolute measurements:

### Method 1: Match Sensor's Direct Reading

If your sensor provides its own PPFD or lux value, you can scale so the zone values match at the sensor's location:

```
scaling_factor = sensor_direct_reading / calculated_zone_value
```

**Example (based on current readings):**
- Sensor direct PPFD: 0.58 μmol/m²/s
- Calculated zone PPFD at sensor location: 11419.80
- Scaling factor: 0.58 / 11419.80 ≈ **0.000051**

### Method 2: Reference Instrument Calibration

1. Place a calibrated quantum sensor (reference instrument) at a known location
2. Note the reference reading (e.g., 150 μmol/m²/s)
3. Check the calculated zone value at that location
4. Calculate: `scaling_factor = reference_reading / calculated_zone_value`

### Method 3: Known Light Source

1. Measure a light source with known output (e.g., manufacturer spec)
2. Compare with calculated values
3. Adjust scaling factor to match

## Configuration Example

### In Web UI:
1. Navigate to **Lights** page
2. Find your sensor in the "Light Sensors" table
3. Enter the scaling factor in the "Scaling Factor" column
4. Click "Save Sensors"

### In JSON (data/light_sensors.json):
```json
{
  "sensors": {
    "ls-1760396125463": {
      "name": "TCS34725 Sensor",
      "type": "TCS34725",
      "connection": {
        "bus": 1,
        "address": 41
      },
      "zone_key": "15-6",
      "scaling_factor": 0.000051
    }
  }
}
```

## Notes

- Scaling factor is applied **per sensor**, so each sensor can have its own calibration
- The scaling affects all zones calculated from that sensor
- Changes require a scheduler restart to take effect (or wait for the next update cycle)
- For best results, calibrate under typical lighting conditions
- Re-calibration may be needed if you change sensor settings (gain, integration time, etc.)

## Current Status

Based on your current setup:
- **Sensor:** TCS34725 at zone 15-6
- **Sensor direct PPFD:** ~0.58 μmol/m²/s
- **Calculated zone PPFD (before scaling):** ~11419.80
- **Recommended scaling factor:** 0.000051

After applying this scaling factor, the zone PPFD values should match the sensor's calibrated output.
