"""Light calibration system for measuring sensor responses to individual lights.

This module provides functionality to:
1. Turn lights on/off individually during calibration
2. Measure sensor responses to determine light influence
3. Store calibration matrices for optimization algorithms
4. Calculate optimal light combinations for target illumination
"""
import json
import time
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

from control.enhanced_relay import LightController as EnhancedLightController
from control.light_optimizer import LightOptimizer
from control.adaptive_calibration import AdaptiveZoneCalibrator
from control.mixed_capability_optimizer import MixedCapabilityOptimizer, ZoneTarget, OptimizationResult
from control.ambient_light_handler import AmbientAwareCalibrator, AmbientLightLevel
from control.light_decision_engine import LightDecisionEngine, LightDecision, LightDecisionReason
from sensors.bh1750 import BH1750
from sensors.tsl2561 import TSL2561
from sensors.tsl2591 import TSL2591
from sensors.veml7700 import VEML7700
from sensors.spectral_sensors import SpectralSensorReader


# Legacy LightController removed (replaced by EnhancedLightController)


class SensorReader:
    """Reads from all available light sensors."""
    
    def __init__(self, sensors_config: Dict):
        self.sensors = {}
        
        # Initialize sensors based on config
        for sensor_id, config in sensors_config.items():
            sensor_type = config.get('type')
            connection = config.get('connection', {})
            
            try:
                if sensor_type == 'BH1750':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', BH1750.DEFAULT_ADDR)
                    self.sensors[sensor_id] = {
                        'instance': BH1750(bus=bus, addr=addr),
                        'config': config
                    }
                elif sensor_type == 'TSL2561':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', TSL2561.DEFAULT_ADDR)
                    self.sensors[sensor_id] = {
                        'instance': TSL2561(bus=bus, addr=addr),
                        'config': config
                    }
                elif sensor_type == 'TSL2591':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', TSL2591.DEFAULT_ADDR)
                    self.sensors[sensor_id] = {
                        'instance': TSL2591(bus=bus, addr=addr),
                        'config': config
                    }
                elif sensor_type == 'VEML7700':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', VEML7700.DEFAULT_ADDR)
                    self.sensors[sensor_id] = {
                        'instance': VEML7700(bus=bus, addr=addr),
                        'config': config
                    }
                elif sensor_type == 'TCS34725':
                    # Add TCS34725 as a basic sensor for lux reading
                    from sensors.spectral_sensors import TCS34725Color
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', 0x29)
                    class TCS34725LuxWrapper:
                        def __init__(self, bus, addr):
                            self._sensor = TCS34725Color(bus=bus, addr=addr)
                        def read_lux(self):
                            color = self._sensor.read_color()
                            if color and 'lux' in color:
                                return color['lux']
                            return None
                    self.sensors[sensor_id] = {
                        'instance': TCS34725LuxWrapper(bus=bus, addr=addr),
                        'config': config
                    }
            except Exception as e:
                print(f"Failed to initialize sensor {sensor_id}: {e}")
    
    def read_all_sensors(self) -> Dict[str, Optional[float]]:
        """Read lux values from all sensors."""
        readings = {}
        
        for sensor_id, sensor_data in self.sensors.items():
            try:
                sensor = sensor_data['instance']
                if hasattr(sensor, 'read_lux'):
                    readings[sensor_id] = sensor.read_lux()
                else:
                    readings[sensor_id] = None
            except Exception as e:
                print(f"Error reading sensor {sensor_id}: {e}")
                readings[sensor_id] = None
        
        return readings
    
    def get_sensor_zones(self) -> Dict[str, str]:
        """Get mapping of sensor IDs to their zone locations."""
        zone_mapping = {}
        for sensor_id, sensor_data in self.sensors.items():
            zone_key = sensor_data['config'].get('zone_key')
            if zone_key:
                zone_mapping[sensor_id] = zone_key
        return zone_mapping


class LightCalibrator:
    """Main calibration system for lights and sensors."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        
        # Load configurations
        self.lights_config = self._load_json('lights.json')['lights']
        self.sensors_config = self._load_json('light_sensors.json')['sensors']
        
        # Initialize controllers with enhanced relay support
        self.light_controller = EnhancedLightController(self.lights_config, str(self.data_dir))
        self.sensor_reader = SensorReader(self.sensors_config)
        self.spectral_reader = SpectralSensorReader(self.sensors_config)
        
        # Initialize adaptive components
        self.adaptive_calibrator = None
        self.mixed_optimizer = None
        self.ambient_handler = None
        self.decision_engine = None
        
        # Calibration data
        self.calibration_data = self._load_calibration_data()
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON configuration file."""
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_json(self, data: Dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_calibration_data(self) -> Dict:
        """Load existing calibration data."""
        return self._load_json('light_calibration.json')
    
    def _save_calibration_data(self):
        """Save calibration data to file."""
        self._save_json(self.calibration_data, 'light_calibration.json')
    
    def measure_baseline_comprehensive(self, num_readings: int = 5, delay: float = 2.0, lux_stddev_percent: float = 5.0) -> Dict:
        """
        Measure comprehensive baseline including spectrum data.
        Uses a stability check on lux readings: if the standard deviation exceeds lux_stddev_percent of the mean,
        up to 3 rounds of readings are taken. If still unstable, raises an error.
        Tuning parameter: lux_stddev_percent (default 5.0). Adjust as needed for your environment.
        Only the lux readings are used for steadiness check. See documentation for tuning guidance.
        """
        import statistics
        print("Measuring comprehensive baseline with all lights off...")
        self.light_controller.turn_off_all_lights()
        time.sleep(5)  # Wait for stabilization
        max_attempts = 3
        for attempt in range(max_attempts):
            baseline_readings = []
            for i in range(num_readings):
                basic_readings = self.sensor_reader.read_all_sensors()
                spectral_readings = self.spectral_reader.read_comprehensive_data()
                combined_reading = {
                    'basic': basic_readings,
                    'spectral': spectral_readings,
                    'timestamp': time.time()
                }
                baseline_readings.append(combined_reading)
                if i < num_readings - 1:
                    time.sleep(delay)
            # Check lux stability
            lux_values = []
            for reading in baseline_readings:
                for v in reading['basic'].values():
                    if v is not None:
                        lux_values.append(v)
            print(f"[DEBUG] Lux values for stability check: {lux_values}")
            stdev_percent = None
            if len(lux_values) == 0:
                print("No valid lux readings collected. Retrying...")
            elif len(lux_values) == 1:
                # Only one value, treat as perfectly stable
                mean_lux = lux_values[0]
                stddev_lux = 0.0
                percent = 0.0
                stdev_percent = percent
                print(f"Lux stability check: mean={mean_lux:.2f}, stddev={stddev_lux:.2f}, percent={percent:.2f}% (threshold {lux_stddev_percent}%) [single value, treated as stable]")
                baseline = self._process_comprehensive_readings(baseline_readings)
                baseline['lux_stdev_percent'] = stdev_percent
                print(f"Comprehensive baseline measured (stable), stdev_percent={stdev_percent:.2f}%")
                return baseline
            else:
                mean_lux = sum(lux_values) / len(lux_values)
                stddev_lux = statistics.stdev(lux_values)
                if mean_lux > 0:
                    percent = 100.0 * stddev_lux / mean_lux
                    stdev_percent = percent
                    print(f"Lux stability check: mean={mean_lux:.2f}, stddev={stddev_lux:.2f}, percent={percent:.2f}% (threshold {lux_stddev_percent}%)")
                    if percent <= lux_stddev_percent:
                        baseline = self._process_comprehensive_readings(baseline_readings)
                        baseline['lux_stdev_percent'] = stdev_percent
                        print(f"Comprehensive baseline measured (stable), stdev_percent={stdev_percent:.2f}%")
                        return baseline
                    else:
                        print(f"Lux readings not steady (attempt {attempt+1}/{max_attempts}), retrying...")
                else:
                    print("Mean lux is zero, cannot check stability. Retrying...")
        raise RuntimeError(f"Lux readings did not stabilize after {max_attempts} attempts. Calibration failed.")
    
    def _process_comprehensive_readings(self, readings_list: List[Dict]) -> Dict:
        """Process and average comprehensive sensor readings."""
        if not readings_list:
            return {}
        
        # Separate basic and spectral data
        basic_data = {}
        spectral_data = {}
        
        # Average basic sensor readings
        for reading in readings_list:
            basic = reading.get('basic', {})
            for sensor_id, value in basic.items():
                if value is not None:
                    if sensor_id not in basic_data:
                        basic_data[sensor_id] = []
                    basic_data[sensor_id].append(value)
        
        # Calculate basic averages
        basic_averages = {}
        for sensor_id, values in basic_data.items():
            if values:
                basic_averages[sensor_id] = sum(values) / len(values)
        
        # Process spectral data (use latest reading since it's more complex)
        if readings_list:
            spectral_data = readings_list[-1].get('spectral', {})
        
        return {
            'basic_sensors': basic_averages,
            'spectral_sensors': spectral_data,
            'measurement_count': len(readings_list),
            'timestamp': datetime.now().isoformat()
        }
        """Measure baseline light levels with all lights off."""
        print("Measuring baseline with all lights off...")
        
        # Turn off all lights
        self.light_controller.turn_off_all_lights()
        time.sleep(5)  # Wait for stabilization
        
        # Take multiple readings and average
        baseline_readings = []
        for i in range(num_readings):
            readings = self.sensor_reader.read_all_sensors()
            baseline_readings.append(readings)
            if i < num_readings - 1:
                time.sleep(delay)
        
        # Calculate averages
        baseline = {}
        for sensor_id in baseline_readings[0].keys():
            values = [r[sensor_id] for r in baseline_readings if r[sensor_id] is not None]
            if values:
                baseline[sensor_id] = sum(values) / len(values)
            else:
                baseline[sensor_id] = 0.0
        
    def measure_baseline(self, num_readings: int = 5, delay: float = 2.0) -> Dict[str, float]:
        """Measure baseline light levels with all lights off (basic sensors only)."""
        print("Measuring baseline with all lights off...")
        
        # Turn off all lights
        self.light_controller.turn_off_all_lights()
        time.sleep(5)  # Wait for stabilization
        
        # Take multiple readings and average
        baseline_readings = []
        for i in range(num_readings):
            readings = self.sensor_reader.read_all_sensors()
            baseline_readings.append(readings)
            if i < num_readings - 1:
                time.sleep(delay)
        
        # Calculate averages
        baseline = {}
        for sensor_id in baseline_readings[0].keys():
            values = [r[sensor_id] for r in baseline_readings if r[sensor_id] is not None]
            if values:
                baseline[sensor_id] = sum(values) / len(values)
            else:
                baseline[sensor_id] = 0.0
        
        print(f"Baseline measurements: {baseline}")
        return baseline
    
    def calibrate_light_comprehensive(self, light_id: str, baseline: Dict, 
                                     num_readings: int = 5, delay: float = 2.0, lux_stddev_percent: float = 5.0) -> Dict:
        """
        Comprehensive calibration including spectrum analysis for a single light.
        Uses a stability check on lux readings: if the standard deviation exceeds lux_stddev_percent of the mean,
        up to 3 rounds of readings are taken. If still unstable, raises an error.
        Tuning parameter: lux_stddev_percent (default 5.0). Adjust as needed for your environment.
        Only the lux readings are used for steadiness check. See documentation for tuning guidance.
        """
        import statistics
        print(f"Comprehensive calibration of light: {light_id}")
        self.light_controller.turn_off_all_lights()
        time.sleep(2)
        self.light_controller.turn_on_light(light_id)
        time.sleep(5)  # Wait for stabilization
        max_attempts = 3
        for attempt in range(max_attempts):
            light_readings = []
            for i in range(num_readings):
                basic_readings = self.sensor_reader.read_all_sensors()
                spectral_readings = self.spectral_reader.read_comprehensive_data()
                combined_reading = {
                    'basic': basic_readings,
                    'spectral': spectral_readings,
                    'timestamp': time.time()
                }
                light_readings.append(combined_reading)
                if i < num_readings - 1:
                    time.sleep(delay)
            # Check lux stability
            lux_values = []
            for reading in light_readings:
                for v in reading['basic'].values():
                    if v is not None:
                        lux_values.append(v)
            print(f"[DEBUG] Lux values for stability check: {lux_values}")
            stdev_percent = None
            if len(lux_values) == 0:
                print("No valid lux readings collected. Retrying...")
            elif len(lux_values) == 1:
                mean_lux = lux_values[0]
                stddev_lux = 0.0
                percent = 0.0
                stdev_percent = percent
                print(f"Lux stability check: mean={mean_lux:.2f}, stddev={stddev_lux:.2f}, percent={percent:.2f}% (threshold {lux_stddev_percent}%) [single value, treated as stable]")
                light_data = self._process_comprehensive_readings(light_readings)
                light_data['lux_stdev_percent'] = stdev_percent
                # Analyze spectrum characteristics
                spectrum_analysis = self.spectral_reader.analyze_light_spectrum(
                    light_id, 
                    baseline.get('spectral_sensors', {}),
                    light_data.get('spectral_sensors', {})
                )
                # Calculate basic effects (for backward compatibility)
                basic_effect = {}
                baseline_basic = baseline.get('basic_sensors', {})
                light_basic = light_data.get('basic_sensors', {})
                for sensor_id in baseline_basic.keys():
                    if sensor_id in light_basic:
                        basic_effect[sensor_id] = light_basic[sensor_id] - baseline_basic.get(sensor_id, 0)
                self.light_controller.turn_off_light(light_id)
                result = {
                    'light_id': light_id,
                    'basic_effect': basic_effect,
                    'light_data': light_data,
                    'spectrum_analysis': spectrum_analysis,
                    'timestamp': datetime.now().isoformat(),
                    'lux_stdev_percent': stdev_percent
                }
                print(f"Comprehensive calibration complete for {light_id} (stable), stdev_percent={stdev_percent:.2f}%")
                return result
            else:
                mean_lux = sum(lux_values) / len(lux_values)
                stddev_lux = statistics.stdev(lux_values)
                if mean_lux > 0:
                    percent = 100.0 * stddev_lux / mean_lux
                    stdev_percent = percent
                    print(f"Lux stability check: mean={mean_lux:.2f}, stddev={stddev_lux:.2f}, percent={percent:.2f}% (threshold {lux_stddev_percent}%)")
                    if percent <= lux_stddev_percent:
                        light_data = self._process_comprehensive_readings(light_readings)
                        light_data['lux_stdev_percent'] = stdev_percent
                        # Analyze spectrum characteristics
                        spectrum_analysis = self.spectral_reader.analyze_light_spectrum(
                            light_id, 
                            baseline.get('spectral_sensors', {}),
                            light_data.get('spectral_sensors', {})
                        )
                        # Calculate basic effects (for backward compatibility)
                        basic_effect = {}
                        baseline_basic = baseline.get('basic_sensors', {})
                        light_basic = light_data.get('basic_sensors', {})
                        for sensor_id in baseline_basic.keys():
                            if sensor_id in light_basic:
                                basic_effect[sensor_id] = light_basic[sensor_id] - baseline_basic.get(sensor_id, 0)
                        self.light_controller.turn_off_light(light_id)
                        result = {
                            'light_id': light_id,
                            'basic_effect': basic_effect,
                            'light_data': light_data,
                            'spectrum_analysis': spectrum_analysis,
                            'timestamp': datetime.now().isoformat(),
                            'lux_stdev_percent': stdev_percent
                        }
                        print(f"Comprehensive calibration complete for {light_id} (stable), stdev_percent={stdev_percent:.2f}%")
                        return result
                    else:
                        print(f"Lux readings not steady (attempt {attempt+1}/{max_attempts}), retrying...")
                else:
                    print("Mean lux is zero, cannot check stability. Retrying...")
        self.light_controller.turn_off_light(light_id)
        raise RuntimeError(f"Lux readings did not stabilize after {max_attempts} attempts. Calibration failed.")
        """Calibrate a single light by measuring its effect on all sensors."""
        print(f"Calibrating light: {light_id}")
        
        # Turn on only this light
        self.light_controller.turn_off_all_lights()
        time.sleep(2)
        self.light_controller.turn_on_light(light_id)
        time.sleep(5)  # Wait for stabilization
        
        # Take multiple readings
        light_readings = []
        for i in range(num_readings):
            readings = self.sensor_reader.read_all_sensors()
            light_readings.append(readings)
            if i < num_readings - 1:
                time.sleep(delay)
        
        # Calculate averages and differences from baseline
        light_effect = {}
        for sensor_id in light_readings[0].keys():
            values = [r[sensor_id] for r in light_readings if r[sensor_id] is not None]
            if values:
                avg_reading = sum(values) / len(values)
                light_effect[sensor_id] = avg_reading - baseline.get(sensor_id, 0)
            else:
                light_effect[sensor_id] = 0.0
        
        # Turn off the light
        self.light_controller.turn_off_light(light_id)
        
    def calibrate_light(self, light_id: str, baseline: Dict[str, float], 
                       num_readings: int = 5, delay: float = 2.0) -> Dict[str, float]:
        """Calibrate a single light by measuring its effect on all sensors (basic version)."""
        print(f"Calibrating light: {light_id}")
        
        # Turn on only this light
        self.light_controller.turn_off_all_lights()
        time.sleep(2)
        self.light_controller.turn_on_light(light_id)
        time.sleep(5)  # Wait for stabilization
        
        # Take multiple readings
        light_readings = []
        for i in range(num_readings):
            readings = self.sensor_reader.read_all_sensors()
            light_readings.append(readings)
            if i < num_readings - 1:
                time.sleep(delay)
        
        # Calculate averages and differences from baseline
        light_effect = {}
        for sensor_id in light_readings[0].keys():
            values = [r[sensor_id] for r in light_readings if r[sensor_id] is not None]
            if values:
                avg_reading = sum(values) / len(values)
                light_effect[sensor_id] = avg_reading - baseline.get(sensor_id, 0)
            else:
                light_effect[sensor_id] = 0.0
        
        # Turn off the light
        self.light_controller.turn_off_light(light_id)
        
        print(f"Light {light_id} effect: {light_effect}")
        return light_effect
    
    def run_comprehensive_calibration(self) -> Dict:
        """Run complete calibration with spectrum analysis for all lights."""
        print("Starting comprehensive light calibration with spectrum analysis...")
        
        calibration_timestamp = datetime.now().isoformat()
        
        # Measure comprehensive baseline
        baseline = self.measure_baseline_comprehensive()
        
        # Calibrate each light comprehensively
        light_effects = {}
        spectrum_profiles = {}
        
        for light_id in self.lights_config.keys():
            try:
                comprehensive_result = self.calibrate_light_comprehensive(light_id, baseline)
                
                # Store basic effects for optimization compatibility
                light_effects[light_id] = comprehensive_result['basic_effect']
                
                # Store spectrum profiles
                spectrum_profiles[light_id] = {
                    'spectrum_analysis': comprehensive_result['spectrum_analysis'],
                    'light_data': comprehensive_result['light_data']
                }
                
            except Exception as e:
                print(f"Error in comprehensive calibration of light {light_id}: {e}")
                light_effects[light_id] = {}
                spectrum_profiles[light_id] = {'error': str(e)}
        
        # Store calibration data with spectrum information
        self.calibration_data = {
            'timestamp': calibration_timestamp,
            'calibration_type': 'comprehensive',
            'baseline': baseline.get('basic_sensors', {}),  # Backward compatibility
            'comprehensive_baseline': baseline,
            'light_effects': light_effects,
            'spectrum_profiles': spectrum_profiles,
            'sensor_zones': self.sensor_reader.get_sensor_zones()
        }
        
        self._save_calibration_data()
        
        print("Comprehensive calibration complete!")
        return self.calibration_data
        """Run complete calibration process for all lights."""
        print("Starting full light calibration...")
        
        calibration_timestamp = datetime.now().isoformat()
        
        # Measure baseline
        baseline = self.measure_baseline()
        
        # Calibrate each light
        light_effects = {}
        for light_id in self.lights_config.keys():
            try:
                effect = self.calibrate_light(light_id, baseline)
                light_effects[light_id] = effect
            except Exception as e:
                print(f"Error calibrating light {light_id}: {e}")
                light_effects[light_id] = {}
        
        # Store calibration data
        self.calibration_data = {
            'timestamp': calibration_timestamp,
            'baseline': baseline,
            'light_effects': light_effects,
            'sensor_zones': self.sensor_reader.get_sensor_zones()
        }
        
        self._save_calibration_data()
        
    def run_full_calibration(self) -> Dict:
        """Run complete calibration process for all lights (basic version)."""
        print("Starting full light calibration...")
        
        calibration_timestamp = datetime.now().isoformat()
        
        # Measure baseline
        baseline = self.measure_baseline()
        
        # Calibrate each light
        light_effects = {}
        for light_id in self.lights_config.keys():
            try:
                effect = self.calibrate_light(light_id, baseline)
                light_effects[light_id] = effect
            except Exception as e:
                print(f"Error calibrating light {light_id}: {e}")
                light_effects[light_id] = {}
        
        # Store calibration data
        self.calibration_data = {
            'timestamp': calibration_timestamp,
            'calibration_type': 'basic',
            'baseline': baseline,
            'light_effects': light_effects,
            'sensor_zones': self.sensor_reader.get_sensor_zones()
        }
        
        self._save_calibration_data()
        
        print("Calibration complete!")
        return self.calibration_data
    
    def calculate_light_combination(self, target_zones: Dict[str, float], 
                                  method: str = 'greedy', tolerance: float = 0.1) -> Dict[str, bool]:
        """Calculate which lights to turn on to achieve target illumination in zones."""
        if not self.calibration_data or 'light_effects' not in self.calibration_data:
            raise ValueError("No calibration data available. Run calibration first.")
        
        optimizer = LightOptimizer(self.calibration_data)
        
        if method == 'linear':
            return optimizer.linear_programming_optimization(target_zones)
        elif method == 'weighted_ls':
            return optimizer.weighted_least_squares_optimization(target_zones)
        elif method == 'multi_objective':
            return optimizer.multi_objective_optimization(target_zones)
        else:  # default to greedy
            return optimizer.greedy_optimization(target_zones)
    
    def optimize_for_zones(self, zones_config: Dict, method: str = 'multi_objective') -> Dict[str, bool]:
        """Optimize light settings based on zone requirements."""
        target_zones = {}
        
        # Extract PAR targets from zones config
        for zone_key, zone_data in zones_config.items():
            light_spectrum = zone_data.get('light_spectrum', {})
            par_target = light_spectrum.get('par_target')
            if par_target:
                target_zones[zone_key] = par_target
        
        if not target_zones:
            print("No PAR targets found in zones configuration")
            return {}
        
        print(f"Optimizing for targets: {target_zones}")
        return self.calculate_light_combination(target_zones, method=method)
    
    def extract_measured_spectrum(self, light_id: str) -> Optional[Dict[str, float]]:
        """Extract measured color spectrum for a specific light from calibration data."""
        if not self.calibration_data or 'spectrum_profiles' not in self.calibration_data:
            return None
        
        spectrum_profile = self.calibration_data['spectrum_profiles'].get(light_id, {})
        spectrum_analysis = spectrum_profile.get('spectrum_analysis', {})
        
        # Try to find spectral data from any sensor
        for sensor_id, sensor_data in spectrum_analysis.get('spectral_signature', {}).items():
            color_shift = sensor_data.get('color_shift')
            if color_shift:
                # Convert to positive percentages (assuming these are the dominant colors)
                total_color = sum(abs(v) for v in color_shift.values() if isinstance(v, (int, float)))
                if total_color > 0:
                    normalized_spectrum = {}
                    for color, value in color_shift.items():
                        if isinstance(value, (int, float)):
                            normalized_spectrum[color] = max(0, value) / total_color * 100
                    return normalized_spectrum
        
        return None
    
    def update_lights_with_measured_spectrum(self) -> Dict[str, bool]:
        """Update lights.json with measured spectrum data from calibration."""
        if not self.calibration_data or 'spectrum_profiles' not in self.calibration_data:
            print("No spectrum calibration data available")
            return {}
        
        updated_lights = {}
        lights_data = self.lights_config.copy()
        
        for light_id in lights_data.keys():
            measured_spectrum = self.extract_measured_spectrum(light_id)
            if measured_spectrum:
                # Update the spectrum section
                if 'spectrum' not in lights_data[light_id]:
                    lights_data[light_id]['spectrum'] = {}
                
                # Map measured colors to RGB percentages
                spectrum_section = lights_data[light_id]['spectrum']
                
                if 'red_percent' in measured_spectrum:
                    spectrum_section['red_percent'] = round(measured_spectrum['red_percent'], 1)
                if 'green_percent' in measured_spectrum:
                    spectrum_section['green_percent'] = round(measured_spectrum['green_percent'], 1)
                if 'blue_percent' in measured_spectrum:
                    spectrum_section['blue_percent'] = round(measured_spectrum['blue_percent'], 1)
                
                # Add calibration metadata
                spectrum_section['measured'] = True
                spectrum_section['calibration_timestamp'] = self.calibration_data.get('timestamp')
                
                updated_lights[light_id] = True
                print(f"Updated spectrum for {light_id}: {measured_spectrum}")
            else:
                updated_lights[light_id] = False
                print(f"No spectrum data available for {light_id}")
        
        # Save updated lights configuration
        if any(updated_lights.values()):
            lights_file = self.data_dir / 'lights.json'
            with open(lights_file, 'w') as f:
                json.dump({'lights': lights_data}, f, indent=2)
            print(f"Updated lights.json with measured spectrum data")
        
        return updated_lights
    
    def generate_spectrum_report(self) -> Dict:
        """Generate a comprehensive report of measured light spectrums."""
        if not self.calibration_data or 'spectrum_profiles' not in self.calibration_data:
            return {'error': 'No spectrum calibration data available'}
        
        report = {
            'calibration_timestamp': self.calibration_data.get('timestamp'),
            'lights_analyzed': {},
            'spectrum_summary': {},
            'recommendations': []
        }
        
        spectrum_profiles = self.calibration_data['spectrum_profiles']
        
        for light_id, profile in spectrum_profiles.items():
            if 'error' in profile:
                report['lights_analyzed'][light_id] = {'error': profile['error']}
                continue
            
            spectrum_analysis = profile.get('spectrum_analysis', {})
            light_report = {
                'light_name': self.lights_config.get(light_id, {}).get('name', light_id),
                'spectral_sensors': {},
                'color_analysis': {},
                'par_effectiveness': {}
            }
            
            # Analyze each sensor's response to this light
            for sensor_id, sensor_data in spectrum_analysis.get('spectral_signature', {}).items():
                sensor_report = {
                    'intensity_change': sensor_data.get('intensity_change', 0),
                    'spectral_response': sensor_data.get('spectral_change'),
                    'color_shift': sensor_data.get('color_shift'),
                    'par_increase': sensor_data.get('par_increase'),
                    'color_temp_change': sensor_data.get('color_temp_change')
                }
                
                light_report['spectral_sensors'][sensor_id] = sensor_report
                
                # Determine dominant colors
                color_shift = sensor_data.get('color_shift', {})
                if color_shift:
                    dominant_color = max(color_shift.keys(), key=lambda k: abs(color_shift.get(k, 0)))
                    light_report['color_analysis']['dominant_color'] = dominant_color
                    light_report['color_analysis']['dominant_strength'] = color_shift.get(dominant_color, 0)
            
            # PAR effectiveness analysis
            par_increases = [s.get('par_increase', 0) for s in light_report['spectral_sensors'].values() 
                           if s.get('par_increase') is not None]
            if par_increases:
                light_report['par_effectiveness'] = {
                    'average_par_increase': sum(par_increases) / len(par_increases),
                    'max_par_increase': max(par_increases),
                    'effectiveness_rating': 'high' if max(par_increases) > 1000 else 'moderate' if max(par_increases) > 500 else 'low'
                }
            
            report['lights_analyzed'][light_id] = light_report
        
        # Generate recommendations
        self._generate_spectrum_recommendations(report)
        
        return report
    
    def _generate_spectrum_recommendations(self, report: Dict):
        """Generate recommendations based on spectrum analysis."""
        recommendations = []
        
        for light_id, analysis in report['lights_analyzed'].items():
            if 'error' in analysis:
                continue
            
            light_name = analysis.get('light_name', light_id)
            par_eff = analysis.get('par_effectiveness', {})
            color_analysis = analysis.get('color_analysis', {})
            
            # PAR effectiveness recommendations
            rating = par_eff.get('effectiveness_rating', 'unknown')
            if rating == 'low':
                recommendations.append({
                    'type': 'efficiency',
                    'light': light_name,
                    'message': f'{light_name} shows low PAR effectiveness. Consider replacement with higher efficiency LED.'
                })
            elif rating == 'high':
                recommendations.append({
                    'type': 'optimization',
                    'light': light_name,
                    'message': f'{light_name} shows excellent PAR effectiveness. Good for primary growing areas.'
                })
            
            # Color balance recommendations
            dominant_color = color_analysis.get('dominant_color', '')
            if dominant_color:
                if 'blue' in dominant_color.lower():
                    recommendations.append({
                        'type': 'spectrum',
                        'light': light_name,
                        'message': f'{light_name} is blue-dominant. Good for vegetative growth and compact plants.'
                    })
                elif 'red' in dominant_color.lower():
                    recommendations.append({
                        'type': 'spectrum',
                        'light': light_name,
                        'message': f'{light_name} is red-dominant. Good for flowering and fruiting stages.'
                    })
        
        report['recommendations'] = recommendations
    
    def optimize_zones_with_adaptive_strategy(self, zone_requests: Dict[str, Dict]) -> Dict:
        """Optimize zones using adaptive strategies based on their capabilities."""
        if not self.adaptive_calibrator:
            self.adaptive_calibrator = AdaptiveZoneCalibrator(data_dir=str(self.data_dir))
            adaptive_data = self.adaptive_calibrator.run_adaptive_calibration()
        else:
            # Load existing adaptive data
            adaptive_file = self.data_dir / 'adaptive_calibration.json'
            if adaptive_file.exists():
                with open(adaptive_file, 'r') as f:
                    adaptive_data = json.load(f)
            else:
                adaptive_data = self.adaptive_calibrator.run_adaptive_calibration()
        
        # Initialize mixed capability optimizer
        if not self.mixed_optimizer:
            self.mixed_optimizer = MixedCapabilityOptimizer(adaptive_data)
        
        # Convert zone requests to ZoneTarget objects
        zone_targets = []
        for zone_key, request in zone_requests.items():
            target = self._create_zone_target_from_request(zone_key, request)
            zone_targets.append(target)
        
        # Run optimization
        optimization_results = self.mixed_optimizer.optimize_zones(zone_targets)
        
        # Format results
        results = {
            'timestamp': datetime.now().isoformat(),
            'optimization_type': 'adaptive_mixed_capability',
            'zone_results': {},
            'overall_summary': self._summarize_optimization_results(optimization_results)
        }
        
        for result in optimization_results:
            results['zone_results'][result.zone_key] = {
                'strategy_used': result.strategy_used.value,
                'success': result.success,
                'optimal_lights': result.optimal_lights,
                'predicted_metrics': {
                    'intensity': result.predicted_intensity,
                    'color_temp': result.predicted_color_temp,
                    'power_consumption': result.power_consumption
                },
                'accuracy_metrics': {
                    'intensity_accuracy': result.intensity_accuracy,
                    'color_accuracy': result.color_accuracy,
                    'confidence_score': result.confidence_score
                },
                'feedback': {
                    'limitations': result.limitations or [],
                    'suggestions': result.suggestions or [],
                    'fallback_used': result.fallback_used
                }
            }
        
        return results
    
    def _create_zone_target_from_request(self, zone_key: str, request: Dict) -> ZoneTarget:
        """Convert a zone request dictionary to a ZoneTarget object."""
        # Extract targets from different possible formats
        target_intensity = None
        target_par = None
        target_color_temp = None
        target_spectrum_ratios = None
        
        # Check for PAR target (common in zones config)
        light_spectrum = request.get('light_spectrum', {})
        if 'par_target' in light_spectrum:
            target_par = light_spectrum['par_target']
        elif 'target_par' in request:
            target_par = request['target_par']
        elif 'target_intensity' in request:
            target_intensity = request['target_intensity']
        
        # Check for color temperature
        if 'color_temperature' in light_spectrum:
            target_color_temp = light_spectrum['color_temperature']
        elif 'target_color_temp' in request:
            target_color_temp = request['target_color_temp']
        
        # Check for spectrum ratios
        spectrum_ratios = {}
        for color in ['blue_percent', 'green_percent', 'red_percent']:
            if color in light_spectrum:
                spectrum_ratios[color] = light_spectrum[color]
        
        if spectrum_ratios:
            target_spectrum_ratios = spectrum_ratios
        elif 'target_spectrum' in request:
            target_spectrum_ratios = request['target_spectrum']
        
        # Set priorities based on request
        intensity_priority = request.get('intensity_priority', 1.0)
        color_priority = request.get('color_priority', 0.8)
        efficiency_priority = request.get('efficiency_priority', 0.5)
        
        # Constraints
        max_power = request.get('max_power_consumption')
        required_lights = request.get('required_lights', [])
        forbidden_lights = request.get('forbidden_lights', [])
        
        # Fallback targets
        min_intensity = request.get('min_intensity')
        max_intensity = request.get('max_intensity')
        color_range = request.get('acceptable_color_range')
        
        return ZoneTarget(
            zone_key=zone_key,
            target_intensity=target_intensity,
            target_par=target_par,
            target_color_temp=target_color_temp,
            target_spectrum_ratios=target_spectrum_ratios,
            min_intensity=min_intensity,
            max_intensity=max_intensity,
            acceptable_color_range=color_range,
            intensity_priority=intensity_priority,
            color_priority=color_priority,
            efficiency_priority=efficiency_priority,
            max_power_consumption=max_power,
            required_lights=required_lights,
            forbidden_lights=forbidden_lights
        )
    
    def _summarize_optimization_results(self, results: List[OptimizationResult]) -> Dict:
        """Create a summary of optimization results across all zones."""
        total_zones = len(results)
        successful_zones = sum(1 for r in results if r.success)
        
        strategy_counts = {}
        total_power = 0
        total_lights_on = 0
        
        for result in results:
            strategy = result.strategy_used.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            if result.power_consumption:
                total_power += result.power_consumption
            
            total_lights_on += sum(1 for on in result.optimal_lights.values() if on)
        
        avg_confidence = sum(r.confidence_score for r in results) / total_zones if total_zones > 0 else 0
        
        return {
            'total_zones': total_zones,
            'successful_optimizations': successful_zones,
            'success_rate': successful_zones / total_zones if total_zones > 0 else 0,
            'strategies_used': strategy_counts,
            'total_power_consumption': total_power,
            'total_lights_activated': total_lights_on,
            'average_confidence': avg_confidence,
            'optimization_quality': 'excellent' if avg_confidence > 0.8 else 
                                  'good' if avg_confidence > 0.6 else
                                  'basic' if avg_confidence > 0.4 else 'limited'
        }
    
    def optimize_for_mixed_zone_types(self, crop_types: Dict[str, str], 
                                    growth_stages: Dict[str, str] = None) -> Dict:
        """Optimize zones based on crop types and growth stages with intelligent targeting."""
        # Define crop-specific targets
        crop_targets = {
            'lettuce': {
                'target_par': 180,
                'target_color_temp': 4000,
                'target_spectrum': {'blue_percent': 25, 'red_percent': 35, 'green_percent': 40},
                'intensity_priority': 1.0,
                'color_priority': 0.7
            },
            'basil': {
                'target_par': 200,
                'target_color_temp': 4500,
                'target_spectrum': {'blue_percent': 30, 'red_percent': 40, 'green_percent': 30},
                'intensity_priority': 1.0,
                'color_priority': 0.8
            },
            'tomatoes': {
                'target_par': 300,
                'target_color_temp': 3500,
                'target_spectrum': {'blue_percent': 20, 'red_percent': 50, 'green_percent': 30},
                'intensity_priority': 1.0,
                'color_priority': 0.9
            },
            'herbs': {
                'target_par': 150,
                'target_color_temp': 4200,
                'target_spectrum': {'blue_percent': 28, 'red_percent': 32, 'green_percent': 40},
                'intensity_priority': 0.8,
                'color_priority': 0.6
            }
        }
        
        # Growth stage modifiers
        stage_modifiers = {
            'seedling': {'par_multiplier': 0.5, 'blue_boost': 1.2},
            'vegetative': {'par_multiplier': 0.8, 'blue_boost': 1.1},
            'flowering': {'par_multiplier': 1.2, 'red_boost': 1.3},
            'fruiting': {'par_multiplier': 1.5, 'red_boost': 1.4}
        }
        
        # Build zone requests
        zone_requests = {}
        growth_stages = growth_stages or {}
        
        for zone_key, crop_type in crop_types.items():
            if crop_type in crop_targets:
                base_targets = crop_targets[crop_type].copy()
                
                # Apply growth stage modifiers
                stage = growth_stages.get(zone_key, 'vegetative')
                if stage in stage_modifiers:
                    modifier = stage_modifiers[stage]
                    
                    # Adjust PAR
                    if 'par_multiplier' in modifier:
                        base_targets['target_par'] *= modifier['par_multiplier']
                    
                    # Adjust spectrum
                    if 'target_spectrum' in base_targets:
                        spectrum = base_targets['target_spectrum'].copy()
                        
                        if 'blue_boost' in modifier and 'blue_percent' in spectrum:
                            spectrum['blue_percent'] *= modifier['blue_boost']
                        
                        if 'red_boost' in modifier and 'red_percent' in spectrum:
                            spectrum['red_percent'] *= modifier['red_boost']
                        
                        # Renormalize percentages
                        total = sum(spectrum.values())
                        if total > 0:
                            for color in spectrum:
                                spectrum[color] = (spectrum[color] / total) * 100
                        
                        base_targets['target_spectrum'] = spectrum
                
                zone_requests[zone_key] = base_targets
            else:
                # Default targets for unknown crop types
                zone_requests[zone_key] = {
                    'target_par': 200,
                    'target_color_temp': 4000,
                    'intensity_priority': 1.0,
                    'color_priority': 0.5
                }
        
        return self.optimize_zones_with_adaptive_strategy(zone_requests)
    
    def get_zone_capability_report(self) -> Dict:
        """Get a comprehensive report of zone capabilities and recommendations."""
        if not self.adaptive_calibrator:
            self.adaptive_calibrator = AdaptiveZoneCalibrator(data_dir=str(self.data_dir))
        
        return self.adaptive_calibrator.get_zone_status_report()
    
    def run_ambient_aware_calibration(self) -> Dict:
        """Run calibration with ambient light awareness and adaptive scheduling."""
        # Initialize ambient handler if needed
        if not self.ambient_handler:
            self.ambient_handler = AmbientAwareCalibrator(self.sensors_config)
        
        # Get current sensor readings to assess ambient conditions
        current_readings = {}
        for sensor_id, sensor_config in self.sensors_config.items():
            try:
                reading = self.sensor_reader.read_sensor(sensor_config)
                current_readings[sensor_id] = reading.get('lux') if reading else None
            except Exception as e:
                print(f"Warning: Could not read sensor {sensor_id}: {e}")
                current_readings[sensor_id] = None
        
        # Check if we should calibrate now
        should_calibrate, reason = self.ambient_handler.should_calibrate_now(current_readings)
        
        if not should_calibrate:
            # Return recommendation instead of calibrating
            schedule_info = self.ambient_handler.get_calibration_schedule_recommendations()
            return {
                'timestamp': datetime.now().isoformat(),
                'calibration_type': 'ambient_aware_deferred',
                'ambient_analysis': {
                    'decision': 'deferred',
                    'reason': reason,
                    'current_readings': current_readings
                },
                'recommendations': schedule_info,
                'suggested_actions': [
                    "Wait for better ambient conditions",
                    "Consider using blackout covers",
                    "Schedule automatic calibration for optimal times"
                ]
            }
        
        # Get ambient-adapted calibration parameters
        calibration_params = self.ambient_handler.get_adaptive_calibration_params(current_readings)
        
        # Run calibration with adaptive parameters
        print(f"Running ambient-aware calibration: {reason}")
        print(f"Ambient level: {calibration_params['ambient_conditions']['level']}")
        print(f"Feasibility: {calibration_params['ambient_conditions']['feasibility']:.2f}")
        
        # Measure baseline with ambient-adapted settings
        baseline = self._measure_ambient_aware_baseline(calibration_params)
        
        # Run light effects measurement with adaptive settings
        light_effects = self._measure_light_effects_with_ambient_adaptation(baseline, calibration_params)
        
        # Build calibration data
        calibration_data = {
            'timestamp': datetime.now().isoformat(),
            'calibration_type': 'ambient_aware',
            'ambient_conditions': calibration_params['ambient_conditions'],
            'calibration_parameters': calibration_params,
            'baseline': baseline,
            'light_effects': light_effects,
            'quality_metrics': self._assess_ambient_calibration_quality(
                baseline, light_effects, calibration_params
            )
        }
        
        # Record the calibration attempt
        success = calibration_data['quality_metrics']['overall_quality'] > 0.3
        self.ambient_handler.record_calibration_attempt(current_readings, success, calibration_data)
        
        # Save results
        self._save_calibration_data(calibration_data)
        
        return calibration_data
    
    def _measure_ambient_aware_baseline(self, params: Dict) -> Dict[str, float]:
        """Measure baseline with ambient light adaptations."""
        adjustments = params['calibration_adjustments']
        measurement_time = adjustments['baseline_measurement_time']
        repeats = adjustments['measurement_repeats']
        
        print(f"Measuring ambient-aware baseline ({repeats} samples, {measurement_time}s each)...")
        
        # Ensure all lights are off
        self.light_controller.turn_off_all_lights()
        time.sleep(adjustments['stabilization_delay'])
        
        # Collect multiple baseline measurements
        baseline_readings = {sensor_id: [] for sensor_id in self.sensors_config.keys()}
        
        for sample in range(repeats):
            print(f"  Baseline sample {sample + 1}/{repeats}")
            time.sleep(measurement_time)
            
            for sensor_id, sensor_config in self.sensors_config.items():
                try:
                    reading = self.sensor_reader.read_sensor(sensor_config)
                    lux_value = reading.get('lux') if reading else None
                    if lux_value is not None:
                        baseline_readings[sensor_id].append(lux_value)
                except Exception as e:
                    print(f"    Error reading {sensor_id}: {e}")
        
        # Calculate robust baseline (median to handle outliers)
        baseline = {}
        outlier_threshold = adjustments['outlier_rejection_threshold']
        
        for sensor_id, readings in baseline_readings.items():
            if readings:
                # Remove outliers if we have enough samples
                if len(readings) >= 3:
                    readings_sorted = sorted(readings)
                    median = readings_sorted[len(readings_sorted) // 2]
                    filtered_readings = [
                        r for r in readings 
                        if abs(r - median) / median <= outlier_threshold
                    ] if median > 0 else readings
                    baseline[sensor_id] = sum(filtered_readings) / len(filtered_readings)
                else:
                    baseline[sensor_id] = sum(readings) / len(readings)
            else:
                baseline[sensor_id] = 0.0
        
        return baseline
    
    def _measure_light_effects_with_ambient_adaptation(self, baseline: Dict, params: Dict) -> Dict:
        """Measure light effects with ambient adaptations."""
        adjustments = params['calibration_adjustments']
        constraints = params['optimization_constraints']
        
        light_effects = {}
        measurement_time = adjustments['light_measurement_time']
        repeats = adjustments['measurement_repeats']
        min_effect_threshold = constraints['min_light_effect_threshold']
        
        print(f"Measuring light effects with ambient adaptation...")
        
        for light_id in self.lights_config.keys():
            print(f"  Testing light: {light_id}")
            
            # Turn on the light
            self.light_controller.turn_on_light(light_id)
            time.sleep(adjustments['stabilization_delay'])
            
            # Collect measurements
            light_readings = {sensor_id: [] for sensor_id in self.sensors_config.keys()}
            
            for sample in range(repeats):
                time.sleep(measurement_time)
                
                for sensor_id, sensor_config in self.sensors_config.items():
                    try:
                        reading = self.sensor_reader.read_sensor(sensor_config)
                        lux_value = reading.get('lux') if reading else None
                        if lux_value is not None:
                            light_readings[sensor_id].append(lux_value)
                    except Exception as e:
                        print(f"    Error reading {sensor_id}: {e}")
            
            # Calculate effects
            light_effects[light_id] = {}
            for sensor_id in self.sensors_config.keys():
                readings = light_readings[sensor_id]
                if readings:
                    avg_reading = sum(readings) / len(readings)
                    effect = avg_reading - baseline.get(sensor_id, 0)
                    
                    # Apply minimum threshold filter
                    if abs(effect) < min_effect_threshold:
                        effect = 0.0  # Noise level
                    
                    light_effects[light_id][sensor_id] = effect
                else:
                    light_effects[light_id][sensor_id] = 0.0
            
            # Turn off the light
            self.light_controller.turn_off_light(light_id)
            time.sleep(0.5)  # Brief pause between lights
        
        return light_effects
    
    def _assess_ambient_calibration_quality(self, baseline: Dict, light_effects: Dict, params: Dict) -> Dict:
        """Assess the quality of ambient-aware calibration."""
        ambient_conditions = params['ambient_conditions']
        constraints = params['optimization_constraints']
        
        # Count detectable effects
        detectable_effects = 0
        total_effects = 0
        
        for light_id, effects in light_effects.items():
            for sensor_id, effect in effects.items():
                total_effects += 1
                if abs(effect) >= constraints['min_light_effect_threshold']:
                    detectable_effects += 1
        
        detection_rate = detectable_effects / total_effects if total_effects > 0 else 0
        
        # Assess signal-to-noise ratio
        avg_baseline = sum(baseline.values()) / len(baseline) if baseline else 0
        avg_effect = sum(
            abs(effect) for effects in light_effects.values() 
            for effect in effects.values()
        ) / total_effects if total_effects > 0 else 0
        
        signal_to_noise = avg_effect / avg_baseline if avg_baseline > 0 else float('inf')
        
        # Overall quality based on ambient conditions and measurements
        base_quality = min(1.0, detection_rate + signal_to_noise * 0.1)
        ambient_penalty = 1.0 - ambient_conditions['feasibility']
        overall_quality = max(0.0, base_quality - ambient_penalty * 0.5)
        
        return {
            'overall_quality': overall_quality,
            'detection_rate': detection_rate,
            'signal_to_noise_ratio': signal_to_noise,
            'detectable_effects': detectable_effects,
            'total_effects': total_effects,
            'ambient_feasibility': ambient_conditions['feasibility'],
            'quality_factors': {
                'ambient_light_level': ambient_conditions['level'],
                'average_baseline_lux': avg_baseline,
                'average_effect_size': avg_effect,
                'measurement_confidence': min(1.0, signal_to_noise / 10.0)
            }
        }
    
    def make_intelligent_light_decisions(self, current_time: Optional[datetime] = None) -> Dict:
        """Make intelligent decisions about light control using the decision engine."""
        if current_time is None:
            current_time = datetime.now()
        
        # Initialize decision engine if needed
        if not self.decision_engine:
            if not self.calibration_data:
                return {
                    'success': False,
                    'error': 'No calibration data available for decision making',
                    'recommendation': 'Run calibration first'
                }
            
            self.decision_engine = LightDecisionEngine(
                calibration_data=self.calibration_data,
                zones_config=self.zones_config,
                lights_config=self.lights_config,
                sensors_config=self.sensors_config
            )
        
        # Get current sensor readings
        current_readings = {}
        for sensor_id, sensor_config in self.sensors_config.items():
            try:
                reading = self.sensor_reader.read_sensor(sensor_config)
                current_readings[sensor_id] = reading.get('lux') if reading else None
            except Exception as e:
                print(f"Warning: Could not read sensor {sensor_id}: {e}")
                current_readings[sensor_id] = None
        
        # Make decisions
        decisions = self.decision_engine.make_light_decisions(current_readings, current_time)
        
        # Format results
        results = {
            'timestamp': current_time.isoformat(),
            'decision_type': 'intelligent_control',
            'total_lights': len(decisions),
            'lights_on': sum(1 for d in decisions if d.should_be_on),
            'total_power_consumption': sum(d.power_consumption for d in decisions if d.should_be_on),
            'average_confidence': sum(d.confidence for d in decisions) / len(decisions) if decisions else 0,
            'decisions': {},
            'decision_summary': self._summarize_decisions(decisions),
            'current_sensor_readings': current_readings
        }
        
        # Add individual decisions
        for decision in decisions:
            light_config = self.lights_config[decision.light_id]
            results['decisions'][decision.light_id] = {
                'light_name': light_config.get('name', decision.light_id),
                'should_be_on': decision.should_be_on,
                'intensity_percent': decision.intensity_percent,
                'confidence': decision.confidence,
                'primary_reason': decision.primary_reason.value,
                'contributing_factors': decision.contributing_factors,
                'power_consumption': decision.power_consumption,
                'priority_score': decision.priority_score,
                'estimated_effects': decision.estimated_effect,
                'explanation': self.decision_engine.get_decision_explanation(decision.light_id, decision)
            }
        
        return results
    
    def apply_intelligent_decisions(self, decisions_result: Dict, 
                                  dry_run: bool = False) -> Dict:
        """Apply the intelligent light decisions to actual hardware."""
        if not decisions_result.get('decisions'):
            return {'success': False, 'error': 'No decisions to apply'}
        
        application_results = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'applied_decisions': {},
            'errors': [],
            'summary': {
                'lights_turned_on': 0,
                'lights_turned_off': 0,
                'total_power_change': 0
            }
        }
        
        for light_id, decision in decisions_result['decisions'].items():
            try:
                current_state = self.light_controller.get_light_state(light_id) if hasattr(self.light_controller, 'get_light_state') else None
                
                if not dry_run:
                    if decision['should_be_on']:
                        success = self.light_controller.turn_on_light(light_id)
                        if success:
                            application_results['summary']['lights_turned_on'] += 1
                    else:
                        success = self.light_controller.turn_off_light(light_id)
                        if success:
                            application_results['summary']['lights_turned_off'] += 1
                else:
                    success = True  # Simulate success for dry run
                
                application_results['applied_decisions'][light_id] = {
                    'success': success,
                    'action': 'turn_on' if decision['should_be_on'] else 'turn_off',
                    'intensity_requested': decision['intensity_percent'],
                    'previous_state': current_state,
                    'power_change': decision['power_consumption'] if decision['should_be_on'] else -decision['power_consumption']
                }
                
                if success and decision['should_be_on']:
                    application_results['summary']['total_power_change'] += decision['power_consumption']
                elif success and not decision['should_be_on']:
                    application_results['summary']['total_power_change'] -= decision['power_consumption']
                
            except Exception as e:
                error_msg = f"Failed to control light {light_id}: {e}"
                application_results['errors'].append(error_msg)
                application_results['applied_decisions'][light_id] = {
                    'success': False,
                    'error': str(e)
                }
        
        application_results['success'] = len(application_results['errors']) == 0
        return application_results
    
    def run_automated_light_control_cycle(self) -> Dict:
        """Run a complete automated light control cycle."""
        cycle_start = datetime.now()
        
        print("🤖 Starting automated light control cycle...")
        
        # Step 1: Make intelligent decisions
        print("  📊 Analyzing conditions and making decisions...")
        decisions_result = self.make_intelligent_light_decisions(cycle_start)
        
        if not decisions_result.get('decisions'):
            return {
                'success': False,
                'error': 'Failed to make light decisions',
                'details': decisions_result
            }
        
        # Step 2: Check if decisions make sense
        print("  🔍 Validating decisions...")
        validation_result = self._validate_decisions(decisions_result)
        
        if not validation_result['valid']:
            return {
                'success': False,
                'error': 'Decision validation failed',
                'validation_issues': validation_result['issues'],
                'decisions': decisions_result
            }
        
        # Step 3: Apply decisions
        print("  ⚡ Applying light control decisions...")
        application_result = self.apply_intelligent_decisions(decisions_result)
        
        # Step 4: Verify results
        print("  ✅ Verifying applied changes...")
        verification_result = self._verify_light_control_results(
            decisions_result, application_result
        )
        
        cycle_end = datetime.now()
        cycle_duration = (cycle_end - cycle_start).total_seconds()
        
        return {
            'success': application_result['success'],
            'cycle_duration_seconds': cycle_duration,
            'decisions': decisions_result,
            'application': application_result,
            'validation': validation_result,
            'verification': verification_result,
            'summary': {
                'lights_controlled': len(decisions_result['decisions']),
                'lights_turned_on': application_result['summary']['lights_turned_on'],
                'lights_turned_off': application_result['summary']['lights_turned_off'],
                'total_power_consumption': decisions_result['total_power_consumption'],
                'average_decision_confidence': decisions_result['average_confidence'],
                'cycle_timestamp': cycle_start.isoformat()
            }
        }
    
    def _summarize_decisions(self, decisions: List[LightDecision]) -> Dict:
        """Create a summary of the light decisions."""
        if not decisions:
            return {}
        
        # Count decisions by reason
        reason_counts = {}
        for decision in decisions:
            reason = decision.primary_reason.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        # Calculate statistics
        lights_on = [d for d in decisions if d.should_be_on]
        lights_off = [d for d in decisions if not d.should_be_on]
        
        return {
            'total_decisions': len(decisions),
            'lights_on': len(lights_on),
            'lights_off': len(lights_off),
            'decisions_by_reason': reason_counts,
            'confidence_stats': {
                'average': sum(d.confidence for d in decisions) / len(decisions),
                'minimum': min(d.confidence for d in decisions),
                'maximum': max(d.confidence for d in decisions)
            },
            'power_stats': {
                'total_consumption': sum(d.power_consumption for d in lights_on),
                'average_per_light': sum(d.power_consumption for d in lights_on) / len(lights_on) if lights_on else 0,
                'highest_consumer': max(lights_on, key=lambda d: d.power_consumption).light_id if lights_on else None
            },
            'priority_stats': {
                'average_priority': sum(d.priority_score for d in decisions) / len(decisions),
                'high_priority_lights': [d.light_id for d in decisions if d.priority_score > 0.8]
            }
        }
    
    def _validate_decisions(self, decisions_result: Dict) -> Dict:
        """Validate that the decisions make sense."""
        issues = []
        
        # Check total power consumption
        total_power = decisions_result.get('total_power_consumption', 0)
        if total_power > 2000:  # Configurable limit
            issues.append(f"Total power consumption ({total_power:.0f}W) exceeds recommended limit")
        
        # Check if any lights are on without clear justification
        low_confidence_on = []
        for light_id, decision in decisions_result['decisions'].items():
            if decision['should_be_on'] and decision['confidence'] < 0.3:
                low_confidence_on.append(light_id)
        
        if low_confidence_on:
            issues.append(f"Low confidence decisions for lights: {', '.join(low_confidence_on)}")
        
        # Check for zone conflicts
        zone_lights = {}
        for light_id, decision in decisions_result['decisions'].items():
            light_config = self.lights_config[light_id]
            zone_key = light_config.get('zone_key')
            if zone_key and decision['should_be_on']:
                if zone_key not in zone_lights:
                    zone_lights[zone_key] = []
                zone_lights[zone_key].append(light_id)
        
        for zone_key, lights in zone_lights.items():
            if len(lights) > 2:  # More than 2 lights on in same zone might be excessive
                issues.append(f"Zone {zone_key} has {len(lights)} lights on simultaneously")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'validation_timestamp': datetime.now().isoformat()
        }
    
    def _verify_light_control_results(self, decisions_result: Dict, 
                                    application_result: Dict) -> Dict:
        """Verify that the light control was applied correctly."""
        verification_issues = []
        
        # Check if all decisions were applied
        expected_actions = len(decisions_result['decisions'])
        actual_actions = len(application_result['applied_decisions'])
        
        if expected_actions != actual_actions:
            verification_issues.append(f"Expected {expected_actions} actions, applied {actual_actions}")
        
        # Check for any errors
        if application_result.get('errors'):
            verification_issues.append(f"Application errors: {len(application_result['errors'])}")
        
        # Could add sensor reading verification here to check if lights actually turned on/off
        
        return {
            'verified': len(verification_issues) == 0,
            'issues': verification_issues,
            'verification_timestamp': datetime.now().isoformat()
        }
    
    def cleanup(self):
        """Clean up resources."""
        self.light_controller.cleanup()


def main():
    """Example usage of the calibration system."""
    calibrator = LightCalibrator()
    
    try:
        # Run calibration
        calibration_data = calibrator.run_full_calibration()
        
        # Load zones and optimize
        zones_config = calibrator._load_json('zones.json').get('zones', {})
        optimal_lights = calibrator.optimize_for_zones(zones_config)
        
        print(f"Optimal light combination: {optimal_lights}")
        
        # Apply the optimal combination
        for light_id, should_be_on in optimal_lights.items():
            if should_be_on:
                calibrator.light_controller.turn_on_light(light_id)
            else:
                calibrator.light_controller.turn_off_light(light_id)
        
    except KeyboardInterrupt:
        print("Calibration interrupted")
    finally:
        calibrator.cleanup()


if __name__ == "__main__":
    main()