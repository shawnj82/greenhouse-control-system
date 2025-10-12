"""Flask web server for greenhouse control interface."""
import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Import our sensor and control modules
from sensors.dht22 import DHT22
from sensors.bh1750 import BH1750
from sensors.tsl2561 import TSL2561
from sensors.veml7700 import VEML7700
from sensors.tsl2591 import TSL2591
from sensors.soil_moisture import SoilMoisture
from sensors.spectral_sensors import TCS34725Color
from control.relay import Relay
from control.fan_controller import FanController
from control.light_calibration import LightCalibrator

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

# Initialize hardware (with fallbacks)
dht = DHT22(pin=4)
light_sensor = BH1750()
soil_sensor = SoilMoisture()
grow_light = Relay(pin=17, active_high=True)
heater = Relay(pin=27, active_high=True)
fan = FanController(pin=22)

# Initialize light calibrator
light_calibrator = None

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
    dht_data = dht.read()
    return {
        "timestamp": datetime.now().isoformat(),
        "temperature_c": dht_data.get("temperature_c") if isinstance(dht_data, dict) else None,
        "humidity": dht_data.get("humidity") if isinstance(dht_data, dict) else None,
        "light_lux": light_sensor.read_lux(),
        "soil_moisture": soil_sensor.moisture_percent(),
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
    
    return render_template('index.html', 
                         status=status, 
                         zones=zones, 
                         recent_errors=errors.get("errors", [])[-5:],
                         todos=todos.get("todos", []))

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
    return render_template('lights.html', lights=lights, zones=zones)

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
    """API for lights configuration."""
    if request.method == 'GET':
        lights = load_json_file(LIGHTS_FILE, {"lights": {}})
        return jsonify(lights)
    
    elif request.method == 'POST':
        data = request.get_json()
        if save_json_file(LIGHTS_FILE, data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save lights"}), 500

@app.route('/api/light-sensors', methods=['GET', 'POST'])
def api_light_sensors():
    """API for light sensors configuration and readings."""
    if request.method == 'GET':
        sensors = load_json_file(LIGHT_SENSORS_FILE, {"sensors": {}})
        # Attach latest readings with caching
        now = datetime.now().timestamp()
        readings = {}
        for sid, cfg in sensors.get("sensors", {}).items():
            cached = _light_sensor_cache["readings"].get(sid)
            if cached and (now - cached.get("ts", 0) < _light_sensor_cache["ttl_sec"]):
                readings[sid] = {"lux": cached.get("lux")}
            else:
                r = read_light_sensor(cfg)
                readings[sid] = r
                _light_sensor_cache["readings"][sid] = {"lux": r.get("lux"), "ts": now}
        return jsonify({"config": sensors, "readings": readings})

    elif request.method == 'POST':
        data = request.get_json()
        if save_json_file(LIGHT_SENSORS_FILE, data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save light sensors"}), 500

def read_light_sensor(cfg):
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
            sensor = TCS34725Color(bus=bus, addr=addr)
            color_data = sensor.read_color()
            if color_data:
                return {"lux": color_data.get("lux"), "color_temp_k": color_data.get("color_temperature_k")}
            return {"lux": None}
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
def update_growth_schedules():
    """Update growth schedules configuration."""
    try:
        data = request.get_json()
        
        # Load current config
        config_file = Path('data/light_control_config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Update growth schedules
        config['growth_schedules'] = data
        
        # Save updated config
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Growth schedules updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)