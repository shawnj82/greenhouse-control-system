# PCA9548A I2C Multiplexer Integration

## Overview
Added support for the PCA9548A I2C multiplexer to allow multiple I2C devices with the same address to be connected to the Raspberry Pi.

## Changes Made

### 1. New Files
- `sensors/pca9548a.py` - PCA9548A multiplexer driver with channel selection

### 2. Updated Files

#### `sensors/spectral_sensors.py`
- Updated `TCS34725Color.__init__()` to accept `mux_address` and `mux_channel` parameters
- Updated `TCS34725Color._initialize()` to select mux channel before initializing I2C bus
- Updated `SpectralSensorReader._initialize_sensors()` to pass mux parameters to TCS34725Color

#### `sensor_shared.py`
- Updated `read_light_sensor()` to extract and pass `mux_address` and `mux_channel` from config
- Updated TCS34725Color instantiation to include mux parameters

#### `web_app.py`
- Updated sensor instance caching to include mux parameters in cache key
- Updated TCS34725Color instantiation in two places to support mux parameters

#### `control/light_calibration.py`
- Updated `TCS34725LuxWrapper` to accept and pass mux parameters to TCS34725Color

#### `templates/lights.html`
- Added mux_address and mux_channel input fields to sensor configuration table
- Updated `saveLightSensors()` to read and save mux configuration

## Configuration

### Sensor Configuration Format
```json
{
  "sensors": {
    "sensor-id": {
      "name": "TCS34725 Sensor",
      "type": "TCS34725",
      "connection": {
        "bus": 1,
        "address": 41,
        "mux_address": 112,    // Optional: 0x70 = 112 decimal
        "mux_channel": 1       // Optional: 0-7
      },
      "zone_key": "15-6",
      "scaling_factor": 0.7991
    }
  }
}
```

### Field Descriptions
- `mux_address` (optional): I2C address of the PCA9548A multiplexer (typically 0x70 = 112)
- `mux_channel` (optional): Channel number on the mux where the sensor is connected (0-7)

If these fields are omitted or null, the sensor will be accessed directly without using a mux.

## Hardware Setup
1. Connect PCA9548A mux to Raspberry Pi I2C bus (SDA, SCL)
2. Connect TCS34725 sensor to one of the mux channels (SD0-7, SC0-7)
3. Note which channel the sensor is on (0-7)
4. Configure the sensor in `data/light_sensors.json` with the mux parameters

## Testing
After configuration, the sensor should initialize and read successfully through the mux:
```bash
python3 -c "from sensor_shared import read_light_sensor; ..."
```

## Web Interface
The Lights page now includes fields for configuring the mux:
- **Mux Addr**: I2C address of the multiplexer (leave blank if not using mux)
- **Ch**: Channel number 0-7 (leave blank if not using mux)

## Notes
- The mux channel is selected each time the sensor is initialized
- A small delay (50ms) is added after channel selection for stability
- The implementation is backwards compatible - sensors without mux configuration work as before
