# 🌈 TCS34725 RGB Color Sensor Setup Guide

## 📊 What the TCS34725 Can Measure

The TCS34725 is an advanced RGB color sensor that can measure these light qualities:

### 🔬 **Raw Light Measurements**
- **Red Channel** - Intensity of red light (raw counts)
- **Green Channel** - Intensity of green light (raw counts)  
- **Blue Channel** - Intensity of blue light (raw counts)
- **Clear Channel** - Total light intensity (all wavelengths)

### 🌡️ **Calculated Light Properties**
- **Color Temperature** - Warmth/coolness in Kelvin (2700K = warm, 6500K = daylight)
- **Illuminance (Lux)** - Brightness level for human perception
- **RGB Ratios** - Percentage breakdown of color balance

### 🎨 **Practical Applications for Grow Lights**
- **Spectrum Analysis** - Identify red/blue LED ratios in grow lights
- **Color Consistency** - Monitor if lights maintain consistent color output
- **Light Type Detection** - Distinguish between incandescent, LED, fluorescent
- **White Balance** - Measure warm vs cool white LEDs
- **Multi-Channel LED Control** - Identify which color channels are active

## 🔌 Hardware Wiring (I2C)

### **Pin Connections**
```
TCS34725 Breakout → Raspberry Pi
VCC/VIN         → 3.3V (Pin 1) or 5V (Pin 2)
GND             → Ground (Pin 6, 9, 14, 20, 25, 30, 34, 39)
SDA             → GPIO 2 (Pin 3) - I2C Data
SCL             → GPIO 3 (Pin 5) - I2C Clock
```

### **🚨 CRITICAL: LED Disable for Ambient Light**
**For accurate ambient light readings, you MUST disable the onboard LED:**

1. **Locate the LED pin** on your TCS34725 breakout board
2. **Jumper LED pin to GND** using a short wire or solder bridge
3. **Verify LED is OFF** - no white light should emit from the sensor

```
TCS34725 LED Disable:
LED pin → GND (any ground pin on the breakout)
```

**Why this matters:** The onboard LED can add 1000+ lux to readings, completely masking actual ambient light conditions.

### **I2C Configuration**
- **Default Address**: `0x29` (can't be changed)
- **Bus Speed**: Standard 100kHz or Fast 400kHz
- **Pull-up Resistors**: Usually included on breakout boards

### **Power Requirements**
- **Voltage**: 3.3V or 5V tolerant
- **Current**: ~200µA typical operation
- **Enable I2C**: `sudo raspi-config` → Interface Options → I2C → Enable

## 🧪 Testing Your Sensor

### **Quick Test**
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\Activate.ps1  # Windows

# Run the test script
python test_tcs34725.py
```

### **Expected Output**
```
🌈 TCS34725 RGB Color Sensor Test
==================================================
🔴 Red:    1234 ( 35.2%)
🟢 Green: 1456 ( 41.6%) 
🔵 Blue:   813 ( 23.2%)
⚪ Clear: 3503
🌡️  Temp:  4200K
💡 Lux:   125.3
📊 Analysis: 🌞 Bright | 💡 Neutral white | 🎨 Green-tinted
```

### **Troubleshooting**
| Problem | Solution |
|---------|----------|
| "Failed to initialize" | Check I2C wiring, enable I2C in raspi-config |
| All readings are 0 | No light source, or sensor covered |
| Erratic readings | Check power supply stability |
| Import errors | Install requirements: `pip install -r requirements.txt` |

## 🌱 Integration with Grow Light System

Once tested, the TCS34725 integrates with your intelligent light system:

### **Configuration**
Add your sensor to `data/light_sensors.json`:
```json
{
  "sensors": {
    "ls-tcs34725-1": {
      "name": "TCS34725 Sensor",
      "type": "TCS34725",
      "connection": { "bus": 1, "address": 41 },
      "zone_key": "A1"
    }
  }
}
```

### **Decision Making Integration**
The intelligent light system will use TCS34725 data for:
- **Spectrum Validation** - Verify grow lights produce expected color ratios
- **Color Consistency** - Detect when LEDs degrade or change color
- **Multi-Channel Control** - Optimize red/blue ratios based on plant needs
- **Energy Efficiency** - Identify underperforming or failed color channels

## 🔬 Understanding the Data

### **Color Temperature Guide**
- **2700K-3000K**: Warm white (like incandescent) - good for flowering
- **3000K-4000K**: Neutral warm - general purpose
- **4000K-5000K**: Cool white - good for vegetative growth  
- **5000K-6500K**: Daylight - excellent for photosynthesis
- **6500K+**: Cool daylight - may appear blue-tinted

### **RGB Ratio Interpretation**
- **Balanced (33/33/33%)**: White light sources
- **High Red (>40%)**: Grow lights, incandescent, sunset
- **High Blue (>40%)**: Cool LEDs, sky light, some grow lights
- **High Green (>40%)**: Fluorescent, some specialized grow lights

### **Lux Levels for Plants**
- **<100 lux**: Too dim for most plants
- **100-500 lux**: Low light plants (some houseplants)
- **500-2000 lux**: Medium light requirements
- **2000-10000 lux**: High light plants, vegetative growth
- **10000+ lux**: Maximum intensity, flowering/fruiting

## 🚀 Next Steps

1. **Wire up your TCS34725** following the pin diagram above
2. **Run the test script** to verify it's working
3. **Test different light sources** to understand the readings
4. **Integrate with your zones** by updating the configuration
5. **Monitor spectrum changes** as your grow lights operate

The TCS34725 gives you valuable insight into your grow light color spectrum and consistency! 🌈🌱