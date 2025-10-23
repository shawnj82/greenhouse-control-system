#!/usr/bin/env python3
"""
Practical utility for spectrum fusion with your actual TCS34725 + TSL2591 setup.
This shows how to read live sensor data and create spectrum histograms.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion
from sensor_shared import read_light_sensor
import json
import requests
import time


def load_sensor_config():
    """Load sensor configuration from your system."""
    try:
        config_file = "/home/shawn/greenhouse-control-system/data/light_sensors.json"
        with open(config_file, 'r') as f:
            return json.load(f).get("sensors", {})
    except Exception as e:
        print(f"Error loading sensor config: {e}")
        return {}


def read_live_sensors(sensor_ids):
    """Read live data from configured sensors."""
    config = load_sensor_config()
    readings = {}
    
    for sensor_id in sensor_ids:
        if sensor_id not in config:
            print(f"Sensor {sensor_id} not found in configuration")
            continue
            
        try:
            sensor_cfg = config[sensor_id]
            reading = read_light_sensor(sensor_cfg, sensor_id)
            readings[sensor_id] = reading
            print(f"✓ Read {sensor_id}: {reading.get('sensor_type', 'unknown')} - {reading.get('timestamp', 'no timestamp')}")
        except Exception as e:
            print(f"✗ Error reading {sensor_id}: {e}")
            readings[sensor_id] = {"error": str(e)}
    
    return readings


def fuse_and_display(sensor_data, positions, target_pos):
    """Perform fusion and display results."""
    try:
        # Convert to format expected by fusion algorithm
        sensors_list = []
        positions_list = []
        
        for (sensor_id, reading), pos in zip(sensor_data.items(), positions):
            if "error" in reading:
                print(f"Skipping {sensor_id} due to error: {reading['error']}")
                continue
            sensors_list.append(reading)
            positions_list.append(pos)
        
        if len(sensors_list) < 2:
            print("Need at least 2 working sensors for fusion")
            return
        
        # Perform fusion
        result = SpectralDataFusion.fuse_sensor_spectra(
            sensors_list, positions_list, target_pos
        )
        
        histogram = SpectralDataFusion.create_histogram_data(result)
        
        print(f"\n🎯 Fusion Results for position {target_pos}:")
        print(f"  Quality Score: {histogram.get('interpolation_quality', 0):.3f}")
        print(f"  Spectral bins: {len(histogram['wavelengths'])}")
        print(f"  Wavelength range: {min(histogram['wavelengths']):.0f}-{max(histogram['wavelengths']):.0f} nm")
        
        # Show top 5 spectral peaks
        if histogram['wavelengths'] and histogram['intensities']:
            # Sort by intensity
            sorted_data = sorted(zip(histogram['wavelengths'], histogram['intensities']), 
                               key=lambda x: x[1], reverse=True)
            
            print(f"\n📊 Top 5 Spectral Peaks:")
            for i, (wl, intensity) in enumerate(sorted_data[:5]):
                print(f"  {i+1}. {wl:.0f} nm: {intensity:.1f}")
        
        return result, histogram
        
    except Exception as e:
        print(f"Fusion error: {e}")
        return None, None


def test_api_fusion(sensor_ids, positions, target_pos):
    """Test the API-based fusion endpoint."""
    try:
        url = "http://localhost:5000/api/spectrum-fusion/live"
        payload = {
            "sensor_ids": sensor_ids,
            "positions": positions,
            "target_position": target_pos
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("\n🌐 API Fusion Results:")
                fusion_summary = result.get("fusion_summary", {})
                print(f"  Quality Score: {fusion_summary.get('quality_score', 0):.3f}")
                print(f"  Source Sensors: {', '.join(fusion_summary.get('source_sensors', []))}")
                print(f"  Spatial Weights: {fusion_summary.get('spatial_weights', [])}")
                
                histogram = result.get("histogram", {})
                if histogram.get('wavelengths'):
                    print(f"  Histogram bins: {len(histogram['wavelengths'])}")
                    print(f"  Peak wavelength: {histogram['wavelengths'][histogram['intensities'].index(max(histogram['intensities']))]} nm")
                
                return result
            else:
                print(f"API error: {result.get('error', 'Unknown error')}")
        else:
            print(f"HTTP error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("Web server not running - skipping API test")
    except Exception as e:
        print(f"API test error: {e}")
    
    return None


def main():
    print("🔬 Live Spectrum Fusion Utility")
    print("=" * 50)
    
    # Example configuration - adjust for your actual sensor setup
    sensor_ids = ["tcs34725_1", "tsl2591_1"]  # Replace with your actual sensor IDs
    positions = [(0, 0), (2, 0)]  # Positions in your grid
    target_pos = (1, 0)  # Where to estimate spectrum (midpoint)
    
    print(f"Target sensors: {sensor_ids}")
    print(f"Positions: {positions}")
    print(f"Estimation target: {target_pos}")
    print()
    
    # Check what sensors are actually configured
    config = load_sensor_config()
    print(f"Configured sensors: {list(config.keys())}")
    
    if not config:
        print("No sensors configured. Please check data/light_sensors.json")
        return
    
    # Adjust sensor IDs based on what's actually available
    available_sensors = [sid for sid in sensor_ids if sid in config]
    if len(available_sensors) < 2:
        # Try to find any two sensors for demo
        all_sensors = list(config.keys())
        if len(all_sensors) >= 2:
            available_sensors = all_sensors[:2]
            print(f"Using available sensors: {available_sensors}")
        else:
            print("Need at least 2 configured sensors for fusion demo")
            return
    
    # Read live sensor data
    print("\n📡 Reading Live Sensor Data...")
    sensor_data = read_live_sensors(available_sensors)
    
    # Show raw readings
    print("\n📋 Raw Sensor Readings:")
    for sensor_id, reading in sensor_data.items():
        if "error" not in reading:
            sensor_type = reading.get('sensor_type', 'Unknown')
            timestamp = reading.get('timestamp', 0)
            
            # Show relevant raw data based on sensor type
            if sensor_type == 'TCS34725':
                raw_data = reading.get('raw_color_data', {})
                print(f"  {sensor_id} ({sensor_type}): R={raw_data.get('red_raw', 0)}, "
                      f"G={raw_data.get('green_raw', 0)}, B={raw_data.get('blue_raw', 0)}, "
                      f"Lux={raw_data.get('lux', 0)}")
            elif sensor_type == 'TSL2591':
                raw_data = reading.get('raw_spectrum_data', {})
                print(f"  {sensor_id} ({sensor_type}): Visible={raw_data.get('visible', 0)}, "
                      f"IR={raw_data.get('infrared', 0)}, Lux={raw_data.get('lux', 0)}")
            elif sensor_type in ['AS7341', 'AS7265X']:
                raw_data = reading.get('raw_spectrum_data', {})
                channels = len(raw_data)
                total_intensity = sum(v for v in raw_data.values() if isinstance(v, (int, float)))
                print(f"  {sensor_id} ({sensor_type}): {channels} channels, Total={total_intensity:.1f}")
            else:
                raw_data = reading.get('raw_lux_data', {})
                print(f"  {sensor_id} ({sensor_type}): Lux={raw_data.get('lux', 0)}")
        else:
            print(f"  {sensor_id}: ERROR - {reading['error']}")
    
    # Perform direct fusion
    print("\n🔀 Performing Direct Fusion...")
    positions_adj = positions[:len(available_sensors)]  # Adjust positions to match available sensors
    result, histogram = fuse_and_display(sensor_data, positions_adj, target_pos)
    
    # Test API fusion
    print("\n🌐 Testing API Fusion...")
    api_result = test_api_fusion(available_sensors, positions_adj, target_pos)
    
    print("\n" + "=" * 50)
    print("✅ Fusion complete!")
    
    if result and histogram:
        print("\n💡 How to use this in your application:")
        print("1. Configure sensors in data/light_sensors.json with position metadata")
        print("2. Use /api/spectrum-fusion/live endpoint for real-time fusion")
        print("3. Analyze histogram data for grow light optimization")
        print("4. Monitor quality scores to assess fusion reliability")
        print("5. Use multiple sensor types for better spectral coverage")


if __name__ == "__main__":
    main()