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

    def __init__(self, bus=1, addr=DEFAULT_ADDR, mux_address=None, mux_channel=None):
        self.bus = bus
        self.addr = addr
        self.mux_address = mux_address
        self.mux_channel = mux_channel
        self.sensor = None
        if not _HAS_TSL2591:
            print("adafruit_tsl2591 library not available. TSL2591 sensor will not function.")
            self._gains = []
            self._integration_times = []
            self._last_gain_idx = 0
            self._last_integration_idx = 0
            return
        # Adaptive settings
        self._gains = [adafruit_tsl2591.GAIN_LOW, adafruit_tsl2591.GAIN_MED, adafruit_tsl2591.GAIN_HIGH, adafruit_tsl2591.GAIN_MAX]
        self._integration_times = [adafruit_tsl2591.INTEGRATIONTIME_100MS, adafruit_tsl2591.INTEGRATIONTIME_200MS, adafruit_tsl2591.INTEGRATIONTIME_300MS, adafruit_tsl2591.INTEGRATIONTIME_400MS, adafruit_tsl2591.INTEGRATIONTIME_500MS, adafruit_tsl2591.INTEGRATIONTIME_600MS]
        self._last_gain_idx = 0  # Start with lowest gain
        self._last_integration_idx = 0  # Start with shortest integration
        self._select_mux()
        self._initialize()

    def _select_mux(self):
        if self.mux_address is not None and self.mux_channel is not None:
            try:
                from sensors.pca9548a import PCA9548A
                mux = PCA9548A(bus=self.bus, address=self.mux_address)
                mux.select_channel(self.mux_channel)
                time.sleep(0.05)  # Allow mux to settle
            except Exception as e:
                print(f"[TSL2591] Failed to select mux channel {self.mux_channel} at 0x{self.mux_address:02x}: {e}")

    def _initialize(self):
        """Initialize the TSL2591 sensor."""
        if not _HAS_TSL2591:
            print("adafruit_tsl2591 library not available. Cannot initialize sensor.")
            self.sensor = None
            return
        try:
            self._select_mux()
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_tsl2591.TSL2591(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize TSL2591 at 0x{self.addr:02x}: {e}")
            self.sensor = None

    def read_lux(self):
        """Read lux with adaptive gain/integration (stepwise)."""
        self._select_mux()
        if not _HAS_TSL2591 or not self.sensor:
            print("TSL2591 sensor not initialized or library missing.")
            return None
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
        """Read full spectrum data including infrared with adaptive gain/integration."""
        self._select_mux()
        if not _HAS_TSL2591 or not self.sensor:
            # Mock data for development
            return {
                'lux': 1234.0,
                'infrared': 567.0,
                'visible': 890.0,
                'full_spectrum': 1457.0,
                'gain': 1.0,
                'integration_time_ms': 100
            }
        
        try:
            # Get current gain value (numeric multiplier)
            gain_map = {
                0: 1.0,    # GAIN_LOW
                16: 25.0,  # GAIN_MED
                32: 428.0, # GAIN_HIGH
                48: 9876.0 # GAIN_MAX
            }
            
            # Get current integration time in ms
            time_map = {
                0: 100,  # INTEGRATIONTIME_100MS
                1: 200,  # INTEGRATIONTIME_200MS
                2: 300,  # INTEGRATIONTIME_300MS
                3: 400,  # INTEGRATIONTIME_400MS
                4: 500,  # INTEGRATIONTIME_500MS
                5: 600   # INTEGRATIONTIME_600MS
            }
            
            # Apply current settings for this measurement
            gain_idx = self._last_gain_idx
            int_idx = self._last_integration_idx
            self.sensor.gain = self._gains[gain_idx]
            self.sensor.integration_time = self._integration_times[int_idx]
            time.sleep(0.12)
            
            # Try to read the sensor
            lux = float(self.sensor.lux) if self.sensor.lux is not None else None
            infrared = float(self.sensor.infrared) if self.sensor.infrared is not None else None
            visible = float(self.sensor.visible) if self.sensor.visible is not None else None
            full_spectrum = float(self.sensor.full_spectrum) if self.sensor.full_spectrum is not None else None
            
            gain_value = gain_map.get(self.sensor.gain, 1.0)
            integration_ms = time_map.get(self.sensor.integration_time, 100)
            
            # Check for overflow/saturation and adjust for NEXT read
            # TSL2591 has 16-bit ADCs, so max value is 65535
            SATURATION_THRESHOLD = 60000  # Conservative threshold
            max_lux = 88000  # Approximate upper bound
            high_trigger = max_lux * 0.82
            min_lux = 1
            
            adjusted = False
            new_gain_idx = gain_idx
            new_int_idx = int_idx
            
            # Check for saturation in any channel
            if full_spectrum is not None and full_spectrum >= SATURATION_THRESHOLD:
                # Saturated, reduce gain/integration for next read
                changed = False
                if new_gain_idx > 0:
                    new_gain_idx -= 1
                    changed = True
                    print(f"[TSL2591] Saturation detected (full_spectrum={full_spectrum:.0f}): scheduling decrease gain to idx {new_gain_idx}")
                elif new_int_idx > 0:
                    new_int_idx -= 1
                    changed = True
                    print(f"[TSL2591] Saturation detected: scheduling decrease integration_time to idx {new_int_idx}")
                else:
                    print("[TSL2591] Saturation detected but already at minimum gain/time; holding settings")
                adjusted = changed
            elif lux is not None:
                # Use lux-based adaptive logic
                if lux >= high_trigger:
                    changed = False
                    if new_gain_idx > 0:
                        new_gain_idx -= 1
                        changed = True
                        print(f"[TSL2591] High signal ({lux:.1f} >= {high_trigger:.1f}): scheduling decrease gain to idx {new_gain_idx}")
                    elif new_int_idx > 0:
                        new_int_idx -= 1
                        changed = True
                        print(f"[TSL2591] High signal: scheduling decrease integration_time to idx {new_int_idx}")
                    adjusted = changed
                elif lux < min_lux:
                    changed = False
                    if new_int_idx < len(self._integration_times) - 1:
                        new_int_idx += 1
                        changed = True
                        print(f"[TSL2591] Low signal ({lux:.1f} < {min_lux}): scheduling increase integration_time to idx {new_int_idx}")
                    elif new_gain_idx < len(self._gains) - 1:
                        new_gain_idx += 1
                        changed = True
                        print(f"[TSL2591] Low signal: scheduling increase gain to idx {new_gain_idx}")
                    adjusted = changed
            
            # Apply scheduled changes for next read
            if adjusted:
                self._last_gain_idx = new_gain_idx
                self._last_integration_idx = new_int_idx
                self.sensor.gain = self._gains[new_gain_idx]
                self.sensor.integration_time = self._integration_times[new_int_idx]
                print(f"[TSL2591] Adjustment scheduled for next read: gain idx={new_gain_idx}, integration idx={new_int_idx}")
            else:
                self._last_gain_idx = gain_idx
                self._last_integration_idx = int_idx
            
            return {
                'lux': lux,
                'infrared': infrared,
                'visible': visible,
                'full_spectrum': full_spectrum,
                'gain': gain_value,
                'integration_time_ms': integration_ms
            }
        except Exception as e:
            print(f"Error reading TSL2591 full spectrum: {e}")
            # On error, try to reduce gain/integration for next attempt
            if self._last_gain_idx > 0:
                self._last_gain_idx -= 1
                self.sensor.gain = self._gains[self._last_gain_idx]
                print(f"[TSL2591] Error occurred, reducing gain to idx {self._last_gain_idx} for next attempt")
            elif self._last_integration_idx > 0:
                self._last_integration_idx -= 1
                self.sensor.integration_time = self._integration_times[self._last_integration_idx]
                print(f"[TSL2591] Error occurred, reducing integration time to idx {self._last_integration_idx} for next attempt")
            return {
                'lux': None,
                'infrared': None,
                'visible': None,
                'full_spectrum': None,
                'gain': gain_map.get(self.sensor.gain, 1.0),
                'integration_time_ms': time_map.get(self.sensor.integration_time, 100)
            }

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
