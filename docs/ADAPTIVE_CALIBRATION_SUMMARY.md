# Adaptive Light Calibration System - Implementation Summary

## Overview

The adaptive light calibration system has been successfully implemented to handle your "seemingly random array of different kinds of lights" and mixed sensor capabilities. The system intelligently adapts to each zone's hardware configuration and provides optimal lighting solutions.

**🆕 Recent Enhancements:**
- **Improved Spectral Fusion Logic:** Sensor data is now fused using energy-preserving rescale, with AS7262 channels mapped using Gaussian curves (FWHM 40nm) and other sensors mapped to wavelength bins with proper normalization.
- **Calibration Factor Validation:** Calibration factors are checked and can be set per sensor, ensuring correct scaling and lux calibration for each device.
- **Histogram Analysis:** Graphical and numerical histograms are generated for each sensor and the combined fusion, aiding in calibration and debugging.

## Key Features Implemented

### 1. Mixed Capability Optimization (`control/mixed_capability_optimizer.py`)
- **OptimizationStrategy Enum**: Defines 5 different strategies based on zone capabilities
  - `FULL_SPECTRUM`: For zones with spectral sensors and variable color lights
  - `BASIC_COLOR`: For zones with basic color sensors and some color control
  - `INTENSITY_ONLY`: For zones with only intensity sensors
  - `BEST_EFFORT`: For zones with limited capabilities
  - `MANUAL_FALLBACK`: When automated optimization isn't possible

- **ZoneTarget DataClass**: Comprehensive target specification system
  - Supports PAR, intensity, color temperature, and spectrum ratio targets
  - Includes priority weighting and constraint handling
  - Fallback targets for graceful degradation

- **MixedCapabilityOptimizer Class**: Main optimization engine
  - Automatically selects best strategy per zone
  - Provides detailed feedback on limitations and suggestions
  - Returns confidence scores and accuracy metrics

### 2. Adaptive Zone Calibration (`control/adaptive_calibration.py`)
- **ZoneCapabilityAnalyzer**: Analyzes hardware capabilities per zone
  - Detects sensor types and spectral capabilities
  - Evaluates light types and color control options
  - Determines optimal optimization strategy

- **AdaptiveZoneCalibrator**: Zone-aware calibration system
  - Runs calibration adapted to each zone's capabilities
  - Generates comprehensive capability reports
  - Provides optimization level recommendations

### 3. Enhanced TSL2591 Sensor (`sensors/tsl2591.py`)
- **Visible/Infrared Separation**: Basic color analysis capabilities
- **Color Metrics Calculation**: Simple color temperature estimation
- **Capability Reporting**: Integration with adaptive system
- **Spectrum-Sensitive Features**: For advanced zones

### 4. Integrated Main Calibrator (`control/light_calibration.py`)
- **Adaptive Strategy Integration**: Uses adaptive calibration and mixed optimization
- **Crop-Based Optimization**: Pre-defined targets for common crops (lettuce, basil, tomatoes, herbs)
- **Growth Stage Adaptation**: Modifies targets based on plant growth stage
- **Flexible Zone Targeting**: Converts various request formats to optimization targets

### 5. Web Interface Updates (`web_app.py` & `templates/calibration.html`)
- **Adaptive Calibration Endpoint**: `/api/calibration/adaptive`
- **Zone Capabilities API**: `/api/calibration/capabilities`
- **Mixed Optimization API**: `/api/calibration/mixed-optimization`
- **Enhanced UI**: New buttons and displays for adaptive features
- **Capability Visualization**: Shows zone sensor/light capabilities
- **Strategy Reporting**: Displays which optimization strategy was used per zone

## How It Handles Your Requirements

### "Seemingly Random Array of Different Kinds of Lights"
✅ **Solution**: The system automatically detects each light's capabilities (color control, power, spectrum) and adapts optimization strategies accordingly.

### "Some Will Support Color, Others Only Intensity"
✅ **Solution**: Mixed capability optimizer chooses appropriate strategies:
- Full spectrum optimization for color-capable zones
- Intensity-only optimization for basic zones
- Graceful degradation when capabilities are limited

### "Some Areas Will Have Multiple Light Color Options Some Will Not"
✅ **Solution**: Zone-specific optimization that:
- Uses advanced algorithms for zones with multiple color options
- Falls back to simpler strategies for zones with limited options
- Provides feedback on what's possible in each zone

### "When a Zone is Asking for a Certain Color and Intensity We'll Just Come as Close as We Can"
✅ **Solution**: Best-effort optimization with:
- Confidence scoring for each optimization result
- Detailed feedback on limitations and suggestions
- Fallback targets when exact requirements can't be met

## Usage Examples

### 1. Basic Adaptive Calibration
```python
# Web API
POST /api/calibration/adaptive
# Uses zones.json configuration automatically

# Python
calibrator = LightCalibrator(data_dir='data')
results = calibrator.optimize_zones_with_adaptive_strategy({})
```

### 2. Crop-Based Optimization
```python
crop_types = {
    "A1": "lettuce",
    "A2": "basil", 
    "B1": "tomatoes"
}
growth_stages = {
    "A1": "vegetative",
    "A2": "flowering",
    "B1": "seedling"
}

results = calibrator.optimize_for_mixed_zone_types(crop_types, growth_stages)
```

### 3. Custom Zone Requests
```python
zone_requests = {
    "A1": {
        "target_par": 200,
        "target_color_temp": 4200,
        "target_spectrum": {"blue_percent": 30, "red_percent": 35, "green_percent": 35},
        "intensity_priority": 1.0,
        "color_priority": 0.8
    }
}

results = calibrator.optimize_zones_with_adaptive_strategy(zone_requests)
```

### 4. Zone Capability Analysis
```python
# Check what each zone can do
report = calibrator.get_zone_capability_report()

# Web API
GET /api/calibration/capabilities
```

## Testing
A comprehensive test suite has been created (`test_adaptive_calibration.py`) that:
- Sets up realistic test configurations
- Tests zone capability analysis
- Validates adaptive calibration
- Tests custom optimization requests
- Runs performance analysis across different strategies

## Files Created/Modified
1. **control/mixed_capability_optimizer.py** - Main optimization engine
2. **control/adaptive_calibration.py** - Zone capability analysis
3. **sensors/tsl2591.py** - Enhanced with color capabilities
4. **control/light_calibration.py** - Integrated adaptive features
5. **web_app.py** - Added adaptive API endpoints
6. **templates/calibration.html** - Enhanced UI with adaptive features
7. **test_adaptive_calibration.py** - Comprehensive test suite

## Next Steps
1. **Run Tests**: Execute `python test_adaptive_calibration.py` to verify the system
2. **Configure Hardware**: Set up your actual sensors and lights in the JSON files
3. **Calibrate**: Use the web interface or API to run adaptive calibration
4. **Monitor**: Check zone capability reports to understand your system's capabilities
5. **Optimize**: Use crop-based or custom optimization as needed

The system is now ready to handle your heterogeneous greenhouse lighting setup with intelligent adaptation to whatever hardware capabilities are available in each zone!