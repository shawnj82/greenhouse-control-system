# NOTE: Duplicate imports and a second Flask app instantiation previously existed
# here, which caused early-registered routes (like /api/zone-fusion) to be lost
# when the second app = Flask(__name__) overwrote the first. This has been
# cleaned up so there is only one import block and one Flask app.

# Direct sensor imports for Flask endpoints that reference them
from sensors.dht22 import DHT22
from sensors.bh1750 import BH1750
from sensors.tsl2561 import TSL2561
from sensors.veml7700 import VEML7700
from sensors.tsl2591 import TSL2591
from sensors.spectral_sensors import TCS34725Color, SpectralSensorReader
"""Flask web server for greenhouse control interface."""
import json
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
import atexit
import atexit

# Import our sensor and control modules
from sensors.soil_moisture import SoilMoisture
from control.relay import Relay
import time
from control.fan_controller import FanController
from control.light_calibration import LightCalibrator
from sensor_shared import DATA_DIR, _app_config, read_light_sensor
from control.spectral_fusion import SpectralDataFusion, estimate_midpoint_spectrum
# No internal scheduler imports; Flask reads from shared file

app = Flask(__name__)

# Data directory for configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

ZONES_FILE = os.path.join(DATA_DIR, "zones.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
ERRORS_FILE = os.path.join(DATA_DIR, "errors.json")
TODOS_FILE = os.path.join(DATA_DIR, "todos.json")
LIGHTS_FILE = os.path.join(DATA_DIR, "lights.json")
LIGHT_SENSORS_FILE = os.path.join(DATA_DIR, "light_sensors.json")
CALIBRATION_FILE = os.path.join(DATA_DIR, "light_calibration.json")
COLOR_TEMP_PROFILES_FILE = os.path.join(DATA_DIR, "color_temperature_profiles.json")
USER_SETTINGS_FILE = os.path.join(DATA_DIR, "user_settings.json")

# Initialize hardware (with fallbacks)
dht = DHT22(pin=4)
light_sensor = BH1750()
soil_sensor = SoilMoisture()
grow_light = Relay(pin=17, active_high=True)
heater = Relay(pin=27, active_high=True)
fan = FanController(pin=22)

# Initialize light calibrator
light_calibrator = None

# Flask does not start or stop the scheduler; it's a separate service.

# --- Zone Fusion API (moved here AFTER the single app instance is created) ---
@app.route('/api/zone-fusion', methods=['GET'])
def api_zone_fusion():
    """API endpoint to get per-zone fusion, lux, and PPFD values.
    
    Now redirects to zone_light_metrics.json since zone data has been removed
    from sensor_readings.json to keep files smaller and better organized.
    """
    metrics_file = os.path.join(DATA_DIR, "zone_light_metrics.json")
    if not os.path.exists(metrics_file):
        return jsonify({"error": "Zone fusion data not available"}), 503
    try:
        with open(metrics_file, "r") as f:
            data = json.load(f)
        # Return in expected format with 'zone_fusion' key for compatibility
        return jsonify({"zone_fusion": data.get("zones", {}), "timestamp": data.get("timestamp")})
    except Exception as e:
        return jsonify({"error": f"Failed to read zone fusion: {e}"}), 500


@app.route('/api/zone-light-metrics', methods=['GET'])
def api_zone_light_metrics():
    """API endpoint to get per-zone light metrics (lux, PPFD, intensities) without spectrum bin definitions."""
    metrics_file = os.path.join(DATA_DIR, "zone_light_metrics.json")
    if not os.path.exists(metrics_file):
        return jsonify({"error": "Zone light metrics not available"}), 503
    try:
        with open(metrics_file, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Failed to read zone light metrics: {e}"}), 500


@app.route('/api/spectrum-bins', methods=['GET'])
def api_spectrum_bins():
    """API endpoint to get the static spectrum bin definitions."""
    bins_file = os.path.join(DATA_DIR, "spectrum_bins.json")
    if not os.path.exists(bins_file):
        return jsonify({"error": "Spectrum bins not available"}), 503
    try:
        with open(bins_file, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Failed to read spectrum bins: {e}"}), 500


def get_light_calibrator():
    """Get or create light calibrator instance."""
    global light_calibrator
    if light_calibrator is None:
        light_calibrator = LightCalibrator(data_dir=DATA_DIR)
    return light_calibrator

# Simple in-memory cache for sensor readings
_light_sensor_cache = {
    "readings": {},  # { sensor_id: { lux, ts } }
    "ttl_sec": 5
}

# Cache for physical sensor instances to avoid expensive re-initialization
_sensor_instance_cache = {}  # key: (type,bus,addr) -> instance

# Configuration settings
_app_config = {
    "sensor_cache_ttl": 5,          # Backend cache TTL in seconds (legacy)
    "frontend_update_interval": 10   # Frontend update interval in seconds
}

# Default user settings (units & light display)
_user_settings_defaults = {
    "temperature_unit": "C",  # C or F
    "distance_unit": "in",    # in or cm
    "light_unit": "lux"       # lux or par
}

def load_user_settings():
    data = load_json_file(USER_SETTINGS_FILE, _user_settings_defaults.copy())
    # Ensure missing keys are filled with defaults
    updated = False
    for k, v in _user_settings_defaults.items():
        if k not in data:
            data[k] = v
            updated = True
    if updated:
        save_json_file(USER_SETTINGS_FILE, data)
    return data

def save_user_settings(data):
    # Only allow known keys and values
    cleaned = {
        "temperature_unit": data.get("temperature_unit", _user_settings_defaults["temperature_unit"]).upper(),
        "distance_unit": data.get("distance_unit", _user_settings_defaults["distance_unit"]).lower(),
        "light_unit": data.get("light_unit", _user_settings_defaults["light_unit"]).lower()
    }
    if cleaned["temperature_unit"] not in ("C", "F"):
        cleaned["temperature_unit"] = _user_settings_defaults["temperature_unit"]
    if cleaned["distance_unit"] not in ("in", "cm"):
        cleaned["distance_unit"] = _user_settings_defaults["distance_unit"]
    if cleaned["light_unit"] not in ("lux", "par"):
        cleaned["light_unit"] = _user_settings_defaults["light_unit"]
    save_json_file(USER_SETTINGS_FILE, cleaned)
    return cleaned


# Background scheduler for sensor readings
_sensor_scheduler = None  # Deprecated; Flask no longer manages internal scheduler



# Ensure scheduler is started after read_light_sensor is defined
# (place just before __main__ block)

def load_json_file(filepath, default=None):
    """Load JSON file with fallback to default."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return default or {}

def save_json_file(filepath, data):
    """Save data to JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

def get_current_status():
    """Get current sensor readings and device states."""
    # Prefer zone-level light metrics for dashboard summary (matches heatmap)
    light_lux = None
    light_ppfd = None
    metrics_file = os.path.join(DATA_DIR, "zone_light_metrics.json")
    try:
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                z = json.load(f)
            zones = z.get("zones", {}) or {}
            # Average across valid zones for a stable summary
            lux_vals = []
            ppfd_vals = []
            for zone in zones.values():
                if zone is None:
                    continue
                if zone.get("valid", True):
                    lx = zone.get("lux")
                    if isinstance(lx, (int, float)):
                        lux_vals.append(float(lx))
                    pv = zone.get("ppfd")
                    if isinstance(pv, (int, float)):
                        ppfd_vals.append(float(pv))
            if lux_vals:
                light_lux = sum(lux_vals) / max(1, len(lux_vals))
            if ppfd_vals:
                light_ppfd = sum(ppfd_vals) / max(1, len(ppfd_vals))
    except Exception as e:
        print(f"[Dashboard] Failed to read zone light metrics: {e}")

    # Legacy fallback: read first sensor's light_metrics from sensor_readings.json
    if light_lux is None and light_ppfd is None:
        readings_file = os.path.join(DATA_DIR, "sensor_readings.json")
        if os.path.exists(readings_file):
            try:
                with open(readings_file, "r") as f:
                    data = json.load(f)
                    readings = data.get("readings", {})
                    if readings:
                        first_reading = next(iter(readings.values()), {})
                        light_metrics = first_reading.get("light_metrics", {})
                        light_lux = light_metrics.get("lux", {}).get("value")
                        light_ppfd = light_metrics.get("PPFD", {}).get("value")
            except Exception as e:
                print(f"[Dashboard] Failed to read sensor readings file: {e}")
    
    # For other sensors, try quick reads with timeouts, fall back to None on failure
    dht_data = {}
    soil_moisture = None
    try:
        # Quick DHT read with short timeout
        dht_data = dht.read() or {}
    except Exception:
        pass  # Use None values on timeout/error
    
    try:
        # Quick soil moisture read
        soil_moisture = soil_sensor.moisture_percent()
    except Exception:
        pass  # Use None on timeout/error
    
    return {
        "timestamp": datetime.now().isoformat(),
        "temperature_c": dht_data.get("temperature_c"),
        "humidity": dht_data.get("humidity"),
        "light_lux": light_lux,
    "soil_moisture": soil_moisture,
    "light_ppfd": light_ppfd,
        "devices": {
            "grow_light": "on",  # Would track actual state in real implementation
            "heater": "off",
            "fan_speed": 0
        }
    }

@app.route('/')
def index():
    """Main dashboard page."""
    status = get_current_status()
    zones = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
    errors = load_json_file(ERRORS_FILE, {"errors": []})
    todos = load_json_file(TODOS_FILE, {"todos": []})
    
    user_settings = load_user_settings()
    return render_template('index.html', 
                         status=status, 
                         zones=zones, 
                         recent_errors=errors.get("errors", [])[-5:],
                         todos=todos.get("todos", []),
                         user_settings=user_settings)

@app.route('/zones')
def zones_page():
    """Zones configuration page."""
    zones = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
    return render_template('zones.html', zones=zones)

@app.route('/lights')
def lights_page():
    """Lights configuration page."""
    lights = load_json_file(LIGHTS_FILE, {"lights": {}})
    zones = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
    user_settings = load_user_settings()
    return render_template('lights.html', lights=lights, zones=zones, user_settings=user_settings)

@app.route('/intelligent-control')
def intelligent_control_page():
    """Render the intelligent light control dashboard."""
    return render_template('intelligent_control.html')

@app.route('/calibration')
def calibration_page():
    """Light calibration page."""
    calibration = load_json_file(CALIBRATION_FILE, {})
    lights = load_json_file(LIGHTS_FILE, {"lights": {}})
    sensors = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}})
    zones = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
    
    return render_template('calibration.html', 
                         calibration=calibration,
                         lights=lights, 
                         sensors=sensors,
                         zones=zones)

@app.route('/api/status')
def api_status():
    """API endpoint for current status."""
    return jsonify(get_current_status())

@app.route('/api/zones', methods=['GET', 'POST'])
def api_zones():
    """API for zones configuration."""
    if request.method == 'GET':
        zones = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
        return jsonify(zones)
    
    elif request.method == 'POST':
        data = request.get_json()
        if save_json_file(ZONES_FILE, data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save zones"}), 500

@app.route('/api/lights', methods=['GET', 'POST'])
def api_lights():
    """API for lights configuration and control."""
    if request.method == 'GET':
        lights = load_json_file(LIGHTS_FILE, {"lights": {}})
        return jsonify(lights)
    
    elif request.method == 'POST':
        try:
            lights_data = request.get_json()
            
            # Validate and enhance light configurations
            for light_id, light_config in lights_data.get("lights", {}).items():
                # Ensure control configuration exists
                if "control" not in light_config:
                    light_config["control"] = {
                        "type": "none",
                        "description": "No hardware control configured"
                    }
                
                # Validate control configuration
                control_type = light_config["control"].get("type", "none")
                if control_type == "gpio":
                    # Validate GPIO configuration
                    if "pin" not in light_config["control"]:
                        light_config["control"]["pin"] = None
                        light_config["control"]["description"] = "GPIO pin not configured"
                    # Default invert logic to False if not present
                    if "active_low" not in light_config["control"]:
                        light_config["control"]["active_low"] = False
                elif control_type == "pwm":
                    # Validate PWM configuration
                    if "pin" not in light_config["control"]:
                        light_config["control"]["pin"] = None
                    if "frequency" not in light_config["control"]:
                        light_config["control"]["frequency"] = 1000  # Default 1kHz
                elif control_type == "rgb":
                    # Validate RGB configuration
                    if "pins" not in light_config["control"]:
                        light_config["control"]["pins"] = {"red": None, "green": None, "blue": None}
                elif control_type == "i2c":
                    # Validate I2C configuration
                    if "address" not in light_config["control"]:
                        light_config["control"]["address"] = None
                    if "bus" not in light_config["control"]:
                        light_config["control"]["bus"] = 1
            
            if save_json_file(LIGHTS_FILE, lights_data):
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to save lights configuration"}), 500
                
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/lights/<light_id>/control', methods=['POST'])
def api_light_control(light_id):
    """Control individual light based on its hardware configuration."""
    try:
        lights = load_json_file(LIGHTS_FILE, {"lights": {}})
        
        if light_id not in lights.get("lights", {}):
            return jsonify({"success": False, "error": "Light not found"}), 404
        
        light_config = lights["lights"][light_id]
        control_config = light_config.get("control", {})
        control_type = control_config.get("type", "none")
        
        request_data = request.get_json()
        action = request_data.get("action")  # "on", "off", "dim", "color"
        value = request_data.get("value", 100)  # dimming level or color values
        
        result = control_light_hardware(light_id, light_config, action, value)
        
        if result["success"]:
            # Update the light status in configuration
            if action in ["on", "off"]:
                lights["lights"][light_id]["status"] = action
            if action == "dim" and "dimming_level" in lights["lights"][light_id]:
                lights["lights"][light_id]["dimming_level"] = value
            
            save_json_file(LIGHTS_FILE, lights)
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def control_light_hardware(light_id, light_config, action, value=100):
    """Control light hardware based on configuration."""
    control_config = light_config.get("control", {})
    control_type = control_config.get("type", "none")
    
    try:
        if control_type == "none":
            return {"success": True, "message": "No hardware control configured - status updated in software only"}
        
        elif control_type == "gpio":
            # Simple GPIO on/off control
            pin = control_config.get("pin")
            if pin is None:
                return {"success": False, "error": "GPIO pin not configured"}
            
            active_low = bool(control_config.get("active_low", False))
            on_val = 0 if active_low else 1
            off_val = 1 if active_low else 0
            
            import lgpio
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(h, pin)
            
            if action == "on":
                lgpio.gpio_write(h, pin, on_val)
                lgpio.gpiochip_close(h)
                return {"success": True, "message": f"Light {light_id} turned ON via GPIO pin {pin}{' (active_low)' if active_low else ''}"}
            elif action == "off":
                lgpio.gpio_write(h, pin, off_val)
                lgpio.gpiochip_close(h)
                return {"success": True, "message": f"Light {light_id} turned OFF via GPIO pin {pin}{' (active_low)' if active_low else ''}"}
            else:
                lgpio.gpiochip_close(h)
                return {"success": False, "error": "GPIO control only supports on/off actions"}
        
        elif control_type == "pwm":
            # PWM dimming control
            pin = control_config.get("pin")
            frequency = control_config.get("frequency", 1000)
            if pin is None:
                return {"success": False, "error": "PWM pin not configured"}
            
            # Note: lgpio doesn't have built-in PWM, so we'll use simple GPIO for now
            # For true PWM, you'd need hardware PWM or a separate PWM library
            import lgpio
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(h, pin)
            
            if action == "on":
                lgpio.gpio_write(h, pin, 1)
                lgpio.gpiochip_close(h)
                return {"success": True, "message": f"Light {light_id} turned ON via PWM pin {pin} (using GPIO)"}
            elif action == "off":
                lgpio.gpio_write(h, pin, 0)
                lgpio.gpiochip_close(h)
                return {"success": True, "message": f"Light {light_id} turned OFF via PWM pin {pin}"}
            elif action == "dim":
                # For dimming, we'll just turn on (future enhancement could use actual PWM)
                lgpio.gpio_write(h, pin, 1 if value > 0 else 0)
                lgpio.gpiochip_close(h)
                return {"success": True, "message": f"Light {light_id} set to {'ON' if value > 0 else 'OFF'} via PWM pin {pin} (dimming not fully implemented)"}
            else:
                lgpio.gpiochip_close(h)
                return {"success": False, "error": "Invalid action for PWM control"}
        
        elif control_type == "rgb":
            # RGB LED control
            pins = control_config.get("pins", {})
            red_pin = pins.get("red")
            green_pin = pins.get("green") 
            blue_pin = pins.get("blue")
            
            if not all([red_pin, green_pin, blue_pin]):
                return {"success": False, "error": "RGB pins not fully configured"}
            
            # This would implement RGB control logic
            return {"success": True, "message": f"RGB control not yet implemented for light {light_id}"}
        
        elif control_type == "i2c":
            # I2C device control
            address = control_config.get("address")
            bus = control_config.get("bus", 1)
            
            if address is None:
                return {"success": False, "error": "I2C address not configured"}
            
            # This would implement I2C control logic
            return {"success": True, "message": f"I2C control not yet implemented for light {light_id}"}
        
        else:
            return {"success": False, "error": f"Unknown control type: {control_type}"}
            
    except Exception as e:
        return {"success": False, "error": f"Hardware control error: {str(e)}"}

@app.route('/api/light-sensors', methods=['GET', 'POST'])
def api_light_sensors():
    """API for light sensors configuration and readings."""
    global _sensor_scheduler

    if request.method == 'GET':
        # Read from shared sensor readings file written by scheduler service
        readings_file = os.path.join(DATA_DIR, "sensor_readings.json")
        config_file = os.path.join(DATA_DIR, "light_sensors.json")
        if os.path.exists(readings_file):
            try:
                with open(readings_file, "r") as f:
                    data = json.load(f)
                # Merge in config.sensors from light_sensors.json
                if os.path.exists(config_file):
                    try:
                        with open(config_file, "r") as cf:
                            config_data = json.load(cf)
                        data["config"] = {"sensors": config_data.get("sensors", {})}
                    except Exception as ce:
                        print(f"[API] Failed to read light_sensors.json: {ce}")
                        data["config"] = {"sensors": {}}
                else:
                    data["config"] = {"sensors": {}}
                return jsonify(data)
            except Exception as e:
                print(f"[API] Failed to read sensor readings file: {e}")
                return jsonify({"error": "Failed to read sensor readings file"}), 500
        else:
            return jsonify({"error": "Sensor readings not available"}), 503

    elif request.method == 'POST':
        data = request.get_json()
        if save_json_file(LIGHT_SENSORS_FILE, data):
            # Trigger scheduler to reload config
            scheduler = _sensor_scheduler
            if scheduler:
                scheduler.force_update()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save light sensors"}), 500

@app.route('/api/scheduler/control', methods=['POST'])
def api_scheduler_control():
    """Control the background scheduler (start/stop/update interval)."""
    global _sensor_scheduler
    try:
        data = request.get_json()
        action = data.get("action")
        
        if action == "force_update":
            scheduler = _sensor_scheduler
            if scheduler:
                scheduler.force_update()
                return jsonify({"success": True, "message": "Forced sensor update"})
            else:
                return jsonify({"success": False, "error": "Scheduler not running"}), 400
        elif action == "set_interval":
            interval = data.get("interval", 5.0)
            scheduler = _sensor_scheduler
            if scheduler:
                scheduler.set_update_interval(float(interval))
                return jsonify({"success": True, "message": f"Update interval set to {interval}s"})
            else:
                return jsonify({"success": False, "error": "Scheduler not running"}), 400
        else:
            return jsonify({"success": False, "error": "Unknown action"}), 400
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/light-sensors/debug', methods=['GET'])
def api_light_sensors_debug():
    """Debug endpoint to read raw data from configured light sensors."""
    try:
        sensors_cfg = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}}).get("sensors", {})
        results = {}
        for sid, cfg in sensors_cfg.items():
            stype = (cfg.get("type") or "").upper()
            conn = cfg.get("connection", {})
            bus = conn.get("bus", 1)
            if stype == "TCS34725":
                addr = conn.get("address", TCS34725Color.DEFAULT_ADDR)
                mux_addr = conn.get("mux_address")
                mux_ch = conn.get("mux_channel")
                cache_key = ("TCS34725", bus, addr, mux_addr, mux_ch)
                sensor = _sensor_instance_cache.get(cache_key)
                if sensor is None:
                    sensor = TCS34725Color(bus=bus, addr=addr, mux_address=mux_addr, mux_channel=mux_ch)
                    _sensor_instance_cache[cache_key] = sensor
                color = sensor.read_color()
                results[sid] = {
                    "type": stype,
                    "raw": color,
                    "zone_key": cfg.get("zone_key")
                }
            elif stype == "AS7265X":
                addr = conn.get("address", 0x49)  # Default AS7265X address
                cache_key = ("AS7265X", bus, addr)
                reader = _sensor_instance_cache.get(cache_key)
                if reader is None:
                    # Create SpectralSensorReader for AS7265X
                    spectral_config = {
                        sid: {
                            "name": cfg.get("name", "AS7265X Sensor"),
                            "type": "AS7265X",
                            "connection": {"bus": bus, "address": addr}
                        }
                    }
                    reader = SpectralSensorReader(spectral_config)
                    _sensor_instance_cache[cache_key] = reader
                spectral_results = reader.read_sensors()
                as7265x_data = spectral_results.get(sid, {})
                results[sid] = {
                    "type": stype,
                    "raw": as7265x_data.get("raw_data", {}),  # Just return raw driver data
                    "zone_key": cfg.get("zone_key")
                }
            else:
                # Fallback to basic read
                reading = read_light_sensor(cfg, sensor_id=sid)
                results[sid] = {
                    "type": stype or "UNKNOWN",
                    "reading": reading,
                    "zone_key": cfg.get("zone_key")
                }
        return jsonify({"success": True, "debug": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/scheduler/status', methods=['GET'])
def api_scheduler_status():
    """Get background scheduler status and performance metrics."""
    global _sensor_scheduler
    scheduler = _sensor_scheduler
    if not scheduler:
        return jsonify({
            "running": False,
            "error": "Scheduler not initialized"
        })
    
    return jsonify(scheduler.get_stats())

@app.route('/api/spectrum-fusion', methods=['POST'])
def api_spectrum_fusion():
    """
    Fuse spectral data from multiple sensors to estimate spectrum at target location.
    
    Expected JSON payload:
    {
        "sensors": [
            {
                "sensor_id": "tcs1",
                "position": [0, 0],  // x, y coordinates
                "reading": {...}     // raw sensor data
            },
            {
                "sensor_id": "tsl1", 
                "position": [2, 0],
                "reading": {...}
            }
        ],
        "target_position": [1, 0]  // x, y where to estimate spectrum
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400
        
        sensors_info = data.get('sensors', [])
        target_pos = data.get('target_position')
        
        if len(sensors_info) < 2:
            return jsonify({"success": False, "error": "At least 2 sensors required for fusion"}), 400
        
        if not target_pos or len(target_pos) != 2:
            return jsonify({"success": False, "error": "target_position must be [x, y] coordinates"}), 400
        
        # Extract sensor data and positions
        sensors_data = []
        positions = []
        
        for sensor_info in sensors_info:
            sensor_id = sensor_info.get('sensor_id')
            position = sensor_info.get('position')
            reading = sensor_info.get('reading')
            
            if not all([sensor_id, position, reading]):
                return jsonify({"success": False, "error": f"Missing data for sensor {sensor_id}"}), 400
            
            if len(position) != 2:
                return jsonify({"success": False, "error": f"Position for {sensor_id} must be [x, y]"}), 400
            
            sensors_data.append(reading)
            positions.append(tuple(position))
        
        # Perform spectral fusion
        fused_result = SpectralDataFusion.fuse_sensor_spectra(
            sensors_data, positions, tuple(target_pos)
        )
        
        histogram_data = SpectralDataFusion.create_histogram_data(fused_result)
        
        return jsonify({
            "success": True,
            "fused_spectrum": fused_result,
            "histogram": histogram_data,
            "fusion_summary": {
                "target_position": target_pos,
                "source_sensors": [s.get('sensor_type', 'UNKNOWN') for s in sensors_data],
                "spatial_weights": fused_result['spatial_weights'],
                "quality_score": histogram_data.get('interpolation_quality', 0),
                "method": "inverse_distance_weighted_spectral_mapping"
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/spectrum-fusion/live', methods=['POST'])
def api_live_spectrum_fusion():
    """
    Perform spectrum fusion using live sensor readings.
    
    Expected JSON payload:
    {
        "sensor_ids": ["sensor1", "sensor2"],
        "positions": [[0, 0], [2, 0]], 
        "target_position": [1, 0]
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400
        
        sensor_ids = data.get('sensor_ids', [])
        positions = data.get('positions', [])
        target_pos = data.get('target_position')
        
        if len(sensor_ids) != len(positions):
            return jsonify({"success": False, "error": "Number of sensor_ids must match positions"}), 400
        
        if len(sensor_ids) < 2:
            return jsonify({"success": False, "error": "At least 2 sensors required"}), 400
        
        # Load sensor configurations
        sensors_cfg = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}}).get("sensors", {})
        
        # Read live data from each sensor
        sensors_data = []
        actual_positions = []
        
        for i, sensor_id in enumerate(sensor_ids):
            if sensor_id not in sensors_cfg:
                return jsonify({"success": False, "error": f"Sensor {sensor_id} not configured"}), 400
            
            # Read current sensor data
            sensor_cfg = sensors_cfg[sensor_id]
            reading = read_light_sensor(sensor_cfg, sensor_id)
            
            if reading.get('error'):
                return jsonify({"success": False, "error": f"Error reading {sensor_id}: {reading['error']}"}), 500
            
            sensors_data.append(reading)
            actual_positions.append(tuple(positions[i]))
        
        # Perform fusion
        fused_result = SpectralDataFusion.fuse_sensor_spectra(
            sensors_data, actual_positions, tuple(target_pos)
        )
        
        histogram_data = SpectralDataFusion.create_histogram_data(fused_result)
        
        return jsonify({
            "success": True,
            "fused_spectrum": fused_result,
            "histogram": histogram_data,
            "live_readings": {
                sensor_id: reading for sensor_id, reading in zip(sensor_ids, sensors_data)
            },
            "fusion_summary": {
                "target_position": target_pos,
                "sensor_positions": positions,
                "source_sensors": sensor_ids,
                "spatial_weights": fused_result['spatial_weights'],
                "quality_score": histogram_data.get('interpolation_quality', 0),
                "timestamp": time.time()
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def read_light_sensor(cfg, sensor_id: str = None):
    """Read a light sensor based on its configuration.

    cfg schema example:
    {
        "name": "BH1750 #1",
        "type": "BH1750",
        "connection": {"bus": 1, "address": 35},
        "zone_key": "row-col"  # optional zone mapping
    }
    """
    try:
        stype = (cfg.get("type") or "").upper()
        if stype == "BH1750":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", BH1750.DEFAULT_ADDR)
            sensor = BH1750(bus=bus, addr=addr)
            return {"lux": sensor.read_lux()}
        elif stype == "TSL2561":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", 0x39)
            sensor = TSL2561(bus=bus, addr=addr)
            return {"lux": sensor.read_lux()}
        elif stype == "VEML7700":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", 0x10)
            sensor = VEML7700(bus=bus, addr=addr)
            return {"lux": sensor.read_lux()}
        elif stype == "TSL2591":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", 0x29)
            sensor = TSL2591(bus=bus, addr=addr)
            return {"lux": sensor.read_lux()}
        elif stype == "TCS34725":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", TCS34725Color.DEFAULT_ADDR)
            mux_addr = cfg.get("connection", {}).get("mux_address")
            mux_ch = cfg.get("connection", {}).get("mux_channel")
            # Reuse TCS34725 instance to avoid repeated init and I2C setup
            cache_key = ("TCS34725", bus, addr, mux_addr, mux_ch)
            sensor = _sensor_instance_cache.get(cache_key)
            if sensor is None:
                sensor = TCS34725Color(bus=bus, addr=addr, mux_address=mux_addr, mux_channel=mux_ch)
                _sensor_instance_cache[cache_key] = sensor
            color_data = sensor.read_color()
            if color_data:
                # Clamp negative lux but return raw data
                if color_data.get("lux") is not None and color_data["lux"] < 0:
                    print(f"[API][WARN] TCS34725 returned negative lux {color_data['lux']}; clamping to 0.0")
                    color_data["lux"] = 0.0
                return {
                    "raw_color": color_data,  # Return all raw color data
                    "sensor_type": "TCS34725"
                }
            return {"raw_color": {}, "sensor_type": "TCS34725"}
        elif stype == "AS7265X":
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", 0x49)
            # Reuse AS7265X SpectralSensorReader to avoid repeated init
            cache_key = ("AS7265X", bus, addr)
            reader = _sensor_instance_cache.get(cache_key)
            if reader is None:
                spectral_config = {
                    sensor_id or "as7265x": {
                        "name": cfg.get("name", "AS7265X Sensor"),
                        "type": "AS7265X",
                        "connection": {"bus": bus, "address": addr}
                    }
                }
                reader = SpectralSensorReader(spectral_config)
                _sensor_instance_cache[cache_key] = reader
            results = reader.read_sensors()
            if results:
                as7265x_data = next(iter(results.values()), {})
                raw_spectrum = as7265x_data.get("raw_data", {})
                return {
                    "raw_spectrum": raw_spectrum,  # Just return raw 18-channel data
                    "sensor_type": "AS7265X"
                }
            return {"raw_spectrum": {}, "sensor_type": "AS7265X"}
        elif stype == "AS7262":
            # AS7262 6-channel visible spectral sensor
            from sensors.as7262 import AS7262Sensor
            bus = cfg.get("connection", {}).get("bus", 1)
            addr = cfg.get("connection", {}).get("address", 0x49)
            mux_addr = cfg.get("connection", {}).get("mux_address")
            mux_ch = cfg.get("connection", {}).get("mux_channel")
            # Cache key includes mux params for uniqueness
            cache_key = ("AS7262", bus, addr, mux_addr, mux_ch)
            sensor = _sensor_instance_cache.get(cache_key)
            if sensor is None:
                sensor = AS7262Sensor(
                    address=addr,
                    mux_address=mux_addr,
                    mux_channel=mux_ch,
                    mock_mode=False
                )
                _sensor_instance_cache[cache_key] = sensor
            spectrum = sensor.read_spectrum()
            if spectrum:
                return {
                    "raw_spectrum_data": spectrum,  # Contains wavelengths, intensities, raw_values
                    "sensor_type": "AS7262"
                }
            return {"raw_spectrum_data": {}, "sensor_type": "AS7262"}
        return {"lux": None}
    except Exception as e:
        return {"lux": None, "error": str(e)}

@app.route('/whoami')
def whoami():
    """Diagnostic endpoint to identify the running app instance and template source."""
    try:
        searchpath = []
        try:
            # jinja_loader may or may not have searchpath depending on loader type
            searchpath = getattr(app.jinja_loader, 'searchpath', []) or []
        except Exception:
            searchpath = []
        idx_path = None
        idx_mtime = None
        for base in searchpath:
            candidate = os.path.join(base, 'index.html')
            if os.path.exists(candidate):
                idx_path = candidate
                try:
                    idx_mtime = os.path.getmtime(candidate)
                except Exception:
                    idx_mtime = None
                break
        return jsonify({
            "app_file": __file__,
            "cwd": os.getcwd(),
            "template_searchpath": searchpath,
            "index_template_path": idx_path,
            "index_template_mtime": idx_mtime
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/<device>/<action>')
def api_control(device, action):
    """API for device control."""
    try:
        if device == "grow_light":
            if action == "on":
                grow_light.on()
            elif action == "off":
                grow_light.off()
        elif device == "heater":
            if action == "on":
                heater.on()
            elif action == "off":
                heater.off()
        elif device == "fan":
            speed = int(request.args.get('speed', 0))
            fan.set_speed(speed)
        
        return jsonify({"success": True, "device": device, "action": action})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/todos', methods=['GET', 'POST'])
def api_todos():
    """API for todo management."""
    if request.method == 'GET':
        todos = load_json_file(TODOS_FILE, {"todos": []})
        return jsonify(todos)
    
    elif request.method == 'POST':
        data = request.get_json()
        if save_json_file(TODOS_FILE, data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save todos"}), 500

@app.route('/api/calibration', methods=['GET'])
def api_get_calibration():
    """Get current calibration data."""
    calibration = load_json_file(CALIBRATION_FILE, {})
    return jsonify(calibration)

@app.route('/api/calibration/start', methods=['POST'])
def api_start_calibration():
    """Start light calibration process."""
    try:
        data = request.get_json() or {}
        comprehensive = data.get('comprehensive', False)
        
        calibrator = get_light_calibrator()
        
        if comprehensive:
            # Run comprehensive calibration with spectrum analysis
            calibration_data = calibrator.run_comprehensive_calibration()
        else:
            # Run basic calibration
            calibration_data = calibrator.run_full_calibration()
            
        return jsonify({"success": True, "data": calibration_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/baseline', methods=['POST'])
def api_measure_baseline():
    """Measure baseline light levels."""
    try:
        calibrator = get_light_calibrator()
        baseline = calibrator.measure_baseline()
        return jsonify({"success": True, "baseline": baseline})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/light/<light_id>', methods=['POST'])
def api_calibrate_light(light_id):
    """Calibrate a specific light."""
    try:
        calibrator = get_light_calibrator()
        
        # Get baseline from request or measure it
        data = request.get_json() or {}
        baseline = data.get('baseline')
        if not baseline:
            baseline = calibrator.measure_baseline()
        
        light_effect = calibrator.calibrate_light(light_id, baseline)
        return jsonify({"success": True, "light_effect": light_effect})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/optimize', methods=['POST'])
def api_optimize_lights():
    """Optimize lights for current zone requirements."""
    try:
        data = request.get_json() or {}
        method = data.get('method', 'multi_objective')
        
        calibrator = get_light_calibrator()
        zones = load_json_file(ZONES_FILE, {"zones": {}})
        
        optimal_lights = calibrator.optimize_for_zones(zones.get("zones", {}), method=method)
        
        # Apply the optimization if requested
        if data.get('apply', False):
            for light_id, should_be_on in optimal_lights.items():
                if should_be_on:
                    calibrator.light_controller.turn_on_light(light_id)
                else:
                    calibrator.light_controller.turn_off_light(light_id)
        
        return jsonify({"success": True, "optimal_lights": optimal_lights})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/quality', methods=['GET'])
def api_calibration_quality():
    """Analyze calibration quality."""
    try:
        calibrator = get_light_calibrator()
        if not calibrator.calibration_data:
            return jsonify({"success": False, "error": "No calibration data available"})
        
        from control.light_optimizer import LightOptimizer
        optimizer = LightOptimizer(calibrator.calibration_data)
        quality = optimizer.analyze_calibration_quality()
        
        return jsonify({"success": True, "quality": quality})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/lights/control/<light_id>/<action>')
def api_control_light(light_id, action):
    """Control individual lights."""
    try:
        calibrator = get_light_calibrator()
        
        if action == "on":
            success = calibrator.light_controller.turn_on_light(light_id)
        elif action == "off":
            success = calibrator.light_controller.turn_off_light(light_id)
        else:
            return jsonify({"success": False, "error": "Invalid action"}), 400
        
        return jsonify({"success": success, "light_id": light_id, "action": action})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/lights/control/all/<action>')
def api_control_all_lights(action):
    """Control all lights at once."""
    try:
        calibrator = get_light_calibrator()
        
        if action == "off":
            calibrator.light_controller.turn_off_all_lights()
            return jsonify({"success": True, "action": "all_lights_off"})
        else:
            return jsonify({"success": False, "error": "Invalid action"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/spectrum-report', methods=['GET'])
def api_spectrum_report():
    """Get comprehensive spectrum analysis report."""
    try:
        calibrator = get_light_calibrator()
        report = calibrator.generate_spectrum_report()
        return jsonify({"success": True, "report": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/update-spectrum', methods=['POST'])
def api_update_spectrum():
    """Update lights.json with measured spectrum data."""
    try:
        calibrator = get_light_calibrator()
        updated_lights = calibrator.update_lights_with_measured_spectrum()
        return jsonify({"success": True, "updated_lights": updated_lights})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calibration/adaptive', methods=['POST'])
def api_run_adaptive_calibration():
    """Run adaptive calibration for mixed capability zones."""
    try:
        calibrator = get_light_calibrator()
        data = request.get_json() or {}
        zone_requests = data.get('zone_requests', {})
        
        if not zone_requests:
            # If no specific requests, optimize based on current zones.json
            zones = load_json_file(ZONES_FILE, {"zones": {}})
            zones_data = zones.get("zones", {})
            
            if zones_data:
                # Extract crop types and growth stages
                crop_types = {}
                growth_stages = {}
                
                for zone_key, zone_info in zones_data.items():
                    if 'crop_type' in zone_info:
                        crop_types[zone_key] = zone_info['crop_type']
                    if 'growth_stage' in zone_info:
                        growth_stages[zone_key] = zone_info['growth_stage']
                
                if crop_types:
                    results = calibrator.optimize_for_mixed_zone_types(crop_types, growth_stages)
                else:
                    # Fallback to basic adaptive calibration
                    results = calibrator.optimize_zones_with_adaptive_strategy({})
            else:
                results = calibrator.optimize_zones_with_adaptive_strategy({})
        else:
            # Use provided zone requests
            results = calibrator.optimize_zones_with_adaptive_strategy(zone_requests)
        
        # Save results to calibration file
        save_json_file(CALIBRATION_FILE, results)
        
        return jsonify({
            'success': True,
            'results': results,
            'timestamp': results.get('timestamp')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calibration/capabilities', methods=['GET'])
def api_get_zone_capabilities():
    """Get zone capability report."""
    try:
        calibrator = get_light_calibrator()
        report = calibrator.get_zone_capability_report()
        
        return jsonify({
            'success': True,
            'capabilities': report
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calibration/mixed-optimization', methods=['POST'])
def api_mixed_optimization():
    """Run optimization for zones with mixed crop types."""
    try:
        data = request.get_json() or {}
        crop_types = data.get('crop_types', {})
        growth_stages = data.get('growth_stages', {})
        
        if not crop_types:
            # Try to get from zones.json
            zones = load_json_file(ZONES_FILE, {"zones": {}})
            zones_data = zones.get("zones", {})
            
            for zone_key, zone_info in zones_data.items():
                if 'crop_type' in zone_info:
                    crop_types[zone_key] = zone_info['crop_type']
                if 'growth_stage' in zone_info:
                    growth_stages[zone_key] = zone_info['growth_stage']
        
        if not crop_types:
            return jsonify({
                'success': False,
                'error': 'No crop types specified and none found in zones configuration'
            }), 400
        
        calibrator = get_light_calibrator()
        results = calibrator.optimize_for_mixed_zone_types(crop_types, growth_stages)
        
        # Apply optimization if requested
        if data.get('apply', False):
            zone_results = results.get('zone_results', {})
            for zone_key, zone_result in zone_results.items():
                if zone_result.get('success', False):
                    optimal_lights = zone_result.get('optimal_lights', {})
                    for light_id, should_be_on in optimal_lights.items():
                        if should_be_on:
                            calibrator.light_controller.turn_on_light(light_id)
                        else:
                            calibrator.light_controller.turn_off_light(light_id)
        
        # Save results
        save_json_file(CALIBRATION_FILE, results)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calibration/ambient-aware', methods=['POST'])
def api_ambient_aware_calibration():
    """Run ambient light aware calibration."""
    try:
        calibrator = get_light_calibrator()
        results = calibrator.run_ambient_aware_calibration()
        
        # Save results
        save_json_file(CALIBRATION_FILE, results)
        
        return jsonify({
            'success': True,
            'results': results,
            'deferred': results.get('calibration_type') == 'ambient_aware_deferred'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calibration/ambient-status', methods=['GET'])
def api_ambient_status():
    """Get current ambient light status and calibration feasibility."""
    try:
        calibrator = get_light_calibrator()
        
        # Initialize ambient handler if needed
        if not calibrator.ambient_handler:
            from control.ambient_light_handler import AmbientAwareCalibrator
            calibrator.ambient_handler = AmbientAwareCalibrator(calibrator.sensors_config)
        
        # Get current sensor readings
        current_readings = {}
        for sensor_id, sensor_config in calibrator.sensors_config.items():
            try:
                reading = calibrator.sensor_reader.read_sensor(sensor_config)
                current_readings[sensor_id] = reading.get('lux') if reading else None
            except Exception:
                current_readings[sensor_id] = None
        
        # Analyze ambient conditions
        conditions = calibrator.ambient_handler.ambient_analyzer.analyze_current_conditions(current_readings)
        should_calibrate, reason = calibrator.ambient_handler.should_calibrate_now(current_readings)
        
        return jsonify({
            'success': True,
            'ambient_status': {
                'level': conditions.level.value,
                'average_lux': conditions.average_lux,
                'variation_coefficient': conditions.variation_coefficient,
                'time_of_day': conditions.time_of_day,
                'weather_condition': conditions.weather_condition,
                'calibration_feasibility': conditions.calibration_feasibility,
                'recommended_strategy': conditions.recommended_strategy
            },
            'calibration_recommendation': {
                'should_calibrate': should_calibrate,
                'reason': reason
            },
            'current_readings': current_readings
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/lights/intelligent-control', methods=['POST'])
def api_intelligent_light_control():
    """Make intelligent light control decisions."""
    try:
        calibrator = get_light_calibrator()
        data = request.get_json() or {}
        
        # Make intelligent decisions
        decisions_result = calibrator.make_intelligent_light_decisions()
        
        if not decisions_result.get('decisions'):
            return jsonify({
                'success': False,
                'error': 'Failed to make light decisions',
                'details': decisions_result
            }), 500
        
        # Apply decisions if requested
        if data.get('apply', False):
            dry_run = data.get('dry_run', False)
            application_result = calibrator.apply_intelligent_decisions(decisions_result, dry_run)
            
            return jsonify({
                'success': True,
                'decisions': decisions_result,
                'application': application_result,
                'applied': not dry_run
            })
        else:
            return jsonify({
                'success': True,
                'decisions': decisions_result,
                'applied': False
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/lights/automated-cycle', methods=['POST'])
def api_run_automated_cycle():
    """Run a complete automated light control cycle."""
    try:
        calibrator = get_light_calibrator()
        cycle_result = calibrator.run_automated_light_control_cycle()
        
        return jsonify({
            'success': cycle_result['success'],
            'cycle_result': cycle_result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/lights/decision-explanation/<light_id>', methods=['GET'])
def api_get_decision_explanation(light_id):
    """Get detailed explanation for a light control decision."""
    try:
        calibrator = get_light_calibrator()
        
        # Make current decisions to get explanation
        decisions_result = calibrator.make_intelligent_light_decisions()
        
        if light_id not in decisions_result.get('decisions', {}):
            return jsonify({
                'success': False,
                'error': f'No decision found for light {light_id}'
            }), 404
        
        decision_data = decisions_result['decisions'][light_id]
        
        return jsonify({
            'success': True,
            'light_id': light_id,
            'explanation': decision_data['explanation'],
            'decision_summary': {
                'should_be_on': decision_data['should_be_on'],
                'intensity_percent': decision_data['intensity_percent'],
                'confidence': decision_data['confidence'],
                'primary_reason': decision_data['primary_reason'],
                'power_consumption': decision_data['power_consumption']
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/config/light-control', methods=['GET'])
def get_light_control_config():
    """Get current light control configuration."""
    try:
        config_file = Path('data/light_control_config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            # Return default config
            config = {
                'energy_cost_per_kwh': 0.12,
                'time_of_use_pricing': {
                    'off_peak': {'multiplier': 1.0, 'hours': [23, 0, 1, 2, 3, 4, 5]},
                    'standard': {'multiplier': 1.5, 'hours': [6, 7, 8, 9, 10, 11, 12, 13, 14, 15]},
                    'peak': {'multiplier': 2.0, 'hours': [16, 17, 18, 19, 20, 21, 22]}
                },
                'growth_schedules': {}
            }
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/config/light-control', methods=['POST'])
def update_light_control_config():
    """Update light control configuration."""
    try:
        data = request.get_json()
        config_file = Path('data/light_control_config.json')
        
        # Ensure data directory exists
        config_file.parent.mkdir(exist_ok=True)
        
        # Save updated config
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dli/status', methods=['GET'])
def get_dli_status():
    """Get current DLI status for all zones."""
    try:
        # Initialize decision engine to get DLI status
        calibration_data = load_json_file(CALIBRATION_FILE, {})
        zones_config = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
        lights_config = load_json_file(LIGHTS_FILE, {"lights": {}}).get("lights", {})
        sensors_config = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}}).get("sensors", {})
        
        from control.light_decision_engine import LightDecisionEngine
        decision_engine = LightDecisionEngine(
            calibration_data, zones_config, lights_config, sensors_config
        )
        
        # Get DLI status for all zones
        dli_status = decision_engine.get_dli_status()
        
        return jsonify({
            'success': True,
            'dli_status': dli_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dli/status/<zone_key>', methods=['GET'])
def get_zone_dli_status(zone_key):
    """Get DLI status for a specific zone."""
    try:
        # Initialize decision engine to get DLI status
        calibration_data = load_json_file(CALIBRATION_FILE, {})
        zones_config = load_json_file(ZONES_FILE, {"grid_size": {"rows": 4, "cols": 6}, "zones": {}})
        lights_config = load_json_file(LIGHTS_FILE, {"lights": {}}).get("lights", {})
        sensors_config = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}}).get("sensors", {})
        
        from control.light_decision_engine import LightDecisionEngine
        decision_engine = LightDecisionEngine(
            calibration_data, zones_config, lights_config, sensors_config
        )
        
        # Get DLI status for specific zone
        dli_status = decision_engine.get_dli_status(zone_key)
        
        return jsonify({
            'success': True,
            'zone_key': zone_key,
            'dli_status': dli_status.get(zone_key, {}),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/config/time-of-use', methods=['POST'])
def update_time_of_use_pricing():
    """Update time-of-use pricing configuration."""
    try:
        data = request.get_json()
        
        # Validate the time-of-use structure
        required_fields = ['off_peak', 'standard', 'peak']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
            
            if 'multiplier' not in data[field] or 'hours' not in data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} must contain multiplier and hours'
                }), 400
        
        # Load current config
        config_file = Path('data/light_control_config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Update time-of-use pricing
        config['time_of_use_pricing'] = data
        
        # Save updated config
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Time-of-use pricing updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/config/growth-schedules', methods=['POST'])
# No internal scheduler lifecycle; managed externally by separate service.
@app.route('/api/color-temp-schedule/<zone_id>')
def api_get_color_temp_schedule(zone_id):
    """Get current color temperature schedule for a zone."""
    zones = load_json_file(ZONES_FILE, {"zones": {}})
    zone = zones.get("zones", {}).get(zone_id)
    if not zone:
        return jsonify({"error": "Zone not found"}), 404
    
    schedule = zone.get("color_temp_schedule", {})
    return jsonify(schedule)

@app.route('/api/color-temp-schedule/<zone_id>', methods=['POST'])
def api_update_color_temp_schedule(zone_id):
    """Update color temperature schedule for a zone."""
    try:
        zones = load_json_file(ZONES_FILE, {"zones": {}})
        if zone_id not in zones.get("zones", {}):
            return jsonify({"error": "Zone not found"}), 404
        
        schedule_data = request.get_json()
        zones["zones"][zone_id]["color_temp_schedule"] = schedule_data
        
        if save_json_file(ZONES_FILE, zones):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to save schedule"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/current-color-temp/<zone_id>')
def api_current_color_temp(zone_id):
    """Get the current color temperature for a zone based on time of day."""
    try:
        from datetime import datetime
        
        zones = load_json_file(ZONES_FILE, {"zones": {}})
        zone = zones.get("zones", {}).get(zone_id)
        if not zone:
            return jsonify({"error": "Zone not found"}), 404
        
        schedule = zone.get("color_temp_schedule", {})
        if not schedule.get("enabled", False):
            # Return static color temperature
            return jsonify({
                "color_temp_k": zone.get("light_spectrum", {}).get("color_temperature", 4000),
                "source": "static"
            })
        
        current_time = datetime.now().time()
        schedule_times = schedule.get("schedule", {})
        
        # Find the appropriate color temperature based on current time
        morning_time = datetime.strptime(schedule_times.get("morning", {}).get("time", "06:00"), "%H:%M").time()
        midday_time = datetime.strptime(schedule_times.get("midday", {}).get("time", "12:00"), "%H:%M").time()
        afternoon_time = datetime.strptime(schedule_times.get("afternoon", {}).get("time", "18:00"), "%H:%M").time()
        
        if current_time < morning_time:
            # Before morning - use afternoon setting
            color_temp = schedule_times.get("afternoon", {}).get("color_temp_k", 3000)
            period = "pre-morning"
        elif current_time < midday_time:
            # Morning period
            color_temp = schedule_times.get("morning", {}).get("color_temp_k", 5000)
            period = "morning"
        elif current_time < afternoon_time:
            # Midday period
            color_temp = schedule_times.get("midday", {}).get("color_temp_k", 4000)
            period = "midday"
        else:
            # Afternoon/evening period
            color_temp = schedule_times.get("afternoon", {}).get("color_temp_k", 3000)
            period = "afternoon"
        
        return jsonify({
            "color_temp_k": color_temp,
            "period": period,
            "source": "scheduled"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/frontend-config')
def api_frontend_config():
    """API endpoint for frontend configuration values."""
    return jsonify({
        "update_interval_ms": _app_config["frontend_update_interval"] * 1000,  # Convert to milliseconds
        "sensor_cache_ttl": _app_config["sensor_cache_ttl"],
        "user_settings": load_user_settings()
    })

@app.route('/configuration')
def configuration():
    """Configuration page for system settings."""
    user_settings = load_user_settings()
    return render_template('configuration.html', config=_app_config, user_settings=user_settings)

@app.route('/settings')
def settings_page():
    """User settings page (units and light display)."""
    user_settings = load_user_settings()
    return render_template('settings.html', settings=user_settings)

@app.route('/api/user-settings', methods=['GET', 'POST'])
def api_user_settings():
    """API to get/update user unit/display settings."""
    if request.method == 'GET':
        return jsonify(load_user_settings())
    try:
        data = request.get_json() or {}
        updated = save_user_settings(data)
        return jsonify({"success": True, "settings": updated})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/configuration', methods=['GET', 'POST'])
def api_configuration():
    """API for system configuration."""
    global _app_config, _light_sensor_cache
    
    if request.method == 'GET':
        return jsonify({
            "config": _app_config,
            "description": {
                "sensor_cache_ttl": "Backend sensor cache TTL (seconds) - how long sensor readings are cached",
                "frontend_update_interval": "Frontend update interval (seconds) - how often the web interface refreshes"
            }
        })
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validate and update sensor cache TTL
            if 'sensor_cache_ttl' in data:
                ttl = int(data['sensor_cache_ttl'])
                if 1 <= ttl <= 60:  # Between 1-60 seconds
                    _app_config['sensor_cache_ttl'] = ttl
                    # Clear cache to apply new TTL immediately
                    _light_sensor_cache["readings"] = {}
                else:
                    return jsonify({"success": False, "error": "sensor_cache_ttl must be between 1-60 seconds"}), 400
            
            # Validate and update frontend update interval
            if 'frontend_update_interval' in data:
                interval = int(data['frontend_update_interval'])
                if 1 <= interval <= 300:  # Between 1-300 seconds (5 minutes)
                    _app_config['frontend_update_interval'] = interval
                else:
                    return jsonify({"success": False, "error": "frontend_update_interval must be between 1-300 seconds"}), 400
            
            return jsonify({"success": True, "config": _app_config})
            
        except (ValueError, TypeError) as e:
            return jsonify({"success": False, "error": f"Invalid configuration values: {e}"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Configuration update failed: {e}"}), 500

## Removed: init_sensor_scheduler (Flask no longer starts a scheduler)

# No internal scheduler helpers


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    exit(0)

if __name__ == "__main__":
    import signal
    
    # Handle shutdown signals
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start Flask app when running this file directly
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"Starting Greenhouse Control Web Server on http://{host}:{port} (debug={debug})")
    
    try:
        # threaded=True allows concurrent requests (handy for the UI)
        app.run(host=host, port=port, debug=debug, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down web server...")
    except Exception as e:
        print(f"Error starting web server: {e}")
        exit(1)