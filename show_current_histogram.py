#!/usr/bin/env python3
"""
Quick histogram visualization to show current spectral fusion results.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion

def show_current_histogram():
    """Display ASCII histogram of current fusion results."""
    
    print("📊 Current Spectral Fusion Histogram")
    print("=" * 60)
    
    # Test data with 3 sensors
    sensors_data = [
        {
            'sensor_type': 'TCS34725',
            'raw_color_data': {
                'red_raw': 1200, 'green_raw': 1800, 'blue_raw': 800,
                'clear_raw': 4000, 'lux': 450.5, 'color_temperature_k': 4200
            }
        },
        {
            'sensor_type': 'TSL2591', 
            'raw_spectrum_data': {
                'lux': 425.3, 'infrared': 180.0,
                'visible': 340.0, 'full_spectrum': 520.0
            }
        },
        {
            'sensor_type': 'BH1750',
            'raw_lux_data': {'lux': 520.8}
        }
    ]
    
    positions = [(0, 0), (2, 0), (0, 3)]  # Sensor positions
    target_pos = (1, 1)                   # Center of triangle
    
    # Run fusion
    result = SpectralDataFusion.fuse_sensor_spectra(sensors_data, positions, target_pos)
    histogram = SpectralDataFusion.create_histogram_data(result)
    
    # Display histogram info
    print(f"🎯 Target Position: {target_pos}")
    print(f"📈 Overall Quality: {histogram['interpolation_quality']:.3f}")
    print(f"🔬 Sensors: TCS34725, TSL2591, BH1750")
    print(f"⚖️  Spatial Weights: {[f'{w:.3f}' for w in result['spatial_weights']]}")
    
    # Create ASCII histogram
    wavelengths = histogram['wavelengths']
    intensities = histogram['intensities']
    confidences = histogram['confidences']
    
    print(f"\n📊 Spectrum Histogram (28 bins, 20nm width):")
    print(f"{'Wavelength':<10} {'Intensity':<12} {'Confidence':<10} {'Bar':<20}")
    print("-" * 65)
    
    # Find max intensity for scaling
    max_intensity = max(intensities) if intensities else 1
    max_confidence = max(confidences) if confidences else 1
    
    for i, (wl, intensity, confidence) in enumerate(zip(wavelengths, intensities, confidences)):
        # Scale intensity bar (max 20 chars)
        intensity_bar_length = int((intensity / max_intensity) * 20) if max_intensity > 0 else 0
        intensity_bar = "█" * intensity_bar_length
        
        # Color coding by wavelength range
        if wl < 450:
            color_label = "UV/V"
        elif wl < 500:
            color_label = "Blue"
        elif wl < 580:
            color_label = "Green"
        elif wl < 650:
            color_label = "Y/O"
        elif wl < 700:
            color_label = "Red"
        else:
            color_label = "IR"
        
        print(f"{wl:<4.0f}nm {color_label:<5} {intensity:<8.1f} {confidence:<8.3f} {intensity_bar:<20}")
    
    # Summary by color ranges
    print(f"\n🌈 Summary by Color Range:")
    ranges = [
    (280, 450, "UV/Violet"),
        (450, 500, "Blue"), 
        (500, 580, "Green"),
        (580, 650, "Yellow/Orange"),
        (650, 700, "Red"),
    (700, 850, "Near-IR")
    ]
    
    for start, end, name in ranges:
        range_intensity = 0
        range_confidence = 0
        count = 0
        
        for wl, intensity, confidence in zip(wavelengths, intensities, confidences):
            if start <= wl < end:
                range_intensity += intensity
                range_confidence += confidence
                count += 1
        
        avg_confidence = range_confidence / count if count > 0 else 0
        
        print(f"  {name:<15}: {range_intensity:>8.1f} intensity, {avg_confidence:.3f} confidence")
    
    # Show sensor contributions
    print(f"\n🔍 Sensor Contribution Analysis:")
    fused_spectrum = result['fused_spectrum']
    
    sensor_contributions = {'TCS34725': 0, 'TSL2591': 0, 'BH1750': 0}
    total_intensity = 0
    
    for bin_data in fused_spectrum.values():
        total_intensity += bin_data['intensity']
        for source in bin_data['sources']:
            sensor_type = source['sensor_type']
            if sensor_type in sensor_contributions:
                sensor_contributions[sensor_type] += source['contribution']
    
    print(f"  Total Intensity: {total_intensity:.1f}")
    for sensor, contribution in sensor_contributions.items():
        percentage = (contribution / total_intensity * 100) if total_intensity > 0 else 0
        print(f"  {sensor:<10}: {contribution:>8.1f} ({percentage:>5.1f}%)")
    
    # Highlight improvements
    print(f"\n✨ Key Improvements with New Quality System:")
    print(f"  • BH1750 contributing {sensor_contributions['BH1750']:.1f} intensity")
    print(f"  • Quality varies by wavelength (not fixed per sensor)")
    print(f"  • Better confidence in visible range where BH1750 excels")
    print(f"  • More realistic fusion quality scores")

if __name__ == "__main__":
    show_current_histogram()