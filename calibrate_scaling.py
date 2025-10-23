#!/usr/bin/env python3
"""
Interactive scaling factor calibration for light sensors.

This script helps you calibrate the scaling factor by comparing the
sensor's lux reading with the calculated PPFD at the sensor location.
"""

import json
import time

DATA_DIR = "data"
SENSORS_FILE = f"{DATA_DIR}/light_sensors.json"
READINGS_FILE = f"{DATA_DIR}/sensor_readings.json"
ZONES_FILE = f"{DATA_DIR}/zone_light_metrics.json"

# Typical lux-to-PPFD conversion for white LEDs
LUX_TO_PPFD = 0.0185  # μmol/m²/s per lux

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_current_readings():
    """Get current sensor and zone readings."""
    readings = load_json(READINGS_FILE)
    zones = load_json(ZONES_FILE)
    
    # Assuming single sensor for now
    sensor_id = list(readings['readings'].keys())[0]
    sensor_data = readings['readings'][sensor_id]['raw_color_data']
    
    # Get sensor's zone
    sensors_config = load_json(SENSORS_FILE)
    zone_key = sensors_config['sensors'][sensor_id]['zone_key']
    
    return sensor_data, zones['zones'][zone_key], sensor_id, zone_key

def calculate_optimal_scaling(sensor_lux, calculated_ppfd, current_scaling):
    """Calculate optimal scaling factor based on lux."""
    expected_ppfd = sensor_lux * LUX_TO_PPFD
    if calculated_ppfd == 0:
        return current_scaling
    return (expected_ppfd / calculated_ppfd) * current_scaling

def main():
    print("=" * 60)
    print("Light Sensor Scaling Factor Calibration")
    print("=" * 60)
    print()
    
    # Load current configuration
    sensors_config = load_json(SENSORS_FILE)
    sensor_id = list(sensors_config['sensors'].keys())[0]
    sensor_cfg = sensors_config['sensors'][sensor_id]
    current_scaling = sensor_cfg.get('scaling_factor', 1.0)
    
    print(f"Sensor: {sensor_cfg['name']} at zone {sensor_cfg['zone_key']}")
    print(f"Current scaling factor: {current_scaling}")
    print()
    
    # Get current readings
    sensor_data, zone_data, sensor_id, zone_key = get_current_readings()
    
    print("Current Readings:")
    print(f"  Sensor lux: {sensor_data['lux']:.2f}")
    print(f"  Sensor gain: {sensor_data['gain']}x")
    print(f"  Integration time: {sensor_data['integration_time_ms']} ms")
    print()
    
    # Calculate expected vs actual
    expected_ppfd = sensor_data['lux'] * LUX_TO_PPFD
    calculated_ppfd = zone_data['ppfd']
    
    print("PPFD Comparison:")
    print(f"  Expected (from lux × {LUX_TO_PPFD}): {expected_ppfd:.2f} μmol/m²/s")
    print(f"  Calculated (from spectral bins): {calculated_ppfd:.2f} μmol/m²/s")
    print(f"  Difference: {abs(expected_ppfd - calculated_ppfd):.2f} μmol/m²/s")
    print()
    
    # Calculate optimal scaling
    if calculated_ppfd > 0:
        optimal_scaling = calculate_optimal_scaling(sensor_data['lux'], calculated_ppfd, current_scaling)
        print(f"Recommended scaling factor: {optimal_scaling:.4f}")
        print()
        
        # Ask if user wants to apply
        response = input("Apply this scaling factor? (y/n): ").strip().lower()
        if response == 'y':
            sensor_cfg['scaling_factor'] = round(optimal_scaling, 4)
            save_json(SENSORS_FILE, sensors_config)
            print(f"✓ Updated scaling factor to {optimal_scaling:.4f}")
            print("  Please restart the scheduler: sudo systemctl restart greenhouse-scheduler.service")
        else:
            print("  No changes made.")
    else:
        print("⚠️  Calculated PPFD is 0, cannot calibrate.")
        print("   Make sure lights are on and sensor is reading.")
    
    print()
    print("Calibration complete!")

if __name__ == "__main__":
    main()
