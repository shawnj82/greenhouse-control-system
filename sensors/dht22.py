"""DHT22 sensor wrapper with fallback for non-Raspberry Pi environments.

Provides read() -> dict with keys: temperature_c, humidity
"""

import time

try:
    import Adafruit_DHT
    _HAS_ADAFRUIT = True
except Exception:
    _HAS_ADAFRUIT = False


class DHT22:
    def __init__(self, pin=4):
        """pin: GPIO pin number (BCM)
        """
        self.pin = pin
        self.sensor = Adafruit_DHT.DHT22 if _HAS_ADAFRUIT else None

    def read(self):
        """Return a dict: { 'temperature_c': float or None, 'humidity': float or None }
        """
        if not _HAS_ADAFRUIT:
            # Fallback: return dummy values and timestamp
            return {"temperature_c": None, "humidity": None, "note": "Adafruit_DHT not available"}

        humidity, temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
        return {"temperature_c": temperature, "humidity": humidity}