"""Advanced spectral light sensor support for color spectrum measurement.

This module extends the basic light sensors to include color/spectral measurement
capabilities for comprehensive light characterization during calibration.
"""
import time
from typing import Dict, List, Optional, Tuple

# Spectral sensor implementations
try:
    import board
    import busio
    import adafruit_as7341  # 11-channel spectral sensor
    import adafruit_tcs34725  # RGB color sensor
    _HAS_SPECTRAL = True
except ImportError:
    _HAS_SPECTRAL = False

try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except ImportError:
    _HAS_SMBUS = False


class AS7341Spectral:
    """AS7341 11-channel spectral sensor for detailed spectrum analysis."""
    
    DEFAULT_ADDR = 0x39
    
    # Channel wavelength centers (nm)
    CHANNELS = {
        'violet': 415,
        'indigo': 445, 
        'blue': 480,
        'cyan': 515,
        'green': 555,
        'yellow': 590,
        'orange': 630,
        'red': 680,
        'nir_1': 730,
        'nir_2': 850,
        'clear': None  # broadband
    }
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr
        self.sensor = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the AS7341 sensor."""
        if not _HAS_SPECTRAL:
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_as7341.AS7341(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize AS7341: {e}")
            self.sensor = None
    
    def read_spectrum(self) -> Optional[Dict[str, float]]:
        """Read full spectral data from all channels."""
        if not self.sensor:
            return None
        
        try:
            # Read all channels
            readings = {}
            
            # Channel 1-6 (F1-F6)
            channel_data = self.sensor.channel_415nm  # F1 - violet
            readings['violet'] = channel_data
            
            readings['indigo'] = self.sensor.channel_445nm   # F2
            readings['blue'] = self.sensor.channel_480nm     # F3
            readings['cyan'] = self.sensor.channel_515nm     # F4
            readings['green'] = self.sensor.channel_555nm    # F5
            readings['yellow'] = self.sensor.channel_590nm   # F6
            
            # Channel 7-8 (F7-F8) 
            readings['orange'] = self.sensor.channel_630nm   # F7
            readings['red'] = self.sensor.channel_680nm      # F8
            
            # NIR channels
            readings['nir_1'] = self.sensor.channel_730nm    # NIR
            readings['nir_2'] = self.sensor.channel_850nm    # NIR
            
            # Clear channel (broadband)
            readings['clear'] = self.sensor.channel_clear
            
            return readings
            
        except Exception as e:
            print(f"Error reading AS7341: {e}")
            return None
    
    def calculate_color_ratios(self, spectrum: Dict[str, float]) -> Dict[str, float]:
        """Calculate color percentage ratios from spectrum data."""
        if not spectrum:
            return {}
        
        # Group channels into color categories
        blue_channels = ['violet', 'indigo', 'blue']
        green_channels = ['cyan', 'green']
        red_channels = ['yellow', 'orange', 'red']
        
        blue_total = sum(spectrum.get(ch, 0) for ch in blue_channels)
        green_total = sum(spectrum.get(ch, 0) for ch in green_channels)
        red_total = sum(spectrum.get(ch, 0) for ch in red_channels)
        
        total_visible = blue_total + green_total + red_total
        
        if total_visible == 0:
            return {'blue_percent': 0, 'green_percent': 0, 'red_percent': 0}
        
        return {
            'blue_percent': (blue_total / total_visible) * 100,
            'green_percent': (green_total / total_visible) * 100,
            'red_percent': (red_total / total_visible) * 100
        }
    
    def calculate_par_weight(self, spectrum: Dict[str, float]) -> float:
        """Calculate PAR-weighted light intensity."""
        if not spectrum:
            return 0.0
        
        # PAR weighting factors for plant photosynthesis (simplified)
        par_weights = {
            'violet': 0.1,   # 400-450nm - some effect
            'indigo': 0.3,   # 450-500nm - blue light response
            'blue': 0.8,     # 480-520nm - peak blue response
            'cyan': 0.9,     # 500-550nm - good for photosynthesis
            'green': 0.7,    # 520-600nm - moderate effectiveness
            'yellow': 0.9,   # 580-620nm - good red light start
            'orange': 1.0,   # 620-680nm - peak red response
            'red': 1.0,      # 660-700nm - peak red response
            'nir_1': 0.2,    # 700-800nm - far red effects
            'nir_2': 0.0     # >800nm - minimal photosynthetic effect
        }
        
        par_total = 0
        for channel, intensity in spectrum.items():
            weight = par_weights.get(channel, 0)
            par_total += intensity * weight
        
        return par_total


class TCS34725Color:
    """TCS34725 RGB color sensor for basic color analysis."""
    
    DEFAULT_ADDR = 0x29
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr
        self.sensor = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the TCS34725 sensor."""
        if not _HAS_SPECTRAL:
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_tcs34725.TCS34725(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize TCS34725: {e}")
            self.sensor = None
    
    def read_color(self) -> Optional[Dict[str, float]]:
        """Read RGB color data."""
        if not self.sensor:
            return None
        
        try:
            # Read RGBC values
            r, g, b, c = self.sensor.color_raw
            
            # Calculate color temperature and lux
            color_temp = self.sensor.color_temperature
            lux = self.sensor.lux
            
            return {
                'red_raw': r,
                'green_raw': g, 
                'blue_raw': b,
                'clear_raw': c,
                'color_temperature_k': color_temp,
                'lux': lux
            }
            
        except Exception as e:
            print(f"Error reading TCS34725: {e}")
            return None
    
    def calculate_rgb_ratios(self, color_data: Dict[str, float]) -> Dict[str, float]:
        """Calculate RGB percentage ratios."""
        if not color_data:
            return {}
        
        r = color_data.get('red_raw', 0)
        g = color_data.get('green_raw', 0)
        b = color_data.get('blue_raw', 0)
        
        total_rgb = r + g + b
        
        if total_rgb == 0:
            return {'red_percent': 0, 'green_percent': 0, 'blue_percent': 0}
        
        return {
            'red_percent': (r / total_rgb) * 100,
            'green_percent': (g / total_rgb) * 100,
            'blue_percent': (b / total_rgb) * 100
        }


class SpectralSensorReader:
    """Enhanced sensor reader that includes spectral measurement capabilities."""
    
    def __init__(self, sensors_config: Dict):
        self.sensors_config = sensors_config
        self.spectral_sensors = {}
        self.basic_sensors = {}
        
        self._initialize_sensors()
    
    def _initialize_sensors(self):
        """Initialize both basic and spectral sensors."""
        for sensor_id, config in self.sensors_config.items():
            sensor_type = config.get('type', '').upper()
            connection = config.get('connection', {})
            
            try:
                if sensor_type == 'AS7341':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', AS7341Spectral.DEFAULT_ADDR)
                    self.spectral_sensors[sensor_id] = {
                        'instance': AS7341Spectral(bus=bus, addr=addr),
                        'config': config,
                        'type': 'spectral'
                    }
                elif sensor_type == 'TCS34725':
                    bus = connection.get('bus', 1) 
                    addr = connection.get('address', TCS34725Color.DEFAULT_ADDR)
                    self.spectral_sensors[sensor_id] = {
                        'instance': TCS34725Color(bus=bus, addr=addr),
                        'config': config,
                        'type': 'color'
                    }
                else:
                    # Fall back to basic sensors (BH1750, etc.)
                    from control.light_calibration import SensorReader
                    basic_reader = SensorReader({sensor_id: config})
                    if basic_reader.sensors:
                        self.basic_sensors[sensor_id] = basic_reader.sensors[sensor_id]
                        
            except Exception as e:
                print(f"Failed to initialize sensor {sensor_id}: {e}")
    
    def read_comprehensive_data(self) -> Dict[str, Dict]:
        """Read both intensity and spectral data from all sensors."""
        results = {}
        
        # Read spectral sensors
        for sensor_id, sensor_data in self.spectral_sensors.items():
            sensor = sensor_data['instance']
            sensor_type = sensor_data['type']
            
            try:
                if sensor_type == 'spectral' and isinstance(sensor, AS7341Spectral):
                    spectrum = sensor.read_spectrum()
                    if spectrum:
                        color_ratios = sensor.calculate_color_ratios(spectrum)
                        par_weight = sensor.calculate_par_weight(spectrum)
                        
                        results[sensor_id] = {
                            'type': 'spectral',
                            'spectrum': spectrum,
                            'color_ratios': color_ratios,
                            'par_weighted_intensity': par_weight,
                            'total_intensity': spectrum.get('clear', 0)
                        }
                
                elif sensor_type == 'color' and isinstance(sensor, TCS34725Color):
                    color_data = sensor.read_color()
                    if color_data:
                        rgb_ratios = sensor.calculate_rgb_ratios(color_data)
                        
                        results[sensor_id] = {
                            'type': 'color',
                            'color_data': color_data,
                            'rgb_ratios': rgb_ratios,
                            'lux': color_data.get('lux', 0),
                            'color_temperature': color_data.get('color_temperature_k', 0)
                        }
                        
            except Exception as e:
                print(f"Error reading spectral sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        # Read basic sensors
        for sensor_id, sensor_data in self.basic_sensors.items():
            try:
                sensor = sensor_data['instance']
                if hasattr(sensor, 'read_lux'):
                    lux = sensor.read_lux()
                    results[sensor_id] = {
                        'type': 'basic',
                        'lux': lux
                    }
            except Exception as e:
                print(f"Error reading basic sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        return results
    
    def analyze_light_spectrum(self, light_id: str, 
                             baseline_data: Dict, 
                             light_on_data: Dict) -> Dict:
        """Analyze the spectral characteristics of a specific light."""
        analysis = {
            'light_id': light_id,
            'spectral_signature': {},
            'color_analysis': {},
            'par_effectiveness': {}
        }
        
        for sensor_id in baseline_data.keys():
            if sensor_id in light_on_data:
                baseline = baseline_data[sensor_id]
                light_on = light_on_data[sensor_id]
                
                sensor_analysis = {
                    'sensor_id': sensor_id,
                    'intensity_change': 0,
                    'spectral_change': None,
                    'color_shift': None
                }
                
                # Analyze based on sensor type
                if baseline.get('type') == 'spectral' and light_on.get('type') == 'spectral':
                    # Calculate spectral differences
                    baseline_spectrum = baseline.get('spectrum', {})
                    light_spectrum = light_on.get('spectrum', {})
                    
                    spectral_diff = {}
                    for channel in baseline_spectrum.keys():
                        baseline_val = baseline_spectrum.get(channel, 0)
                        light_val = light_spectrum.get(channel, 0)
                        spectral_diff[channel] = light_val - baseline_val
                    
                    sensor_analysis['spectral_change'] = spectral_diff
                    
                    # Color ratio changes
                    baseline_colors = baseline.get('color_ratios', {})
                    light_colors = light_on.get('color_ratios', {})
                    
                    color_shift = {}
                    for color in baseline_colors.keys():
                        baseline_pct = baseline_colors.get(color, 0)
                        light_pct = light_colors.get(color, 0)
                        color_shift[color] = light_pct - baseline_pct
                    
                    sensor_analysis['color_shift'] = color_shift
                    
                    # PAR effectiveness
                    baseline_par = baseline.get('par_weighted_intensity', 0)
                    light_par = light_on.get('par_weighted_intensity', 0)
                    sensor_analysis['par_increase'] = light_par - baseline_par
                
                elif baseline.get('type') == 'color' and light_on.get('type') == 'color':
                    # RGB analysis
                    baseline_rgb = baseline.get('rgb_ratios', {})
                    light_rgb = light_on.get('rgb_ratios', {})
                    
                    rgb_shift = {}
                    for color in baseline_rgb.keys():
                        baseline_pct = baseline_rgb.get(color, 0)
                        light_pct = light_rgb.get(color, 0)
                        rgb_shift[color] = light_pct - baseline_pct
                    
                    sensor_analysis['color_shift'] = rgb_shift
                    
                    # Color temperature change
                    baseline_temp = baseline.get('color_data', {}).get('color_temperature_k', 0)
                    light_temp = light_on.get('color_data', {}).get('color_temperature_k', 0)
                    sensor_analysis['color_temp_change'] = light_temp - baseline_temp
                
                # Basic intensity change for all sensor types
                baseline_intensity = (baseline.get('lux', 0) or 
                                    baseline.get('total_intensity', 0) or 
                                    baseline.get('par_weighted_intensity', 0))
                light_intensity = (light_on.get('lux', 0) or 
                                 light_on.get('total_intensity', 0) or 
                                 light_on.get('par_weighted_intensity', 0))
                
                sensor_analysis['intensity_change'] = light_intensity - baseline_intensity
                
                analysis['spectral_signature'][sensor_id] = sensor_analysis
        
        return analysis


# Mock implementations for testing without hardware
class MockAS7341:
    """Mock AS7341 for testing without hardware."""
    
    def read_spectrum(self):
        import random
        return {
            'violet': random.uniform(100, 500),
            'indigo': random.uniform(200, 800), 
            'blue': random.uniform(300, 1000),
            'cyan': random.uniform(400, 1200),
            'green': random.uniform(500, 1500),
            'yellow': random.uniform(300, 1000),
            'orange': random.uniform(200, 800),
            'red': random.uniform(400, 1200),
            'nir_1': random.uniform(100, 400),
            'nir_2': random.uniform(50, 200),
            'clear': random.uniform(2000, 8000)
        }
    
    def calculate_color_ratios(self, spectrum):
        if not spectrum:
            return {}
        blue = spectrum.get('blue', 0) + spectrum.get('indigo', 0)
        green = spectrum.get('green', 0) + spectrum.get('cyan', 0)
        red = spectrum.get('red', 0) + spectrum.get('orange', 0) + spectrum.get('yellow', 0)
        total = blue + green + red
        if total == 0:
            return {}
        return {
            'blue_percent': (blue/total) * 100,
            'green_percent': (green/total) * 100, 
            'red_percent': (red/total) * 100
        }
    
    def calculate_par_weight(self, spectrum):
        return sum(spectrum.values()) * 0.7  # Mock PAR calculation


# Use mock if hardware not available
if not _HAS_SPECTRAL:
    AS7341Spectral = MockAS7341
    TCS34725Color = MockAS7341