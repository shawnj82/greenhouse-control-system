#!/usr/bin/env python3
"""I2C Scanner utility to check device connections."""

import time
try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except ImportError:
    _HAS_SMBUS = False

class I2CScanner:
    def scan_bus(self, bus_number=1):
        """Scan I2C bus for devices."""
        if not _HAS_SMBUS:
            print("smbus2 module not available. Please install with: pip install smbus2")
            return []
            
        print(f"\nScanning I2C bus {bus_number}...")
        found_devices = []
        
        try:
            with SMBus(bus_number) as bus:
                for address in range(0x03, 0x77 + 1):
                    # Skip reserved addresses
                    if address in [0x00, 0x01, 0x02, 0x7b, 0x7c, 0x7d, 0x7e, 0x7f]:
                        continue
                        
                    try:
                        bus.read_byte(address)
                        found_devices.append(address)
                        print(f"Found device at address: 0x{address:02x} ({address})")
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Error accessing I2C bus {bus_number}: {e}")
            return []
            
        if not found_devices:
            print("No I2C devices found")
        else:
            print(f"\nFound {len(found_devices)} device(s):")
            for addr in found_devices:
                print(f"  0x{addr:02x} ({addr})")
                
        return found_devices

    def scan_mux_channels(self, bus_number=1, mux_address=0x70):
        """Scan all channels of a TCA9548A multiplexer for devices."""
        if not _HAS_SMBUS:
            print("smbus2 module not available")
            return {}
            
        print(f"\nScanning TCA9548A multiplexer at address 0x{mux_address:02x}")
        channel_devices = {}
        
        try:
            with SMBus(bus_number) as bus:
                # First verify the multiplexer is present
                try:
                    bus.read_byte(mux_address)
                    print("Multiplexer found!")
                except Exception as e:
                    print(f"Error: Multiplexer not found at 0x{mux_address:02x}")
                    return channel_devices

                # Scan each channel
                for channel in range(8):  # TCA9548A has 8 channels
                    print(f"\nScanning channel {channel}...")
                    
                    # Select channel
                    try:
                        bus.write_byte(mux_address, 1 << channel)
                        time.sleep(0.1)  # Give devices time to settle
                    except Exception as e:
                        print(f"Error selecting channel {channel}: {e}")
                        continue

                    # Scan for devices on this channel
                    devices = []
                    for address in range(0x03, 0x77 + 1):
                        if address == mux_address:  # Skip mux address
                            continue
                        try:
                            bus.read_byte(address)
                            devices.append(address)
                            print(f"Found device at address: 0x{address:02x}")
                        except Exception:
                            pass

                    if devices:
                        channel_devices[channel] = devices
                        print(f"Channel {channel}: Found {len(devices)} device(s)")
                    else:
                        print(f"Channel {channel}: No devices found")

                # Reset multiplexer
                bus.write_byte(mux_address, 0x00)
                
        except Exception as e:
            print(f"Error during multiplexer scan: {e}")
            
        return channel_devices

if __name__ == "__main__":
    scanner = I2CScanner()
    print("Scanning main I2C bus...")
    scanner.scan_bus(1)
    print("\nScanning multiplexer channels...")
    scanner.scan_mux_channels(1, 0x70)  # Default mux address is 0x70