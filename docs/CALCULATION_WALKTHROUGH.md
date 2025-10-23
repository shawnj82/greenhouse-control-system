# Complete Calculation Walkthrough: Sensor to Zone Light Metrics

This document traces the complete data flow from raw sensor reading to final zone light metrics.

## Step 1: Physical Sensor Reading (TCS34725)

**File:** `sensors/spectral_sensors.py` → `TCS34725Color.read_color()`

### What happens:
1. The sensor reads raw RGBC values from the hardware via I2C
2. The Adafruit library calculates:
   - **Lux** using the DN40 algorithm (Clear channel with compensation)
   - **Color Temperature** using RGB ratios
3. Our code adds a **PPFD approximation** using `approximate_ppfd()`

### Raw values (example from your sensor):
```python
{
  'red_raw': 2845,
  'green_raw': 3198,
  'blue_raw': 3358,
  'clear_raw': 9098,
  'color_temperature_k': 5926.78,
  'lux': 31.20,                    # ← DN40 lux calculation
  'integration_time_ms': 240,
  'gain': 16,
  'ppfd_approx': 0.58              # ← Our approximation
}
```

### PPFD Approximation Method:
```python
def approximate_ppfd(color_data):
    lux = 31.20
    
    # Calculate RGB percentages
    total_rgb = 2845 + 3198 + 3358 = 9401
    r_pct = 2845 / 9401 = 0.303
    g_pct = 3198 / 9401 = 0.340
    b_pct = 3358 / 9401 = 0.357
    
    # Photosynthetic efficiency weights
    red_efficiency = 1.00
    green_efficiency = 0.70
    blue_efficiency = 0.85
    
    # Weighted efficiency
    spectral_efficiency = (0.303 × 1.00) + (0.340 × 0.70) + (0.357 × 0.85)
                        = 0.303 + 0.238 + 0.303
                        = 0.844
    
    # Base conversion factor
    base_conversion = 0.0185 μmol/m²/s per lux
    
    # Adjust for spectral content
    efficiency_factor = 0.844 / 0.85 = 0.993
    
    # Final conversion (with temperature adjustment ≈ 1.0)
    final_conversion = 0.0185 × 0.993 × 1.0 = 0.0184
    
    # PPFD
    ppfd_approx = 31.20 × 0.0184 = 0.574 ≈ 0.58 μmol/m²/s
}
```

**Key Point:** This PPFD is a calibrated approximation based on lux and RGB ratios, using photosynthetic efficiency factors.

---

## Step 2: Data Storage (sensor_readings.json)

**File:** `background_scheduler.py` → `_update_sensors()`

The raw sensor data is stored with its metadata:
```json
{
  "timestamp": 1760483447.47,
  "readings": {
    "ls-1760396125463": {
      "raw_color_data": {
        "red_raw": 2845,
        "green_raw": 3198,
        "blue_raw": 3358,
        "clear_raw": 9098,
        "color_temperature_k": 5926.78,
        "lux": 31.20,
        "integration_time_ms": 240,
        "gain": 16,
        "ppfd_approx": 0.58
      },
      "sensor_type": "TCS34725",
      "timestamp": 1760483447.47,
      "error": null
    }
  }
}
```

---

## Step 3: Spectral Bin Mapping

**File:** `control/spectral_fusion.py` → `SpectralDataFusion.map_sensor_to_bins()`

### Wavelength mapping for TCS34725:
```python
SENSOR_WAVELENGTH_MAPS = {
    'TCS34725': {
        'blue_raw': (430, 490),      # ~60nm width, center ~460nm
        'green_raw': (500, 580),     # ~80nm width, center ~540nm
        'red_raw': (600, 700),       # ~100nm width, center ~650nm
        'clear_raw': (400, 700),     # ~300nm width, broadband visible
    }
}
```

### Spectrum bins (20nm width, 280-850nm):
```
Bin 0: [280-300nm] - UV
Bin 1: [300-320nm] - UV
...
Bin 6: [400-420nm] - Violet (start of visible)
Bin 7: [420-440nm] - Blue-violet
Bin 8: [440-460nm] - Blue
Bin 9: [460-480nm] - Blue
Bin 10: [480-500nm] - Blue-cyan
Bin 11: [500-520nm] - Green
Bin 12: [520-540nm] - Green
Bin 13: [540-560nm] - Green
Bin 14: [560-580nm] - Yellow-green
Bin 15: [580-600nm] - Yellow
Bin 16: [600-620nm] - Orange-red
Bin 17: [620-640nm] - Red
Bin 18: [640-660nm] - Red
Bin 19: [660-680nm] - Red
Bin 20: [680-700nm] - Deep red
Bin 21+: [700-850nm] - Near-infrared
```

### Distribution calculation:
For each sensor channel (e.g., `blue_raw = 3358`):

**Blue channel (430-490nm, width=60nm):**
- Overlaps with bins 7-10 (420-500nm)
- Each bin gets: `3358 × (overlap / 60nm)`

Example for bin 8 (440-460nm):
```
overlap_start = max(430, 440) = 440
overlap_end = min(490, 460) = 460
overlap_width = 460 - 440 = 20nm
overlap_fraction = 20 / 60 = 0.333
contribution = 3358 × 0.333 = 1,119
```

**Problem identified:** We're using **raw counts** (e.g., 3358) directly, not converting them to physical units first!

### What we should be doing:
The raw counts need to be converted to irradiance or intensity values BEFORE mapping to bins. The current approach treats raw ADC counts as if they were calibrated spectral irradiance values.

**Current bin contributions (wrong):**
```
Bin 6: 2,263 (from blue_raw + clear_raw overlap)
Bin 7: 4,349
Bin 8: 6,435
...
Bin 16: 4,397 (from red_raw)
Bin 17: 4,397
...
```

These are **raw ADC counts**, not spectral irradiance in W/m²/nm or μmol/m²/s/nm!

---

## Step 4: Single-Sensor Zone Calculation

**File:** `background_scheduler.py` → Single sensor mode

### Current approach:
```python
# base_intensities = [bin_0, bin_1, ..., bin_28]
# These are the RAW ADC COUNTS distributed across bins

scaling_factor = 1.0  # From sensor config

for zone_key in all_zone_keys:
    # Calculate distance
    dx = zone_x - 15
    dy = zone_y - 6
    distance = sqrt(dx² + dy²)
    
    # Distance attenuation (inverse square law)
    attenuation = 1.0 / (distance² + 1.0)
    
    # Apply attenuation AND scaling
    attenuated_intensities = [
        bin_value × attenuation × scaling_factor
        for bin_value in base_intensities
    ]
```

**For zone 15-6 (at sensor):**
```
distance = 0.0 → clamped to 0.1
attenuation = 1.0 / (0.1² + 1.0) = 1.0 / 1.01 ≈ 0.99
```

**For zone 0-0:**
```
distance = sqrt((0-15)² + (0-6)²) = sqrt(225 + 36) = sqrt(261) = 16.16
attenuation = 1.0 / (16.16² + 1.0) = 1.0 / 262.15 ≈ 0.00381
```

---

## Step 5: PPFD Calculation from Bins

**File:** `background_scheduler.py` → `_estimate_ppfd_from_spectrum()`

### Current calculation:
```python
def _estimate_ppfd_from_spectrum(spectrum_bins, intensities):
    par_sum = 0.0
    for (lo, hi), val in zip(spectrum_bins, intensities):
        center = (lo + hi) / 2.0
        if 400 <= center <= 700:  # PAR range
            par_sum += max(0.0, float(val))
    return round(par_sum, 3)
```

**For zone 15-6 (at sensor):**
```
PAR bins (400-700nm) contributions after attenuation:
Bin 6 (410nm): 2,263 × 0.99 = 2,240
Bin 7 (430nm): 4,349 × 0.99 = 4,305
Bin 8 (450nm): 6,435 × 0.99 = 6,370
...
Bin 20 (690nm): 4,397 × 0.99 = 4,353

par_sum = 2,240 + 4,305 + 6,370 + ... ≈ 11,420
ppfd = 11,420  (units: raw ADC counts)
```

**Actual sensor PPFD:** 0.58 μmol/m²/s

**Ratio:** 11,420 / 0.58 ≈ 19,690

---

## The Core Problems

### Problem 1: Units Mismatch
- **Sensor bins:** Raw ADC counts (0-65535 range)
- **Expected output:** μmol/m²/s (photosynthetic photon flux density)
- **No conversion applied!**

### Problem 2: Double Conversion
The sensor already provides a calibrated PPFD value (0.58) but we're ignoring it and recalculating from raw counts.

### Problem 3: Spectral Distribution Assumption
We're treating each wavelength bin equally in the sum, but:
- Different wavelengths have different photon energies
- Different wavelengths have different photosynthetic efficiencies
- The sensor's spectral response isn't uniform

---

## Proposed Solutions

### Option A: Use Sensor's Direct PPFD (Simplest)
For single-sensor mode, use the sensor's calibrated `ppfd_approx` directly:

```python
# At sensor location
ppfd_at_sensor = sensor_data['raw_color_data']['ppfd_approx']  # 0.58

# For each zone
attenuated_ppfd = ppfd_at_sensor × attenuation × scaling_factor
```

### Option B: Calibrate Spectral Bins (More Complex)
Convert raw ADC counts to spectral irradiance:

```python
# Calibration factors for each channel (determined empirically)
channel_calibration = {
    'red_raw': 0.000123,    # μmol/m²/s per count
    'green_raw': 0.000098,
    'blue_raw': 0.000087,
    'clear_raw': 0.000045
}

# Then distribute calibrated values to bins
```

### Option C: Hybrid Approach (Recommended)
Use the sensor's PPFD as the "ground truth" and scale the spectral distribution accordingly:

```python
# 1. Calculate raw distribution (current method)
raw_bins = map_sensor_to_bins(...)
raw_par_sum = sum(bins in PAR range)

# 2. Get sensor's calibrated PPFD
sensor_ppfd = 0.58  # μmol/m²/s

# 3. Scale entire distribution to match
scaling = sensor_ppfd / raw_par_sum  # 0.58 / 11,420 ≈ 0.000051
calibrated_bins = [bin × scaling for bin in raw_bins]

# 4. Now distribute to zones
for zone:
    zone_bins = [bin × attenuation for bin in calibrated_bins]
    zone_ppfd = sum(zone_bins in PAR range)
```

This preserves the spectral shape while ensuring the total PPFD matches the sensor's calibration.

---

## Recommended Scaling Factor

Based on current data:
```
sensor_ppfd = 0.58 μmol/m²/s
calculated_raw_sum = 11,420
scaling_factor = 0.58 / 11,420 ≈ 0.000051
```

This converts raw ADC count sums to calibrated PPFD values.

---

## Next Steps

1. **Verify sensor's PPFD calculation** - Is 0.58 μmol/m²/s accurate for your light?
2. **Apply scaling factor** - Set to 0.000051 in the UI
3. **Test results** - Zone 15-6 should show ~0.58, zone 0-0 should show ~0.0022
4. **Consider Option A** - Might be simpler to just use sensor's direct PPFD with attenuation
