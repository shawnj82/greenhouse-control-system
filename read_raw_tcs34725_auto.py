#!/usr/bin/env python3
"""Direct read of TCS34725 lux with auto-adjustment to avoid saturation."""

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

# Your sensor configuration
SENSOR_BUS = 1
SENSOR_ADDR = 0x29
MUX_ADDR = 0x70
MUX_CHANNEL = 1

def select_mux_channel(bus_num, mux_addr, channel):
    """Select a channel on the PCA9548A I2C mux."""
    try:
        with SMBus(bus_num) as bus:
            bus.write_byte(mux_addr, 1 << channel)
        time.sleep(0.1)
    except Exception as e:
        print(f"Failed to select mux channel: {e}")

def read_with_auto_adjust(sensor):
    """Read lux with automatic adjustment to avoid saturation."""
    
    # Available settings (from lowest to highest sensitivity)
    integration_times = [2.4, 24, 50, 101, 154, 240]  # ms
    gains = [1, 4, 16, 60]  # multipliers
    
    # Start from lowest sensitivity (shortest time, lowest gain)
    it_idx = 0
    gain_idx = 0
    
    print("\nAuto-adjusting sensor settings to avoid saturation...\n")
    
    max_attempts = 20
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        
        # Apply current settings
        sensor.integration_time = integration_times[it_idx]
        sensor.gain = gains[gain_idx]
        
        # Wait for sensor to settle
        time.sleep(0.3)
        
        # Read values
        r, g, b, c = sensor.color_raw
        lux = sensor.lux
        
        print(f"Attempt {attempt}: IT={integration_times[it_idx]}ms, Gain={gains[gain_idx]}x")
        print(f"  → RGBC: {r}, {g}, {b}, {c}")
        
        # Check saturation threshold
        ATIME = 256 - int(integration_times[it_idx] / 2.4)
        saturation = 65535 if ATIME > 63 else 1024 * ATIME
        
        if c >= saturation * 0.95:  # 95% of saturation
            print(f"  → SATURATED (clear={c} >= {saturation*0.95:.0f})")
            
            # Try to reduce sensitivity
            if gain_idx > 0:
                gain_idx -= 1
                print(f"  → Reducing gain to {gains[gain_idx]}x\n")
            elif it_idx > 0:
                it_idx -= 1
                print(f"  → Reducing integration time to {integration_times[it_idx]}ms\n")
            else:
                print("  → Already at minimum settings, cannot reduce further!")
                print(f"  → Lux result: {lux}\n")
                return lux, r, g, b, c, integration_times[it_idx], gains[gain_idx]
        else:
            # Not saturated - we have a valid reading
            print(f"  → Valid reading! Lux = {lux}")
            print()
            return lux, r, g, b, c, integration_times[it_idx], gains[gain_idx]
    
    print("Maximum attempts reached!")
    return None, r, g, b, c, integration_times[it_idx], gains[gain_idx]

def main():
    print("=" * 70)
    print("Direct TCS34725 Lux Reading with Auto-Adjustment")
    print("=" * 70)
    
    # Select the mux channel
    print(f"\nSelecting I2C mux channel {MUX_CHANNEL}...")
    select_mux_channel(SENSOR_BUS, MUX_ADDR, MUX_CHANNEL)
    
    # Initialize sensor
    print(f"Initializing TCS34725 at address 0x{SENSOR_ADDR:02x}...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_tcs34725.TCS34725(i2c, address=SENSOR_ADDR)
    except Exception as e:
        print(f"Failed to initialize sensor: {e}")
        sys.exit(1)
    
    # Auto-adjust and read
    lux, r, g, b, c, it, gain = read_with_auto_adjust(sensor)
    
    # Display final results
    print("=" * 70)
    print("FINAL RESULTS from Adafruit TCS34725 Library (DN40 Algorithm)")
    print("=" * 70)
    print(f"\nSensor Settings:")
    print(f"  Integration Time: {it} ms")
    print(f"  Gain: {gain}x")
    print(f"\nRaw RGBC Values:")
    print(f"  Red:   {r:5d}")
    print(f"  Green: {g:5d}")
    print(f"  Blue:  {b:5d}")
    print(f"  Clear: {c:5d}")
    print(f"\nLux Measurement:")
    if lux is None:
        print(f"  RAW Lux: None (saturated even at minimum settings)")
    else:
        print(f"  RAW Lux from DN40: {lux:.2f} lux")
        print(f"\nWith 0.3545 calibration factor:")
        print(f"  Calibrated Lux: {lux * 0.3545:.2f} lux")
    
    # Read color temperature too
    color_temp = sensor.color_temperature
    if color_temp is not None:
        print(f"\nColor Temperature: {color_temp:.0f} K")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
