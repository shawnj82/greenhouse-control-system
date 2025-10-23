# Daily Light Integral (DLI) & Configuration Features

## 🌱 Daily Light Integral (DLI) System

**🆕 Sensor Mapping & Calibration Enhancements:**
- Sensor data used for DLI tracking now benefits from improved spectral fusion logic:
  - **AS7262:** Gaussian mapping (FWHM 40nm) for each channel, energy-preserving integration
  - **TCS34725:** Normalized RGB+clear mapping, with raw counts normalized by gain/integration time
  - **TSL2591:** Broadband/visible/IR split, mapped to wavelength bins
- Calibration factors are validated and can be set per sensor for precise adjustment
- All sensor fusion is energy-preserving, ensuring accurate DLI calculation and cross-sensor consistency

### What is DLI?
Daily Light Integral (DLI) measures the total amount of photosynthetically active radiation (PAR) a plant receives over a 24-hour period, expressed in mol/m²/day. This is crucial for:

- **Optimal Growth**: Each plant type has specific DLI requirements
- **Energy Efficiency**: Prevents over-lighting and waste
- **Quality Control**: Ensures consistent light exposure
- **Timing Optimization**: Distributes light throughout the day

### DLI Tracking Features

#### 📊 Real-Time Calculation
- Converts lux readings to PPFD (μmol/m²/s)
- Accumulates DLI throughout the day
- Tracks progress against plant-specific targets
- Stores historical data for analysis

#### 🎯 Plant-Specific Targets
```json
{
  "lettuce": {"target_dli": 14.0},
  "basil": {"target_dli": 16.0},
  "tomatoes": {"target_dli": 20.0},
  "herbs": {"target_dli": 12.0},
  "seedlings": {"target_dli": 10.0},
  "flowering": {"target_dli": 25.0}
}
```

#### 🏭 Zone-Level Configuration
Each zone can override default crop settings:
```json
{
  "A1": {
    "dli_config": {
      "target_dli": 14.0,
      "morning_start_time": "06:00",
      "evening_end_time": "20:00",
      "priority": "medium"
    }
  }
}
```

#### 🧠 DLI-Based Decision Making
The system now considers DLI progress when making light decisions:

1. **Early in Day**: Higher intensity to meet targets
2. **Target Met**: Reduce intensity to maintain (not exceed)
3. **Over Target**: Turn lights off to prevent damage
4. **End of Period**: Stop lighting even if target not met

### DLI API Endpoints

```http
GET /api/dli/status
GET /api/dli/status/{zone_key}
```

**Response Example:**
```json
{
  "success": true,
  "dli_status": {
    "A1": {
      "crop_type": "lettuce",
      "target_dli": 14.0,
      "current_dli": 8.5,
      "progress_percent": 60.7,
      "remaining_dli": 5.5,
      "is_target_met": false,
      "remaining_hours": 6.5
    }
  }
}
```

## ⚡ Configurable Time-of-Use Pricing

### Dynamic Energy Pricing
Replace hardcoded pricing with configurable time-based rates:

```json
{
  "time_of_use_pricing": {
    "off_peak": {
      "multiplier": 1.0,
      "hours": [23, 0, 1, 2, 3, 4, 5],
      "description": "11 PM - 6 AM"
    },
    "standard": {
      "multiplier": 1.5,
      "hours": [6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
      "description": "6 AM - 4 PM"
    },
    "peak": {
      "multiplier": 2.0,
      "hours": [16, 17, 18, 19, 20, 21, 22],
      "description": "4 PM - 11 PM"
    }
  }
}
```

### Smart Energy Decisions
- **Off-Peak**: Full lighting intensity
- **Standard**: Normal optimization
- **Peak**: Reduce intensity unless critical for DLI targets

### Configuration API

```http
GET /api/config/light-control
POST /api/config/light-control
POST /api/config/time-of-use
```

## 🌅 Configurable Morning Turn-On Times

### Crop-Specific Schedules
Each crop type can have different lighting schedules:

```json
{
  "lettuce": {
    "preferred_start_time": "06:00",
    "preferred_end_time": "20:00",
    "light_hours_per_day": 14
  },
  "basil": {
    "preferred_start_time": "05:00",
    "preferred_end_time": "21:00",
    "light_hours_per_day": 16
  }
}
```

### Zone-Level Overrides
Individual zones can override crop defaults:

```json
{
  "A1": {
    "dli_config": {
      "morning_start_time": "05:30",
      "evening_end_time": "20:30"
    }
  }
}
```

### Priority-Based Scheduling
Zones with "high" priority may start earlier during energy constraints.

## 🔧 Configuration Management

### Persistent Settings
All configurations are automatically saved to `data/light_control_config.json`:

- Energy pricing rates
- Growth schedules
- DLI targets
- Light timing preferences

### Runtime Updates
Configurations can be updated without restarting:

```python
# Update time-of-use pricing
decision_engine.update_time_of_use_pricing(new_pricing)

# Update growth schedule
decision_engine.update_growth_schedule('lettuce', new_schedule)

# Update energy cost
decision_engine.update_energy_cost(0.15)
```

### Configuration API

```http
POST /api/config/growth-schedules
```

**Request Body:**
```json
{
  "lettuce": {
    "light_hours_per_day": 16,
    "preferred_start_time": "05:30",
    "preferred_end_time": "21:30",
    "target_dli": 16.0
  }
}
```

## 📊 Enhanced Web Dashboard

### DLI Status Display
The intelligent control dashboard now shows:

- Real-time DLI progress for each zone
- Progress bars with color coding
- Remaining DLI and light hours
- Target vs. current values

### Visual Indicators
- 🟢 **Green**: Target met (90-110%)
- 🟡 **Yellow**: Behind target (<70%)
- 🔴 **Red**: Over target (>110%)

### Auto-Refresh
DLI status updates automatically every 10 seconds when auto-refresh is enabled.

## 🎯 Decision Engine Enhancements

### New Decision Factors

1. **DLI Progress**: Adjusts intensity based on daily accumulation
2. **Configurable Energy Pricing**: Uses custom time-of-use rates
3. **Zone-Specific Timing**: Respects individual zone schedules
4. **Priority Weighting**: High-priority zones get preference

### Enhanced Confidence Scoring
DLI progress affects decision confidence:
- High confidence when DLI data is complete
- Reduced confidence when targets are uncertain
- Increased confidence for well-calibrated zones

### Smart Optimization
The system now balances:
- Plant DLI requirements
- Energy cost optimization
- Equipment efficiency
- Zone-specific priorities

## 📈 Usage Examples

### 1. Basic DLI Tracking
```python
from control.light_decision_engine import DLITracker

tracker = DLITracker()
reading = tracker.add_reading('A1', 1500, duration_minutes=5)
daily_dli = tracker.get_daily_dli('A1')
```

### 2. Configuration Updates
```python
# Update pricing for your utility company
new_pricing = {
    'off_peak': {'multiplier': 0.8, 'hours': [0, 1, 2, 3, 4, 5, 6]},
    'peak': {'multiplier': 3.0, 'hours': [17, 18, 19, 20, 21]}
}
decision_engine.update_time_of_use_pricing(new_pricing)
```

### 3. Zone-Specific DLI Targets
```python
# Get DLI status for specific zone
status = decision_engine.get_dli_status('A1')
print(f"DLI Progress: {status['A1']['progress_percent']:.0f}%")
```

## 🚀 Getting Started

### 1. Configuration Setup
Create `data/light_control_config.json` with your settings:

```bash
curl -X GET http://localhost:5000/api/config/light-control
```

### 2. Update Zone Configurations
Add DLI targets to your zones:

```json
{
  "zones": {
    "A1": {
      "dli_config": {
        "target_dli": 15.0,
        "morning_start_time": "06:00",
        "priority": "high"
      }
    }
  }
}
```

### 3. Monitor DLI Progress
Visit the intelligent control dashboard:
```
http://localhost:5000/intelligent-control
```

### 4. API Integration
Use the DLI API to integrate with other systems:

```javascript
// Get current DLI status
fetch('/api/dli/status')
  .then(response => response.json())
  .then(data => console.log(data.dli_status));
```

## 🎯 Benefits

### For Plants
- **Optimal Growth**: Precise DLI targeting for each crop
- **Consistent Quality**: Uniform daily light exposure
- **Reduced Stress**: Prevents over/under lighting

### For Energy Efficiency
- **Cost Optimization**: Avoids peak energy rates when possible
- **Smart Scheduling**: Distributes lighting across time periods
- **Waste Reduction**: Stops lighting when targets are met

### for Operations
- **Flexibility**: Easy configuration changes
- **Monitoring**: Real-time DLI tracking and alerts
- **Automation**: Hands-off operation with intelligent decisions

This enhanced system provides the foundation for truly intelligent greenhouse lighting that adapts to your specific crops, energy costs, and operational requirements!