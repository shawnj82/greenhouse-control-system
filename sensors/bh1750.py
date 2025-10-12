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

    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr

    def read_lux(self):
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