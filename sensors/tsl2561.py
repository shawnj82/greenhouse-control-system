"""TSL2561 light sensor wrapper with graceful fallback."""
try:
    import board  # type: ignore
    import busio  # type: ignore
    import adafruit_tsl2561  # type: ignore
    _HAS_TSL = True
except Exception:
    _HAS_TSL = False


class TSL2561:
    DEFAULT_ADDR = 0x39
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr

    def read_lux(self):
        if not _HAS_TSL:
            return None
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_tsl2561.TSL2561(i2c, address=self.addr)
            return float(sensor.lux) if sensor.lux is not None else None
        except Exception:
            return None
