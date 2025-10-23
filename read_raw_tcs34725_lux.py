#!/usr/bin/env python3
"""Direct read of TCS34725 lux from Adafruit library - no application logic."""

import sys
import time

try:
    import board
    import busio
    import adafruit_tcs34725
    from smbus2 import SMBus
except ImportError as e:
    print(f"Missing required library: {e}")
    sys.exit(1)

# Your sensor configuration (from light_sensors.json)
SENSOR_BUS = 1
SENSOR_ADDR = 0x29  # TCS34725 default address
MUX_ADDR = 0x70     # PCA9548A mux address
MUX_CHANNEL = 1     # Your TCS34725 is on channel 1

def select_mux_channel(bus_num, mux_addr, channel):
    """Select a channel on the PCA9548A I2C mux."""
    try:
        with SMBus(bus_num) as bus:
            # Write channel bitmask to mux
            bus.write_byte(mux_addr, 1 << channel)
        print(f"Selected mux channel {channel}")
        time.sleep(0.1)  # Let mux settle
    except Exception as e:
        print(f"Failed to select mux channel: {e}")

def main():
    print("=" * 60)
    print("Direct TCS34725 Lux Reading from Adafruit Library")
    print("=" * 60)
    
    # Select the mux channel
    print(f"\n1. Selecting I2C mux channel {MUX_CHANNEL}...")
    select_mux_channel(SENSOR_BUS, MUX_ADDR, MUX_CHANNEL)
    
    # Initialize I2C and sensor
    print(f"\n2. Initializing TCS34725 at address 0x{SENSOR_ADDR:02x}...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_tcs34725.TCS34725(i2c, address=SENSOR_ADDR)
    except Exception as e:
        print(f"Failed to initialize sensor: {e}")
        sys.exit(1)
    
    # Configure sensor
    print("\n3. Configuring sensor settings...")
    sensor.integration_time = 240  # 240ms
    sensor.gain = 16              # 16x gain
    print(f"   - Integration time: {sensor.integration_time} ms")
    print(f"   - Gain: {sensor.gain}x")
    
    # Wait for sensor to stabilize
    print("\n4. Waiting for sensor to stabilize...")
    time.sleep(0.3)
    
    # Read raw RGBC values
    print("\n5. Reading raw RGBC values...")
    r, g, b, c = sensor.color_raw
    print(f"   - Red:   {r}")
    print(f"   - Green: {g}")
    print(f"   - Blue:  {b}")
    print(f"   - Clear: {c}")
    
    # Read lux directly from library
    print("\n6. Reading LUX from Adafruit library (DN40 algorithm)...")
    lux = sensor.lux
    
    print("\n" + "=" * 60)
    if lux is None:
        print("RESULT: lux = None (sensor saturated or invalid)")
        print("\nThe DN40 algorithm returned None, which typically means:")
        print("  - Clear channel >= saturation threshold")
        print("  - Integration time/gain combination too high for light level")
    else:
        print(f"RESULT: lux = {lux:.2f}")
        print(f"\nThis is the RAW output from the Adafruit TCS34725 driver")
        print(f"using the DN40 algorithm (no application calibration applied)")
    print("=" * 60)
    
    # Also read color temperature
    color_temp = sensor.color_temperature
    if color_temp is not None:
        print(f"\nBonus - Color Temperature: {color_temp:.0f} K")
    
    # Show what our calibration would do
    if lux is not None:
        calibrated_lux = lux * 0.3545
        print(f"\nWith 0.3545 calibration factor: {calibrated_lux:.2f} lux")

if __name__ == "__main__":
    main()
