
# Crane Creek Sensors

## Project Summary (for Copilot Integration)

# Crane Creek Sensors

## Project Summary (for Copilot Integration)

Crane Creek Sensors is an advanced, AI-driven greenhouse monitoring and control system with intelligent light management. It provides real-time data collection, automated device control, Daily Light Integral (DLI) tracking, and sophisticated decision-making algorithms for optimal plant growth while minimizing energy costs.

**🆕 Advanced Features:**
- **Intelligent Light Control**: AI-powered decision engine with 8-factor analysis
- **Daily Light Integral (DLI) Tracking**: Precise daily light exposure monitoring per crop
- **Configurable Energy Optimization**: Custom time-of-use pricing and cost-aware decisions  
- **Spectral Analysis**: Advanced color spectrum measurement and optimization
- **Adaptive Calibration**: Self-learning light calibration with mixed sensor capabilities
- **Zone-Specific Management**: Individual DLI targets and timing per growing zone

**Core Capabilities:**
- Modular sensor support: temperature, humidity, soil moisture, and advanced light sensors (BH1750, TSL2561, VEML7700, TSL2591, AS7341, TCS34725)
- Intelligent device control: relays, PWM fans with energy-aware automation
- Advanced web dashboard: intelligent control, DLI monitoring, spectrum analysis, configuration management
- Comprehensive REST API for integration with other systems
- Runs on Raspberry Pi or in mock mode for development
- JSON-based configuration for zones, lights, sensors, energy pricing, and growth schedules
- Designed for extensibility and integration with larger greenhouse automation projects


**Integration Points:**
- Advanced REST API endpoints for intelligent lighting, DLI monitoring, configuration management
- Real-time decision explanations and cost analysis
- MQTT support for multi-node sensor networks
- Configuration APIs for dynamic updates without restart
- DLI tracking and spectrum analysis APIs
- Easily extendable for additional sensors or actuators
- Can be used as a standalone greenhouse controller or as a subsystem in a larger automation project

**How to Use in a Larger Project:**
- Deploy on a Raspberry Pi or development machine
- Configure crop-specific DLI targets and energy pricing
- Connect sensors and relays as needed
- Use the intelligent control dashboard for monitoring and optimization
- Integrate with other systems via the comprehensive REST API or MQTT
- Access real-time decision explanations and cost analysis

**🎯 What Makes This Special:**
This isn't just a basic sensor monitoring system - it's an intelligent greenhouse brain that makes real-time decisions about lighting based on plant needs, energy costs, ambient conditions, and Daily Light Integral requirements. It learns from your greenhouse and adapts to provide optimal growing conditions while minimizing operating costs.

For more details, see the sections below or contact the project maintainer.

Raspberry Pi-based greenhouse monitoring and control system with web interface.

## Project Structure

```
crane-creek-sensors/
├── README.md
├── requirements.txt
├── requirements-windows.txt     # Windows-specific dependencies
├── sensors/                     # Sensor drivers
│   ├── dht22.py                # Temperature & humidity
│   ├── soil_moisture.py        # Soil moisture via ADC
│   ├── bh1750.py               # Basic light sensor
│   ├── tsl2561.py              # Light sensor with IR
│   ├── tsl2591.py              # Advanced light sensor with spectrum
│   ├── veml7700.py             # High accuracy light sensor
│   └── spectral_sensors.py     # Advanced spectrum sensors (AS7341, TCS34725)
├── control/                     # Device controllers & intelligent systems
│   ├── relay.py                # Relay control
│   ├── fan_controller.py       # PWM fan control
│   ├── light_calibration.py    # 🆕 Main intelligent light control system
│   ├── light_decision_engine.py # 🆕 AI decision making with DLI tracking
│   ├── light_optimizer.py      # 🆕 Advanced optimization algorithms
│   ├── adaptive_calibration.py # 🆕 Self-learning calibration system
│   ├── mixed_capability_optimizer.py # 🆕 Mixed sensor/light optimization
│   └── ambient_light_handler.py # 🆕 Ambient light analysis
├── logging/
│   └── logger.py               # CSV + console logging
├── templates/                  # Web UI templates
│   ├── index.html              # Main dashboard
│   ├── zones.html              # Zone configuration
│   ├── lights.html             # Light configuration
│   ├── calibration.html        # 🆕 Light calibration interface
│   └── intelligent_control.html # 🆕 Intelligent control dashboard
├── static/                     # Web assets
│   ├── style.css               # Styling
│   └── app.js                  # JavaScript
├── data/                       # Configuration & data files
│   ├── zones.json              # Growing zones config with DLI targets
│   ├── lights.json             # Light fixtures configuration
│   ├── light_sensors.json      # Light sensor configuration
│   ├── light_control_config.json # 🆕 Energy pricing & growth schedules
│   ├── light_calibration.json  # 🆕 Calibration data storage
│   ├── dli_tracking.json       # 🆕 Daily Light Integral tracking
│   ├── todos.json              # Task reminders
│   └── errors.json             # Error log
├── main.py                     # Command-line orchestrator
├── web_app.py                  # Flask web server with advanced APIs
├── demonstrate_light_decisions.py # 🆕 Live decision-making demo
├── demonstrate_dli_config.py   # 🆕 DLI & configuration demo
├── demonstrate_ambient_behavior.py # 🆕 Ambient light behavior demo
├── test_adaptive_calibration.py # 🆕 Test suite for calibration
└── docs/ # 📚 Documentation directory
    ├── INTELLIGENT_LIGHT_DECISIONS.md # 🆕 Comprehensive decision system docs
    ├── DLI_AND_CONFIGURATION_FEATURES.md # 🆕 DLI & config feature guide
    └── ADAPTIVE_CALIBRATION_SUMMARY.md # 🆕 Calibration system technical reference
```


## Features

### 🧠 **Intelligent Light Control System**
- **AI-Powered Decisions**: 8-factor decision engine considering plant needs, energy costs, DLI progress, ambient conditions
- **Daily Light Integral (DLI) Tracking**: Precise monitoring of cumulative daily light exposure per crop/zone
- **Configurable Energy Optimization**: Custom time-of-use pricing with peak/off-peak rate optimization
- **Real-Time Decision Explanations**: Understand why the system makes each lighting decision
- **Confidence Scoring**: Reliability assessment for each decision with transparent reasoning

### 🌱 **Advanced Crop Management**
- **Crop-Specific DLI Targets**: Individual daily light requirements for lettuce, basil, tomatoes, herbs, etc.
- **Zone-Level Configuration**: Override defaults with specific DLI targets and timing per growing area
- **Growth Stage Adaptation**: Different light requirements for seedling, vegetative, and flowering stages
- **Priority-Based Scheduling**: High-priority zones get preference during energy constraints

### ⚡ **Energy Intelligence**
- **Cost-Aware Automation**: Reduces lighting during expensive peak energy periods
- **Configurable Time-of-Use Pricing**: Adapt to your utility's specific rate structure
- **Smart Scheduling**: Distributes daily light requirements across cost-effective time periods
- **Energy Cost Tracking**: Real-time cost analysis and optimization recommendations

### 🔬 **Advanced Sensor Support**
- **Multi-Sensor Calibration**: BH1750, TSL2561, VEML7700, TSL2591, AS7341, TCS34725
- **Spectral Analysis**: Color temperature and spectrum measurement for optimal plant lighting
- **Mixed Capability Optimization**: Works with any combination of basic and advanced sensors
- **Ambient Light Intelligence**: Automatically adjusts for natural light conditions

### 🎛️ **Sophisticated Web Interface**
- **Intelligent Control Dashboard**: Real-time DLI progress, decision monitoring, cost analysis
- **Light Calibration Interface**: Automated and manual calibration with optimization algorithms
- **Configuration Management**: Update energy pricing, growth schedules, and DLI targets
- **Spectral Analysis Tools**: Visualize light spectrum and color characteristics
- **Historical Tracking**: Monitor DLI patterns and system performance over time

### 🔧 **Core System Features**
- **Individual & Shared Relay Control**: Cost-effective light control with relay sharing options
- **Sensor Monitoring**: DHT22 (temp/humidity), advanced light sensors, soil moisture
- **Device Control**: Intelligent relay control, PWM fan automation
- **Zone Management**: Configure crops, watering, lighting, and DLI targets per area
- **Logging**: Comprehensive data logging with error tracking and analysis
- **Safe Fallbacks**: Runs on non-RPi machines for development and testing
- **Multi-Node/MQTT Support**: Scalable to multiple devices for distributed control

## Quick Start

### Command Line Mode

1. Create virtual environment and install dependencies:

```powershell
# Set execution policy to allow scripts (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Windows-compatible dependencies
pip install -r requirements-windows.txt

# Alternative: Use full path if activation doesn't work
# .\venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

> **Note**: Use `requirements-windows.txt` for Windows development, which excludes Raspberry Pi-specific libraries (`Adafruit_DHT`, `RPi.GPIO`, `smbus2`). The full `requirements.txt` is for Raspberry Pi deployment.

2. Run the sensor loop or demonstrations:

```powershell
# Basic sensor monitoring
python main.py

# Intelligent light control demonstration
python demonstrate_light_decisions.py

# DLI tracking and configuration demo
python demonstrate_dli_config.py

# Test the calibration system
python test_adaptive_calibration.py
```

### Web Interface Mode

1. Install dependencies (same as above)

2. Start the web server:

```powershell
# If virtual environment is activated:
python web_app.py

# Alternative: Use full path if needed
# .\venv\Scripts\python.exe web_app.py
```

3. Open browser to http://localhost:5000

To run on a different port (e.g., 5001):

```powershell
$env:PORT = "5001"
python web_app.py
```

Diagnostic endpoint to verify template source and paths:

```text
GET /whoami
```
Returns JSON with the Flask app file, CWD, template search path, and the resolved `index.html` template path.

## Advanced Web Interface

### 🧠 **Intelligent Control Dashboard** 
**URL:** `http://localhost:5000/intelligent-control`

The crown jewel of the system - an AI-powered lighting control interface featuring:

- **Real-Time Decision Monitoring**: Watch the system make intelligent lighting decisions
- **DLI Progress Tracking**: Visual progress bars showing daily light accumulation per zone
- **Energy Cost Analysis**: Live cost tracking with time-of-use pricing visualization  
- **Decision Explanations**: Understand exactly why each light is on or off
- **Scenario Testing**: Simulate different conditions (morning, sunny, cloudy, peak energy rates)
- **Configuration Management**: Update energy pricing and growth schedules on-the-fly

### 🔧 **Light Calibration Interface**
**URL:** `http://localhost:5000/calibration`

Professional-grade calibration system with:

- **Automated Calibration**: AI-driven light measurement and optimization
- **Baseline Establishment**: Measure ambient light conditions
- **Individual Light Testing**: Calibrate each fixture independently
- **Optimization Algorithms**: Greedy, linear programming, weighted least squares, multi-objective
- **Spectrum Analysis**: Color temperature and spectrum measurement
- **Mixed Capability Support**: Works with any sensor/light combination

### 📊 **Core Dashboard Features**
**URL:** `http://localhost:5000/`

- **Real-Time Monitoring**: Live sensor readings with DLI integration
- **Zone Grid Editor**: Configure crops and DLI targets per growing area
- **Device Controls**: Manual override for lights, fans, and other equipment
- **Intelligent Overlays**: 
  - Light fixtures with real positioning
  - DLI heatmaps showing daily light distribution
  - Sensor markers with live readings
  - Energy cost visualization

### ⚙️ **Configuration Interfaces**
- **Zone Management** (`/zones`): Crop configuration with DLI targets
- **Light Setup** (`/lights`): Fixture positioning and power settings
- **API Endpoints**: Complete REST API for integration and automation

Diagnostic endpoint to verify system status:
```text
GET /whoami
```
Returns JSON with system information, paths, and configuration status.

## 🚀 **API Reference**

The system provides a comprehensive REST API for integration:

### Core System APIs
```
GET  /api/status                    # System status and sensor readings
GET  /api/zones                     # Zone configuration
POST /api/zones                     # Update zone configuration
GET  /api/lights                    # Light fixture configuration
POST /api/lights                    # Update light configuration
GET  /api/light-sensors             # Sensor configuration and readings
POST /api/light-sensors             # Update sensor configuration
```

### 🧠 Intelligent Control APIs
```
POST /api/lights/intelligent-control   # Make intelligent lighting decisions
GET  /api/lights/automated-cycle       # Run automated control cycle
POST /api/lights/decision-explanation  # Get decision reasoning
GET  /api/lights/control/{light_id}/{action}  # Manual light control
```

### 🌱 DLI (Daily Light Integral) APIs
```
GET  /api/dli/status                # Current DLI status for all zones
GET  /api/dli/status/{zone_key}     # DLI status for specific zone
```

### ⚙️ Configuration APIs
```
GET  /api/config/light-control      # Get current system configuration
POST /api/config/light-control      # Update system configuration
POST /api/config/time-of-use        # Update energy pricing configuration
POST /api/config/growth-schedules   # Update crop growth schedules
```

### 🔧 Calibration APIs
```
GET  /api/calibration               # Get calibration status
POST /api/calibration/start         # Start calibration process
POST /api/calibration/baseline      # Establish baseline readings
POST /api/calibration/light/{id}    # Calibrate individual light
POST /api/calibration/optimize      # Run optimization algorithms
GET  /api/calibration/spectrum-report  # Get spectrum analysis
POST /api/calibration/adaptive      # Run adaptive calibration
POST /api/calibration/mixed-optimization  # Mixed capability optimization
POST /api/calibration/ambient-aware # Ambient-aware calibration
```

### 📊 Example API Usage

**Get DLI Status:**
```bash
curl http://localhost:5000/api/dli/status
```

**Make Intelligent Lighting Decision:**
```bash
curl -X POST http://localhost:5000/api/lights/intelligent-control \
  -H "Content-Type: application/json" \
  -d '{"scenario": "evening", "current_time": "2025-10-12T18:00:00"}'
```

**Update Energy Pricing:**
```bash
curl -X POST http://localhost:5000/api/config/time-of-use \
  -H "Content-Type: application/json" \
  -d '{"peak": {"multiplier": 2.5, "hours": [16,17,18,19,20,21,22]}}'
```

## Configuration

### 📁 **Core Configuration Files**

**`data/zones.json`** - Enhanced zone configuration with DLI targets:
```json
{
  "zones": {
    "A1": {
      "name": "Lettuce Section",
      "crop_type": "lettuce", 
      "growth_stage": "vegetative",
      "dli_config": {
        "target_dli": 14.0,
        "morning_start_time": "06:00",
        "evening_end_time": "20:00",
        "priority": "medium"
      }
    }
  }
}
```

**`data/light_control_config.json`** - Energy pricing and growth schedules:
```json
{
  "energy_cost_per_kwh": 0.12,
  "time_of_use_pricing": {
    "off_peak": {"multiplier": 1.0, "hours": [23,0,1,2,3,4,5]},
    "standard": {"multiplier": 1.5, "hours": [6,7,8,9,10,11,12,13,14,15]}, 
    "peak": {"multiplier": 2.0, "hours": [16,17,18,19,20,21,22]}
  },
  "growth_schedules": {
    "lettuce": {
      "target_dli": 14.0,
      "preferred_start_time": "06:00",
      "preferred_end_time": "20:00"
    }
  }
}
```

**`data/lights.json`** - Light fixtures with positioning and power:
```json
{
  "lights": {
    "led_strip_1": {
      "name": "Full Spectrum LED Strip 1",
      "type": "LED_STRIP",
      "zone_key": "A1",
      "power_watts": 45,
      "gpio_pin": 18,
      "position": {"row": 0, "col": 0, "row_span": 1, "col_span": 2}
    }
  }
}
```

**`data/light_sensors.json`** - Sensor configuration and capabilities:
```json
{
  "sensors": {
    "sensor_1": {
      "name": "TSL2591 Sensor A1",
      "type": "TSL2591", 
      "zone_key": "A1",
      "capabilities": ["lux", "ir", "full_spectrum"]
    }
  }
}
```

### 🔧 **Advanced Configuration**

- **Hardware Configuration**: Pin assignments in `main.py` and `web_app.py`
- **DLI Tracking**: Automatic data storage in `data/dli_tracking.json`
- **Calibration Data**: System-maintained in `data/light_calibration.json`
- **System Tasks**: User reminders in `data/todos.json`
- **Error Logging**: Automatic tracking in `data/errors.json`

All configurations support runtime updates through the web interface or API calls.

## Hardware Notes

- **GPIO Compatibility**: Uses BCM GPIO pin numbering for Raspberry Pi
- **Development-Friendly**: Includes comprehensive mock implementations for development without RPi hardware
- **Sensor Requirements**: 
  - Soil moisture requires an ADC (MCP3008, ADS1115, etc.) - customize `soil_moisture.py`
  - Advanced light sensors (TSL2591, AS7341) provide spectrum analysis capabilities
  - Basic sensors (BH1750, TSL2561) work with intelligent adaptation
- **Graceful Fallbacks**: All GPIO libraries are optional and fall back gracefully
- **Power Management**: System tracks power consumption and optimizes for energy efficiency
- **Mixed Hardware Support**: Works with any combination of basic and advanced sensors/lights

## 📚 **Documentation**

- **[docs/INTELLIGENT_LIGHT_DECISIONS.md](docs/INTELLIGENT_LIGHT_DECISIONS.md)**: Comprehensive guide to the AI decision-making system
- **[docs/DLI_AND_CONFIGURATION_FEATURES.md](docs/DLI_AND_CONFIGURATION_FEATURES.md)**: Complete DLI tracking and configuration guide
- **[docs/ADAPTIVE_CALIBRATION_SUMMARY.md](docs/ADAPTIVE_CALIBRATION_SUMMARY.md)**: Technical reference for adaptive calibration system
- **Demonstration Scripts**: 
  - `demonstrate_light_decisions.py`: Live decision-making examples
  - `demonstrate_dli_config.py`: DLI and configuration features
  - `demonstrate_ambient_behavior.py`: Ambient light handling
- **Test Suite**: `test_adaptive_calibration.py` for system validation


## 📡 Multi-Node Sensor Network Architecture

For larger homesteads or distributed environments, it's often more practical to use multiple microcontrollers or SBCs (Single Board Computers) instead of wiring all sensors into a single Raspberry Pi. This project supports a **master-slave architecture**, where:

- **Master Node** (e.g., Raspberry Pi 5):  
	Hosts the web interface, central logic, and MQTT broker. It aggregates data from all slave nodes and controls global outputs.

- **Slave Nodes** (e.g., ESP32, Pi Pico W, Raspberry Pi Zero 2 W):  
	Handle local sensors and actuators. Each node publishes data to the master via MQTT or HTTP and listens for control commands.

**Configuration:**
- MQTT broker and REST endpoint details can be configured in your master node's code (see `web_app.py` and related modules). For MQTT, you may need to install `paho-mqtt` or similar libraries and set the broker address in your environment or config files.
- Example MQTT/REST integration code for slave nodes is provided below.

### 🔧 Recommended Slave Devices

| Device               | Cost     | Features                         | Notes                          | Example Use Case               |
|----------------------|----------|----------------------------------|--------------------------------|-------------------------------|
| ESP32                | ~$5–$10  | Wi-Fi, GPIO, low power           | Ideal for remote zones         | Soil moisture in far beds      |
| Pi Pico W            | ~$6–$8   | Wi-Fi, fast I/O                  | Great for GPIO-heavy tasks     | Local relay/fan control        |
| Raspberry Pi Zero 2 W| ~$15–$20 | Full Linux, GPIO, Wi-Fi          | Best for zones needing local logic | Mini greenhouse controller     |
| STM32 Blue Pill      | ~$3–$5   | Ultra low power, robust          | Requires more setup            | Battery-powered temp sensor    |

### 🌐 Communication Protocols

- **MQTT** (recommended): Lightweight, scalable, and asynchronous  
- **HTTP/REST**: Easy to implement, good for polling  
- **WebSocket**: Real-time updates, more complex  
- **LoRa**: Long-range, low-bandwidth (optional for remote zones)

#### Example: Publishing Sensor Data via MQTT (Python, ESP32/Pi Pico W)

```python
import paho.mqtt.client as mqtt
import json

broker = "192.168.1.100"  # Set to your master node's IP
topic = "greenhouse/sensors/zone1"
data = {"temperature": 23.5, "humidity": 60}

client = mqtt.Client()
client.connect(broker, 1883, 60)
client.publish(topic, json.dumps(data))
client.disconnect()
```

#### Example: Sending Data via REST (Python, ESP32/Pi Pico W)

```python
import requests
url = "http://192.168.1.100:5000/api/sensors"
data = {"zone": "zone1", "temperature": 23.5, "humidity": 60}
requests.post(url, json=data)
```

This modular approach improves scalability, simplifies wiring, and allows each zone to operate semi-independently. Perfect for greenhouse automation, barn monitoring, coop control, and more.

## Troubleshooting

### 🔧 **System Issues**

**Web Interface Problems:**
- **Grid not visible**: Ensure the grid container uses id `greenhouse-grid`, hard refresh (Ctrl+F5)
- **Overlays misaligned**: Verify grid size in `data/zones.json` and light positions in `data/lights.json`
- **Template issues**: Check `/whoami` endpoint and restart Flask after template changes

**Intelligent Control Issues:**
- **No DLI data**: Check sensor connections and verify readings at `/api/light-sensors`
- **Poor decisions**: Review configuration at `/api/config/light-control` and decision explanations
- **Calibration problems**: Run `test_adaptive_calibration.py` to validate system

**Configuration Issues:**
- **Settings not saving**: Ensure `data/` directory is writable
- **API errors**: Check JSON formatting in configuration files
- **Energy pricing not working**: Verify time-of-use configuration format

### 🚨 **Quick Diagnostics**

```bash
# Check system status
curl http://localhost:5000/api/status

# Verify DLI tracking
curl http://localhost:5000/api/dli/status

# Test intelligent control
curl -X POST http://localhost:5000/api/lights/intelligent-control

# Check configuration
curl http://localhost:5000/api/config/light-control

# System information
curl http://localhost:5000/whoami
```

### 📞 **Getting Help**

1. **Run Demonstrations**: Use the demo scripts to verify system functionality
2. **Check Logs**: Review console output for detailed error messages
3. **API Testing**: Use the diagnostic endpoints to isolate issues
4. **Configuration Validation**: Ensure all JSON files are properly formatted

---

## 🎯 **What Makes This Special**

This isn't just another greenhouse monitoring system. **Crane Creek Sensors** represents the cutting edge of agricultural automation:

- **🧠 AI-Driven**: Makes intelligent decisions like an experienced grower
- **🌱 Science-Based**: Uses Daily Light Integral for precise plant care
- **⚡ Cost-Smart**: Optimizes energy usage with configurable pricing
- **🔧 Adaptive**: Learns and improves performance over time
- **📱 Modern**: Beautiful web interface with real-time monitoring
- **🔌 Flexible**: Works with any hardware combination

Whether you're growing microgreens or managing a commercial operation, this system provides the intelligence and automation to maximize plant health while minimizing costs.

**Ready to revolutionize your greenhouse? Let's grow smarter! 🌱🚀**
