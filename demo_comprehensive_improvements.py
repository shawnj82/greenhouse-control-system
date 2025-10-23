#!/usr/bin/env python3
"""
Comprehensive demonstration of all improvements made to the spectral fusion system:
1. Measurement-specific quality weighting (BH1750 gets proper credit for lux accuracy)
2. 3D distance modeling (accounts for light height vs sensor height)
3. Realistic greenhouse geometry modeling
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion

def comprehensive_improvements_demo():
    """Show all improvements in context."""
    
    print("🌱 Comprehensive Spectral Fusion System Improvements")
    print("=" * 70)
    print("Modeling realistic greenhouse setup:")
    print("• Lights mounted at 6 feet height")
    print("• Sensors positioned at 3 feet height") 
    print("• 3D distance calculations with inverse square law")
    print("• Measurement-specific quality weighting")
    print()
    
    # Test configuration
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
    
    positions = [(0, 0), (2, 0), (0, 3)]  # TCS34725, TSL2591, BH1750
    target_pos = (1, 1)  # Center of triangle
    
    print("📊 Test Configuration:")
    print("  TCS34725 at (0, 0) - RGB color sensor")
    print("  TSL2591 at (2, 0) - Full spectrum sensor")  
    print("  BH1750 at (0, 3) - High-accuracy lux sensor")
    print(f"  Target position: {target_pos} - Center of sensor triangle")
    print()
    
    # Run fusion analysis
    result = SpectralDataFusion.fuse_sensor_spectra(sensors_data, positions, target_pos)
    histogram = SpectralDataFusion.create_histogram_data(result)
    
    print("🔬 Fusion Results:")
    print(f"  Overall Quality: {histogram['interpolation_quality']:.3f}")
    print(f"  Spatial Weights: {[f'{w:.3f}' for w in result['spatial_weights']]}")
    print(f"  Interpolation Method: 3D inverse distance weighting")
    print()
    
    # Show 3D distances
    print("📏 3D Distance Analysis:")
    for i, (pos, sensor_data) in enumerate(zip(positions, sensors_data)):
        sensor_type = sensor_data['sensor_type']
        dist_3d = SpectralDataFusion.calculate_3d_light_distance(pos, target_pos)
        spatial_weight = result['spatial_weights'][i]
        
        print(f"  {sensor_type:<10}: {dist_3d:.2f}ft → weight {spatial_weight:.3f}")
    print()
    
    # Quality analysis by wavelength
    print("🌈 Quality Assessment by Wavelength Range:")
    
    # Get quality weights for each sensor
    spectrum_bins = SpectralDataFusion.create_spectrum_bins()
    # Bins now default to 280-850nm (20nm bins)
    
    ranges = [
        (400, 500, "Blue"),
        (500, 600, "Green"), 
        (600, 700, "Red"),
        (700, 800, "Near-IR")
    ]
    
    for start, end, color_name in ranges:
        print(f"\n  {color_name} Range ({start}-{end}nm):")
        
        for sensor_data in sensors_data:
            sensor_type = sensor_data['sensor_type']
            quality_weights = SpectralDataFusion.get_sensor_quality_for_measurement(
                sensor_type, sensor_data, spectrum_bins
            )
            
            # Calculate average quality in this range
            range_qualities = []
            for i, (bin_start, bin_end) in enumerate(spectrum_bins):
                if start <= bin_start < end:
                    range_qualities.append(quality_weights.get(i, 0))
            
            avg_quality = sum(range_qualities) / len(range_qualities) if range_qualities else 0
            print(f"    {sensor_type:<10}: {avg_quality:.3f} quality")
    
    # Sensor contribution analysis
    print(f"\n🔍 Sensor Contribution Analysis:")
    fused_spectrum = result['fused_spectrum']
    
    sensor_contributions = {}
    total_intensity = 0
    
    for bin_data in fused_spectrum.values():
        total_intensity += bin_data['intensity']
        for source in bin_data['sources']:
            sensor_type = source['sensor_type']
            if sensor_type not in sensor_contributions:
                sensor_contributions[sensor_type] = 0
            sensor_contributions[sensor_type] += source['contribution']
    
    print(f"  Total Spectrum Intensity: {total_intensity:.1f}")
    for sensor_type, contribution in sensor_contributions.items():
        percentage = (contribution / total_intensity * 100) if total_intensity > 0 else 0
        print(f"  {sensor_type:<10}: {contribution:>8.1f} ({percentage:>5.1f}%)")
    
    print(f"\n✨ Key System Improvements:")
    print("  1. 🎯 Measurement-Specific Quality Weighting:")
    print("     • BH1750 gets 0.6 quality for visible light (was 0.2 for all)")
    print("     • TCS34725 gets higher quality in RGB bands")
    print("     • Quality varies by wavelength, not fixed per sensor")
    print()
    print("  2. 📐 3D Distance Modeling:")
    print("     • Accounts for 6ft light height and 3ft sensor height")
    print("     • 3ft baseline distance (not 0ft for co-located)")
    print("     • Follows inverse square law of light physics")
    print("     • More balanced weight distribution")
    print()
    print("  3. 🌱 Realistic Greenhouse Geometry:")
    print("     • Models actual light-to-sensor distances")
    print("     • Prevents unrealistic weight dominance")
    print("     • Better spatial interpolation coverage")
    print("     • More accurate confidence estimates")
    
    print(f"\n🎉 Result: BH1750 now contributes {sensor_contributions.get('BH1750', 0):.1f} intensity")
    print("    (Previously contributed ~0 due to poor quality weighting)")
    print(f"    Quality degradation minimal: {(1-histogram['interpolation_quality'])*100:.1f}% uncertainty")
    print("    (Previously showed 15-50% quality drops)")

if __name__ == "__main__":
    comprehensive_improvements_demo()