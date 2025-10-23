#!/usr/bin/env python3
"""
Simple command-line tool to demonstrate spectrum fusion between your TCS34725 and TSL2591 sensors.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion, estimate_midpoint_spectrum
import json


def create_text_histogram(wavelengths, intensities, width=60):
    """Create a simple ASCII histogram."""
    if not wavelengths or not intensities:
        return "No data to display"
    
    max_intensity = max(intensities)
    if max_intensity == 0:
        return "All intensities are zero"
    
    lines = []
    lines.append("Light Spectrum Histogram (Raw Sensor Fusion)")
    lines.append("=" * (width + 20))
    
    for wl, intensity in zip(wavelengths, intensities):
        # Normalize to histogram width
        bar_length = int((intensity / max_intensity) * width)
        bar = "█" * bar_length
        # Color coding based on wavelength
        if 280 <= wl < 450:
            color_name = "Violet/Blue"
        elif 450 <= wl < 520:
            color_name = "Blue/Cyan"
        elif 520 <= wl < 580:
            color_name = "Green"
        elif 580 <= wl < 650:
            color_name = "Yellow/Orange"
        elif 650 <= wl < 700:
            color_name = "Red"
        elif 700 <= wl < 850:
            color_name = "Near-IR"
        else:
            color_name = "Other"
        lines.append(f"{wl:3.0f}nm |{bar:<{width}} {intensity:6.1f} ({color_name})")
    
    lines.append("=" * (width + 20))
    lines.append(f"Peak intensity: {max_intensity:.1f} | Total bins: {len(wavelengths)}")
    
    return "\n".join(lines)


def main():
    # Example: Your TCS34725 and TSL2591 setup + third sensor
    print("🌱 Greenhouse Spectrum Fusion Tool")
    print("Combining TCS34725 (RGB color) + TSL2591 (full spectrum) + BH1750 (lux) data")
    print()
    

    # Simulate realistic sensor readings
    tcs34725_data = {
        'sensor_type': 'TCS34725',
        'raw_color_data': {
            'red_raw': 1850,     # Strong red component
            'green_raw': 2100,   # Dominant green (grow lights)
            'blue_raw': 650,     # Some blue
            'clear_raw': 4600,   # Total visible
            'lux': 580.3,
            'color_temperature_k': 3800  # Warm white grow light
        }
    }

    tsl2591_data = {
        'sensor_type': 'TSL2591',
        'raw_spectrum_data': {
            'lux': 595.7,
            'infrared': 240.0,   # Some IR component  
            'visible': 395.0,    # Visible matches roughly with TCS34725
            'full_spectrum': 635.0
        }
    }

    # Add a third sensor (BH1750) at position (0, 3)
    bh1750_data = {
        'sensor_type': 'BH1750',
        'raw_lux_data': {
            'lux': 520.8  # Slightly different lux reading due to position
        }
    }

    # Add a simulated UV sensor (320-400nm) at a random position
    import random
    uv_position = (round(random.uniform(0,2),2), round(random.uniform(0,3),2))
    uv_sensor_data = {
        'sensor_type': 'UV_SIM',
        'raw_uv_data': {
            'uv': 180.0  # Simulated UV intensity
        }
    }

    print(f"📍 TCS34725 position: (0, 0)")
    print(f"📍 TSL2591 position: (2, 0)")
    print(f"📍 BH1750 position: (0, 3) (NEW SENSOR)")
    print(f"📍 UV_SIM position: {uv_position} (RANDOM UV SENSOR)")
    
    # Test different target positions to show the effect
    target_positions = [
        (1, 0),     # Original midpoint between TCS and TSL
        (1, 1),     # Center of triangle formed by all three sensors
        (0, 1.5),   # Midpoint between TCS and BH1750
    ]
    
    for i, target_pos in enumerate(target_positions):
        print(f"\n{'='*60}")
        print(f"🎯 Test {i+1}: Estimating spectrum at position {target_pos}")
        print('='*60)

        print(f"\n🔬 4-Sensor Fusion (TCS34725 + TSL2591 + BH1750 + UV_SIM):")

        sensors_data = [tcs34725_data, tsl2591_data, bh1750_data, uv_sensor_data]
        positions = [(0,0), (2,0), (0,3), uv_position]

        result = SpectralDataFusion.fuse_sensor_spectra(
            sensors_data, positions, target_pos
        )

        histogram = SpectralDataFusion.create_histogram_data(result)

        print(f"  Quality Score: {histogram.get('interpolation_quality', 0):.3f}/1.0")
        print(f"  Data Sources: {', '.join(result['source_sensors'])}")
        print(f"  Spatial Weights: {[f'{w:.3f}' for w in result['spatial_weights']]}")
        print(f"  Histogram bins: {len(histogram['wavelengths'])}")

        # Calculate distances from target to each sensor
        distances = []
        for pos in positions:
            dist = ((target_pos[0] - pos[0])**2 + (target_pos[1] - pos[1])**2)**0.5
            distances.append(dist)

        print(f"\n📏 Distances from target {target_pos}:")
        sensor_names = ['TCS34725', 'TSL2591', 'BH1750', 'UV_SIM']
        for name, pos, dist, weight in zip(sensor_names, positions, distances, result['spatial_weights']):
            print(f"  {name} at {pos}: {dist:.2f} units → weight {weight:.3f}")

        # Show compact histogram for this target
        if histogram['wavelengths']:
            print(f"\n📈 Spectrum Summary for {target_pos}:")
            # Group into major spectral regions
            regions = {
                'UV (280-400nm)': (280, 400),
                'Violet/Blue (400-450nm)': (400, 450),
                'Blue (450-500nm)': (450, 500),
                'Green (500-580nm)': (500, 580),
                'Yellow/Orange (580-650nm)': (580, 650),
                'Red (650-700nm)': (650, 700),
                'Near-IR (700-850nm)': (700, 850)
            }
            for region_name, (min_wl, max_wl) in regions.items():
                region_intensity = sum(intensity for wl, intensity in zip(histogram['wavelengths'], histogram['intensities'])
                                     if min_wl <= wl < max_wl)
                if region_intensity > 0:
                    print(f"  {region_name}: {region_intensity:.1f}")
            # Find peak
            max_intensity_idx = histogram['intensities'].index(max(histogram['intensities']))
            peak_wavelength = histogram['wavelengths'][max_intensity_idx]
            peak_intensity = histogram['intensities'][max_intensity_idx]
            print(f"  Peak: {peak_wavelength:.0f} nm ({peak_intensity:.1f})")


if __name__ == "__main__":
    main()