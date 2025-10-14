#!/usr/bin/env python3
"""
Quick sanity checks for dynamic gain/integration logic without hardware.
Uses a mock sensor to simulate clear channel values and verifies settings behavior.
"""
from sensors.spectral_sensors import TCS34725Color

class MockTCS:
    def __init__(self, clear_sequence):
        self.sequence = list(clear_sequence)
        self.idx = 0
        self.integration_time = 240
        self.gain = 16
        self.interrupt = False
    @property
    def color_raw(self):
        if self.idx < len(self.sequence):
            c = self.sequence[self.idx]
        else:
            c = self.sequence[-1]
        self.idx += 1
        # r,g,b just placeholders
        return (1000, 1000, 1000, c)
    @property
    def color_temperature(self):
        return 5000
    @property
    def lux(self):
        return 100.0


def check_hold_at_max():
    # Low signal while already at maximum settings
    sensor = TCS34725Color()
    sensor.sensor = MockTCS([1000, 1200])  # stay low
    sensor._last_gain_idx = len(sensor._gains) - 1
    sensor._last_integration_idx = len(sensor._integration_times) - 1
    d1 = sensor.read_color()
    d2 = sensor.read_color()
    assert sensor._last_gain_idx == len(sensor._gains) - 1, "Gain should hold at max"
    assert sensor._last_integration_idx == len(sensor._integration_times) - 1, "IT should hold at max"
    assert d1['gain'] == sensor._gains[-1] and d2['gain'] == sensor._gains[-1]
    assert d1['integration_time_ms'] == sensor._integration_times[-1] and d2['integration_time_ms'] == sensor._integration_times[-1]
    return "hold_at_max: OK"


def check_hold_at_min():
    # Clipping while already at minimum settings
    sensor = TCS34725Color()
    sensor.sensor = MockTCS([65535, 65000])  # near/max clip
    sensor._last_gain_idx = 0
    sensor._last_integration_idx = 0
    d1 = sensor.read_color()
    d2 = sensor.read_color()
    assert sensor._last_gain_idx == 0, "Gain should hold at min"
    assert sensor._last_integration_idx == 0, "IT should hold at min"
    assert d1['gain'] == sensor._gains[0] and d2['gain'] == sensor._gains[0]
    assert d1['integration_time_ms'] == sensor._integration_times[0] and d2['integration_time_ms'] == sensor._integration_times[0]
    return "hold_at_min: OK"


def check_step_down_from_clip():
    # Clipping with high settings should step down gain first
    sensor = TCS34725Color()
    sensor.sensor = MockTCS([65000])
    # Start at gain index 2 (16x) and IT index 5 (240ms)
    sensor._last_gain_idx = 2
    sensor._last_integration_idx = 5
    d = sensor.read_color()
    assert sensor._last_gain_idx == 1, "Gain should step down by one"
    assert sensor._last_integration_idx == 5, "IT should be unchanged when gain can step"
    return "step_down_from_clip: OK"


def check_step_up_from_low():
    # Low signal with low settings should step up gain first
    sensor = TCS34725Color()
    sensor.sensor = MockTCS([1000])
    sensor._last_gain_idx = 0
    sensor._last_integration_idx = 0
    d = sensor.read_color()
    assert sensor._last_integration_idx == 1, "Integration time should step up by one"
    assert sensor._last_gain_idx == 0, "Gain should remain until integration increments are exhausted"
    return "step_up_from_low: OK"


if __name__ == "__main__":
    results = []
    for fn in [check_hold_at_max, check_hold_at_min, check_step_down_from_clip, check_step_up_from_low]:
        try:
            results.append(fn())
        except AssertionError as e:
            print(f"FAIL: {fn.__name__}: {e}")
            raise
    print("\n".join(results))
    print("All dynamic gain checks passed.")
