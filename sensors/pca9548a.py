# PCA9548A I2C multiplexer helper
from smbus2 import SMBus

class PCA9548A:
    def __init__(self, bus=1, address=0x70):
        self.bus = bus
        self.address = address

    def select_channel(self, channel):
        """Select the given channel (0-7) on the mux."""
        if not (0 <= channel <= 7):
            raise ValueError("Channel must be 0-7")
        with SMBus(self.bus) as bus:
            bus.write_byte(self.address, 1 << channel)
