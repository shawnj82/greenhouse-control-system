"""
fusion_calculator.py

Core functions for calculating spectral fusion values from multiple sensors.
Moved from demo scripts for production use.
"""

import random
from control.spectral_fusion import SpectralDataFusion

def calculate_fusion_for_positions(sensor_data_list, positions, target_positions):
    """
    Calculate fusion results for a set of sensors and target positions.
    Args:
        sensor_data_list: List of sensor data dicts (as in demo_spectrum_fusion.py)
        positions: List of (x, y) tuples for sensor positions
        target_positions: List of (x, y) tuples for fusion targets
    Returns:
        List of dicts with fusion results for each target position
    """
    results = []
    for target_pos in target_positions:
        result = SpectralDataFusion.fuse_sensor_spectra(sensor_data_list, positions, target_pos)
        histogram = SpectralDataFusion.create_histogram_data(result)
        results.append({
            'target': target_pos,
            'fusion_result': result,
            'histogram': histogram
        })
    return results

# Example usage (remove or comment out in production):
if __name__ == "__main__":
    # Simulate sensors: TCS34725, TSL2591, BH1750, UV_SIM
    tcs34725_data = {
        'sensor_type': 'TCS34725',
        'raw_color_data': {
            'red_raw': 1850,
            'green_raw': 2100,
            'blue_raw': 650,
            'clear_raw': 4600,
            'lux': 580.3,
            'color_temperature_k': 3800
        }
    }
    tsl2591_data = {
        'sensor_type': 'TSL2591',
        'raw_spectrum_data': {
            'lux': 595.7,
            'infrared': 240.0,
            'visible': 395.0,
            'full_spectrum': 635.0
        }
    }
    bh1750_data = {
        'sensor_type': 'BH1750',
        'raw_lux_data': {
            'lux': 520.8
        }
    }
    uv_position = (round(random.uniform(0,2),2), round(random.uniform(0,3),2))
    uv_sensor_data = {
        'sensor_type': 'UV_SIM',
        'raw_uv_data': {
            'uv': 180.0
        }
    }
    sensor_data_list = [tcs34725_data, tsl2591_data, bh1750_data, uv_sensor_data]
    positions = [(0,0), (2,0), (0,3), uv_position]
    target_positions = [
        (1, 0),
        (1, 1),
        (0, 1.5),
    ]
    results = calculate_fusion_for_positions(sensor_data_list, positions, target_positions)
    for res in results:
        print(f"Target: {res['target']}")
        print(f"  Quality: {res['histogram'].get('interpolation_quality', 0):.3f}")
        print(f"  Data Sources: {', '.join(res['fusion_result']['source_sensors'])}")
        print(f"  Spatial Weights: {[f'{w:.3f}' for w in res['fusion_result']['spatial_weights']]}")
        print(f"  Histogram bins: {len(res['histogram']['wavelengths'])}")
        print()
