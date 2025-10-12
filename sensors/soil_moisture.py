"""Soil moisture sensor wrapper.

Assumes an analog moisture sensor connected via an ADC like MCP3008.
This file provides a simple interface and a mock fallback when ADC libs are missing.
"""

try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except Exception:
    _HAS_SMBUS = False


class SoilMoisture:
    def __init__(self, adc_channel=0):
        self.adc_channel = adc_channel

    def read_raw(self):
        """Return raw ADC value (0-1023) or None if unavailable."""
        if not _HAS_SMBUS:
            return None
        # Placeholder for real ADC reading using MCP3008 or similar
        # Users should replace with their ADC code.
        return None

    def moisture_percent(self):
        """Convert raw reading to percentage (0-100). Returns None if raw not available."""
        raw = self.read_raw()
        if raw is None:
            return None
        # Assuming 0 -> dry, 1023 -> wet
        try:
            return max(0, min(100, (raw / 1023.0) * 100.0))
        except Exception:
            return None