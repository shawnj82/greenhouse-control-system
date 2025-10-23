# Zone Light Data Structure

## Overview

The zone light calculation data has been separated into multiple files to reduce file sizes and improve data organization.

## File Structure

### 1. `data/spectrum_bins.json` (Static Reference)
**Size:** ~779 bytes  
**Update Frequency:** Never (static configuration)

Contains the wavelength bin definitions used for spectral analysis across all zones.

```json
{
  "bins": [[280, 300], [300, 320], ...],
  "bin_width_nm": 20,
  "range_start_nm": 280,
  "range_end_nm": 860,
  "description": "Standard 20nm spectral bins from 280-860nm"
}
```

**API Endpoint:** `GET /api/spectrum-bins`

### 2. `data/zone_light_metrics.json` (Dynamic Measurements)
**Size:** ~1.6K (for 2 zones)  
**Update Frequency:** Every sensor cycle (~5-10 seconds)

Contains per-zone light measurements without duplicating spectrum bin definitions.

```json
{
  "timestamp": 1760476458.8451226,
  "zones": {
    "0-0": {
      "intensities": [0.0, 0.0, ..., 1132.21, 2307.62, ...],
      "lux": 17869.626,
      "ppfd": 33989.109,
      "color": null,
      "single_sensor_mode": true,
      "distance_from_sensor": 0.1
    }
  }
}
```

**API Endpoint:** `GET /api/zone-light-metrics`

### 3. `data/sensor_readings.json` (Sensor Data Only)
**Size:** ~504 bytes  
**Update Frequency:** Every sensor cycle (~5-10 seconds)

Contains only raw sensor readings without zone fusion data.

```json
{
  "timestamp": 1760476981.3886933,
  "readings": {
    "ls-1760396125463": {
      "raw_color_data": {
        "red_raw": 4625,
        "green_raw": 5452,
        "blue_raw": 7133,
        "clear_raw": 17172,
        "color_temperature_k": 7276.02,
        "lux": 3744.68,
        "integration_time_ms": 240,
        "gain": 1,
        "ppfd_approx": 67.32
      },
      "sensor_type": "TCS34725",
      "timestamp": 1760476834.796,
      "error": null
    }
  }
}
```

**API Endpoint:** `GET /api/light-sensors`

## Benefits

### Size Reduction
- **Before:** sensor_readings.json was ~5.0K (included zone_fusion with repeated spectrum_bins)
- **After:** 
  - sensor_readings.json: ~504 bytes (sensor data only)
  - zone_light_metrics.json: ~1.6K (zone metrics without bins)
  - spectrum_bins.json: ~779 bytes (static, loaded once)
- **Savings:** ~2.9K for 2 zones; scales with zone count

### Performance
- Clients can cache `spectrum_bins.json` indefinitely
- Only `zone_light_metrics.json` needs frequent polling
- Reduced bandwidth usage for dashboard updates

### Maintainability
- Spectrum bin configuration centralized in one file
- Easier to update bin definitions globally
- Clear separation of static vs dynamic data

## Usage Example

### Frontend JavaScript
```javascript
// Load static bins once on page load
const spectrumBins = await fetch('/api/spectrum-bins').then(r => r.json());

// Poll for zone metrics updates
setInterval(async () => {
  const metrics = await fetch('/api/zone-light-metrics').then(r => r.json());
  updateZoneDisplay(metrics.zones, spectrumBins.bins);
}, 10000);
```

### Python Backend
```python
import json

# Load static bins
with open('data/spectrum_bins.json') as f:
    bins = json.load(f)['bins']

# Load current zone metrics
with open('data/zone_light_metrics.json') as f:
    zone_metrics = json.load(f)

# Combine for analysis
for zone_key, data in zone_metrics['zones'].items():
    spectrum = dict(zip(bins, data['intensities']))
    print(f"Zone {zone_key}: {data['lux']} lux, {data['ppfd']} μmol/m²/s")
```

## Migration Notes

- **Breaking Change:** `/api/light-sensors` no longer includes zone_fusion data
- Use `/api/zone-fusion` or `/api/zone-light-metrics` for zone data instead
- `/api/zone-fusion` now reads from `zone_light_metrics.json` (not `sensor_readings.json`)
- Spectrum bins moved to separate file (`spectrum_bins.json`) - load once and cache
- Total data size reduced by ~58% for typical 2-zone setup
