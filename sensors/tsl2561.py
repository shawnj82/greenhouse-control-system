"""TSL2561 light sensor wrapper with graceful fallback."""
import time
try:
    import board  # type: ignore
    import busio  # type: ignore
    import adafruit_tsl2561  # type: ignore
    _HAS_TSL = True
except Exception:
    _HAS_TSL = False


class TSL2561:
    DEFAULT_ADDR = 0x39

    def __init__(self, bus=1, addr=DEFAULT_ADDR, mux_address=None, mux_channel=None):
        self.bus_num = bus
        self.addr = addr
        self.mux_address = mux_address
        self.mux_channel = mux_channel

    def _select_mux(self):
        if self.mux_address is not None and self.mux_channel is not None:
            try:
                from sensors.pca9548a import PCA9548A
                mux = PCA9548A(bus=self.bus_num, address=self.mux_address)
                mux.select_channel(self.mux_channel)
                time.sleep(0.05)
            except Exception as e:
                print(f"[TSL2561] Failed to select mux channel {self.mux_channel} at 0x{self.mux_address:02x}: {e}")

    def read_lux(self):
        self._select_mux()
        if not _HAS_TSL:
            return None
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_tsl2561.TSL2561(i2c, address=self.addr)
            return float(sensor.lux) if sensor.lux is not None else None
        except Exception:
            return None
