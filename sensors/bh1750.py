"""BH1750 light sensor wrapper using smbus2 with fallback.

Provides read_lux() -> float or None
"""
import time

try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except Exception:
    _HAS_SMBUS = False


class BH1750:
    DEFAULT_ADDR = 0x23

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
                print(f"[BH1750] Failed to select mux channel {self.mux_channel} at 0x{self.mux_address:02x}: {e}")

    def read_lux(self):
        self._select_mux()
        if not _HAS_SMBUS:
            return None
        try:
            with SMBus(self.bus_num) as bus:
                # Power on
                bus.write_byte(self.addr, 0x01)
                # Continuously H-Resolution Mode
                bus.write_byte(self.addr, 0x10)
                time.sleep(0.18)
                data = bus.read_i2c_block_data(self.addr, 0x00, 2)
                raw = (data[0] << 8) | data[1]
                lux = raw / 1.2
                return lux
        except Exception:
            return None