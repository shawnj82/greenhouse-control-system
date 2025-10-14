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
        # Adaptive settings
        self._gains = [adafruit_tsl2591.GAIN_LOW, adafruit_tsl2591.GAIN_MED, adafruit_tsl2591.GAIN_HIGH, adafruit_tsl2591.GAIN_MAX]
        self._integration_times = [adafruit_tsl2591.INTEGRATIONTIME_100MS, adafruit_tsl2591.INTEGRATIONTIME_200MS, adafruit_tsl2591.INTEGRATIONTIME_300MS, adafruit_tsl2591.INTEGRATIONTIME_400MS, adafruit_tsl2591.INTEGRATIONTIME_500MS, adafruit_tsl2591.INTEGRATIONTIME_600MS]
        self._last_gain_idx = 0  # Start with lowest gain
        self._last_integration_idx = 0  # Start with shortest integration
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
        """Read lux with adaptive gain/integration (stepwise)."""
        if not self.sensor:
            return 1234.0
        try:
            # Aim to keep measurement under ~80% of a conservative full-scale estimate
            max_lux = 88000  # Approximate upper bound for the device
            target_ratio = 0.80
            high_trigger = max_lux * 0.82  # step-down trigger
            min_lux = 1

            gain_idx = self._last_gain_idx
            int_idx = self._last_integration_idx

            # Apply current settings for this measurement
            self.sensor.gain = self._gains[gain_idx]
            self.sensor.integration_time = self._integration_times[int_idx]
            time.sleep(0.12)
            lux = float(self.sensor.lux) if self.sensor.lux is not None else None

            # Decide adjustments for NEXT read
            adjusted = False
            new_gain_idx = gain_idx
            new_int_idx = int_idx
            if lux is not None:
                if lux >= high_trigger:
                    # Too high, reduce gain first then integration
                    changed = False
                    if new_gain_idx > 0:
                        new_gain_idx -= 1
                        changed = True
                        print(f"[TSL2591] High signal ({lux:.1f} >= {high_trigger:.1f}): scheduling decrease gain to idx {new_gain_idx}")
                    elif new_int_idx > 0:
                        new_int_idx -= 1
                        changed = True
                        print(f"[TSL2591] High signal: scheduling decrease integration_time to idx {new_int_idx}")
                    else:
                        print("[TSL2591] High signal but already at minimum gain/time; holding settings")
                    adjusted = changed
                elif lux < min_lux:
                    # Too low, increase integration time first then gain
                    changed = False
                    if new_int_idx < len(self._integration_times) - 1:
                        new_int_idx += 1
                        changed = True
                        print(f"[TSL2591] Low signal ({lux:.1f} < {min_lux}): scheduling increase integration_time to idx {new_int_idx}")
                    elif new_gain_idx < len(self._gains) - 1:
                        new_gain_idx += 1
                        changed = True
                        print(f"[TSL2591] Low signal: scheduling increase gain to idx {new_gain_idx}")
                    else:
                        print("[TSL2591] Low signal but already at maximum gain/time; holding settings")
                    adjusted = changed

            # Apply scheduled changes after completing this read
            if adjusted:
                self._last_gain_idx = new_gain_idx
                self._last_integration_idx = new_int_idx
                self.sensor.gain = self._gains[new_gain_idx]
                self.sensor.integration_time = self._integration_times[new_int_idx]
                print(f"[TSL2591] Adjustment scheduled for next read: gain idx={new_gain_idx}, integration idx={new_int_idx}")
            else:
                self._last_gain_idx = gain_idx
                self._last_integration_idx = int_idx

            return lux
        except Exception as e:
            print(f"Error reading TSL2591: {e}")
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
