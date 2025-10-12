# TSL2591 Light Sensor Driver with enhanced capabilities
# Supports both basic lux and infrared/full spectrum measurements for color analysis

import time

try:
    import board
    import busio
    import adafruit_tsl2591
    _HAS_TSL2591 = True
except ImportError:
    _HAS_TSL2591 = False

try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except ImportError:
    _HAS_SMBUS = False


class TSL2591:
    DEFAULT_ADDR = 0x29
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus = bus
        self.addr = addr
        self.sensor = None
        self._initialize()

    def _initialize(self):
        """Initialize the TSL2591 sensor."""
        if not _HAS_TSL2591:
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_tsl2591.TSL2591(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize TSL2591 at 0x{self.addr:02x}: {e}")
            self.sensor = None

    def read_lux(self):
        """Read basic lux value for compatibility."""
        if not self.sensor:
            # Mock value for development; replace with real sensor reading
            return 1234.0
        
        try:
            return float(self.sensor.lux) if self.sensor.lux is not None else None
        except Exception:
            return None

    def read_full_spectrum(self):
        """Read full spectrum data including infrared."""
        if not self.sensor:
            # Mock data for development
            return {
                'lux': 1234.0,
                'infrared': 567.0,
                'visible': 890.0,
                'full_spectrum': 1457.0
            }
        
        try:
            return {
                'lux': float(self.sensor.lux) if self.sensor.lux is not None else None,
                'infrared': float(self.sensor.infrared) if self.sensor.infrared is not None else None,
                'visible': float(self.sensor.visible) if self.sensor.visible is not None else None,
                'full_spectrum': float(self.sensor.full_spectrum) if self.sensor.full_spectrum is not None else None
            }
        except Exception as e:
            print(f"Error reading TSL2591 full spectrum: {e}")
            return None

    def calculate_color_metrics(self, spectrum_data=None):
        """Calculate basic color metrics from spectrum data."""
        if spectrum_data is None:
            spectrum_data = self.read_full_spectrum()
        
        if not spectrum_data or not all(v is not None for v in spectrum_data.values()):
            return None
        
        infrared = spectrum_data['infrared']
        visible = spectrum_data['visible']
        full_spectrum = spectrum_data['full_spectrum']
        
        if full_spectrum == 0:
            return None
        
        # Calculate basic color ratios
        # Visible light represents primarily blue-green spectrum
        # Infrared represents red and far-red
        # This is a simplified approximation
        
        visible_ratio = visible / full_spectrum if full_spectrum > 0 else 0
        ir_ratio = infrared / full_spectrum if full_spectrum > 0 else 0
        
        # Estimate color temperature (simplified)
        # Higher visible/IR ratio typically means cooler (bluer) light
        if ir_ratio > 0:
            color_temp_estimate = 2700 + (visible_ratio / ir_ratio) * 3000  # Rough estimate
            color_temp_estimate = min(6500, max(2700, color_temp_estimate))
        else:
            color_temp_estimate = 6500  # Default to daylight
        
        return {
            'visible_ratio': visible_ratio * 100,  # Percentage
            'infrared_ratio': ir_ratio * 100,     # Percentage
            'estimated_color_temp': color_temp_estimate,
            'spectrum_balance': 'cool' if visible_ratio > ir_ratio else 'warm',
            'intensity_lux': spectrum_data['lux']
        }

    def get_sensor_capabilities(self):
        """Return the capabilities of this sensor."""
        return {
            'type': 'TSL2591',
            'measures_intensity': True,
            'measures_color': 'basic',  # Basic visible/IR separation
            'spectral_channels': ['visible', 'infrared'],
            'color_temperature': 'estimated',
            'par_sensitive': True,  # Good for plant applications
            'dynamic_range': 'high'
        }
