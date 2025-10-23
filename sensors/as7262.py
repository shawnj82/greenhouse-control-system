"""
AS7262 Visible Light Spectral Sensor driver implementation.
The AS7262 provides spectral response detection in 6 wavelength bands:
- 450nm (Violet)
- 500nm (Blue)
- 550nm (Green)
- 570nm (Yellow)
- 600nm (Orange)
- 650nm (Red)
"""

import time
import random
from logging import getLogger

logger = getLogger(__name__)


class AS7262Sensor:
    """Interface for the AS7262 6-channel visible light spectral sensor.

    Supports optional I2C mux selection (PCA9548A/TCA9548A style) via smbus2 helper.
    """

    def __init__(self, i2c_bus=None, address=0x49, mux_address=None, mux_channel=None, mock_mode=False):
        """Initialize the AS7262 sensor.

        Args:
            i2c_bus: Optional existing I2C bus instance. If None, will create new one.
            address: I2C address of the sensor (default 0x49)
            mux_address: Optional I2C address of the multiplexer (e.g., 0x70)
            mux_channel: Optional multiplexer channel to select (0-7)
            mock_mode: If True, generate synthetic readings (no hardware required)
        """
        self._mock_mode = mock_mode
        self._mux_address = mux_address
        self._mux_channel = mux_channel

        if self._mock_mode:
            logger.info("AS7262: Initializing in mock mode")
            self._mock_temp = 25.0
            self.sensor = None
            return

        try:
            # If using a multiplexer, select the desired channel first via smbus2 helper
            if (self._mux_address is not None) and (self._mux_channel is not None):
                try:
                    from sensors.pca9548a import PCA9548A
                    logger.info(f"AS7262: Selecting mux 0x{self._mux_address:02x} channel {self._mux_channel}")
                    mux = PCA9548A(bus=1, address=self._mux_address)
                    # Directly select our channel; give hardware a bit of time to settle
                    mux.select_channel(self._mux_channel)
                    time.sleep(0.2)
                except Exception as e:
                    logger.error(f"AS7262: Failed to select mux channel: {e}")
                    raise

            # Import hardware-specific modules only when needed
            import board
            import busio
            import adafruit_as726x  # Supports AS7262/AS7263

            if i2c_bus is None:
                i2c_bus = busio.I2C(board.SCL, board.SDA)

            # Create I2C-backed sensor instance
            self.sensor = adafruit_as726x.AS726x_I2C(i2c_bus, address=address)
            # Configure sensible defaults (MODE_2: continuous reads)
            self.sensor.conversion_mode = adafruit_as726x.AS726x.MODE_2
            # Gain expects one of [1, 3.7, 16, 64]
            self.sensor.gain = 64
            # Integration time units are 2.8ms steps (0-255). 200 ~ 560ms.
            self.sensor.integration_time = 200

            logger.info("AS7262: Sensor initialized successfully")

        except Exception as e:
            logger.error(f"AS7262: Failed to initialize sensor: {str(e)}")
            raise
    
    def read_calibrated_values(self):
        """Read calibrated values from all channels.
        
        Returns:
            dict: Calibrated values for each wavelength channel (450-650nm)
        """
        if self._mock_mode:
            # Generate realistic mock values
            base = random.uniform(1000, 2000)
            noise = lambda: random.uniform(0.8, 1.2)
            return {
                'violet': base * 0.6 * noise(),
                'blue': base * 0.8 * noise(),
                'green': base * 1.0 * noise(),
                'yellow': base * 0.9 * noise(),
                'orange': base * 0.7 * noise(),
                'red': base * 0.5 * noise()
            }
            
        # Try a few times in case of transient I2C errors
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                # Wait for data to be ready
                t0 = time.time()
                while not self.sensor.data_ready and (time.time() - t0) < 1.0:
                    time.sleep(0.05)

                raw_values = {
                    'violet': self.sensor.violet,
                    'blue': self.sensor.blue,
                    'green': self.sensor.green,
                    'yellow': self.sensor.yellow,
                    'orange': self.sensor.orange,
                    'red': self.sensor.red
                }
                
                # Hardware validation: AS7262 uses 16-bit ADC, calibrated values
                # should be in a reasonable range. Corrupt I2C reads can produce
                # impossibly large floats due to bit errors or library issues.
                # Max reasonable calibrated value is ~100k (bright sunlight).
                MAX_VALID = 100000.0
                validated = {}
                corruption_detected = False
                
                for channel, value in raw_values.items():
                    try:
                        fv = float(value)
                        # Check for NaN, Inf, negative, or impossibly large values
                        if fv < 0 or fv != fv or fv in (float('inf'), float('-inf')) or fv > MAX_VALID:
                            logger.warning(f"AS7262: Corrupt {channel} value {fv:.2e}, using 0")
                            validated[channel] = 0.0
                            corruption_detected = True
                        else:
                            validated[channel] = fv
                    except (ValueError, TypeError):
                        logger.warning(f"AS7262: Invalid {channel} value type, using 0")
                        validated[channel] = 0.0
                        corruption_detected = True
                
                # If corruption detected, retry unless we're on last attempt
                if corruption_detected and attempt < attempts:
                    logger.info(f"AS7262: Retrying read due to corruption (attempt {attempt}/{attempts})")
                    time.sleep(0.2)
                    continue
                    
                return validated
                
            except Exception as e:
                logger.error(f"Error reading from AS7262 (attempt {attempt}/{attempts}): {str(e)}")
                time.sleep(0.1)
        return None
    
    def read_spectrum(self):
        """Read and process the full spectrum data.
        
        Returns:
            dict: Processed spectral data with wavelengths and relative intensities
        """
        values = self.read_calibrated_values()
        if not values:
            return None
            
        return {
            'wavelengths': [450, 500, 550, 570, 600, 650],
            'intensities': [
                values['violet'],
                values['blue'],
                values['green'],
                values['yellow'],
                values['orange'],
                values['red']
            ],
            'raw_values': values
        }
        
    def set_gain(self, gain):
        """Set the sensor gain.
        
        Args:
            gain: One of the adafruit_as7262.GAIN_* constants
        """
        try:
            self.sensor.gain = gain
        except Exception as e:
            logger.error(f"Error setting AS7262 gain: {str(e)}")
    
    def set_integration_time(self, time_ms):
        """Set the sensor integration time in milliseconds (2.8-714ms).
        
        Args:
            time_ms: Integration time in milliseconds
        """
        try:
            # Convert ms to raw value (2.8ms * value)
            raw_value = min(255, max(0, int(time_ms / 2.8)))
            self.sensor.integration_time = raw_value
        except Exception as e:
            logger.error(f"Error setting AS7262 integration time: {str(e)}")
            
    def get_temperature(self):
        """Read the sensor temperature.
        
        Returns:
            float: Temperature in Celsius
        """
        if self._mock_mode:
            # Simulate temperature variations
            self._mock_temp += random.uniform(-0.1, 0.1)
            return self._mock_temp
            
        try:
            return self.sensor.temperature
        except Exception as e:
            logger.error(f"Error reading AS7262 temperature: {str(e)}")
            return None