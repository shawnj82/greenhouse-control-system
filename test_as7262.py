#!/usr/bin/env python3
"""
Test script for the AS7262 spectral sensor implementation.
"""

import time
import argparse
from sensors.as7262 import AS7262Sensor
from rich.console import Console
from rich.table import Table
from pathlib import Path
import json

def test_basic_readings(sensor):
    """Test basic sensor readings and print results."""
    console = Console()
    
    # Create results table
    table = Table(title="AS7262 Spectral Readings")
    table.add_column("Channel", style="cyan")
    table.add_column("Wavelength (nm)", style="green")
    table.add_column("Value", style="magenta")
    
    # Take reading
    spectrum = sensor.read_spectrum()
    if not spectrum:
        console.print("[red]Error getting sensor readings[/red]")
        return False
        
    # Add rows to table
    channels = ['violet', 'blue', 'green', 'yellow', 'orange', 'red']
    for channel, wavelength, value in zip(channels, 
                                        spectrum['wavelengths'],
                                        spectrum['intensities']):
        table.add_row(
            channel.capitalize(),
            str(wavelength),
            f"{value:.2f}"
        )
    
    console.print(table)
    console.print(f"\nSensor Temperature: {sensor.get_temperature():.1f}°C")
    return True

def monitor_mode(sensor, update_interval=1.0):
    """Continuously monitor and display sensor readings."""
    console = Console()
    console.print("[yellow]Starting continuous monitoring (Ctrl+C to stop)...[/yellow]")
    
    try:
        while True:
            console.clear()
            test_basic_readings(sensor)
            time.sleep(update_interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")

def save_calibration_data(sensor, output_file):
    """Take multiple readings and save calibration data."""
    console = Console()
    readings = []
    
    console.print("[yellow]Taking calibration readings...[/yellow]")
    
    # Take 10 readings with a short delay between each
    for i in range(10):
        spectrum = sensor.read_spectrum()
        if spectrum:
            readings.append(spectrum)
            console.print(f"Reading {i+1}/10 complete")
            time.sleep(0.5)
    
    # Calculate averages
    avg_spectrum = {
        'wavelengths': readings[0]['wavelengths'],
        'intensities': [0] * len(readings[0]['intensities']),
        'timestamp': time.time()
    }
    
    for reading in readings:
        for i, value in enumerate(reading['intensities']):
            avg_spectrum['intensities'][i] += value / len(readings)
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(avg_spectrum, f, indent=2)
    
    console.print(f"[green]Calibration data saved to {output_file}[/green]")

def main():
    parser = argparse.ArgumentParser(description='Test AS7262 spectral sensor')
    parser.add_argument('--monitor', action='store_true',
                       help='Continuously monitor sensor readings')
    parser.add_argument('--interval', type=float, default=1.0,
                       help='Update interval for monitor mode (seconds)')
    parser.add_argument('--calibrate', action='store_true',
                       help='Take calibration readings and save to file')
    parser.add_argument('--mux-addr', type=lambda x: int(x, 0), default=None,
                       help='I2C mux address (e.g., 0x70)')
    parser.add_argument('--mux-channel', type=int, default=None,
                       help='I2C mux channel (0-7). Example: 2')
    parser.add_argument('--mock', action='store_true',
                       help='Use mock mode (no hardware required)')
    args = parser.parse_args()
    
    try:
        sensor = AS7262Sensor(
            mux_address=args.mux_addr,
            mux_channel=args.mux_channel,
            mock_mode=args.mock
        )
        
        if args.monitor:
            monitor_mode(sensor, args.interval)
        elif args.calibrate:
            output_file = Path('data/as7262_calibration.json')
            output_file.parent.mkdir(exist_ok=True)
            save_calibration_data(sensor, output_file)
        else:
            test_basic_readings(sensor)
            
    except Exception as e:
        console = Console()
        console.print(f"[red]Error: {str(e)}[/red]")
        return 1
        
    return 0

if __name__ == '__main__':
    exit(main())