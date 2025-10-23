#!/usr/bin/env python3
"""
Demonstration of improved quality weighting system that properly values
BH1750's lux measurement accuracy while recognizing its spectral limitations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion

def demonstrate_quality_improvements():
    """Show how the new quality weighting system better represents sensor capabilities."""
    
    print("🔬 Improved Sensor Quality Assessment Demo")
    print("=" * 60)
    
    # Create sample sensor data
    bh1750_data = {
        'sensor_type': 'BH1750',
        'raw_lux_data': {'lux': 450.2}
    }
    
    tcs34725_data = {
        'sensor_type': 'TCS34725', 
        'raw_color_data': {
            'red_raw': 1200, 'green_raw': 1800, 'blue_raw': 800,
            'clear_raw': 4000, 'lux': 380.5, 'color_temperature_k': 4200
        }
    }
    
    # Create spectrum bins for analysis
    spectrum_bins = SpectralDataFusion.create_spectrum_bins()
    
    print("📊 Quality Assessment Comparison:")
    print("\nOLD SYSTEM (Fixed quality per sensor):")
    print("  BH1750:  0.2 (poor) - same for all wavelengths")
    print("  TCS34725: 0.5 (medium) - same for all wavelengths")
    
    print("\nNEW SYSTEM (Measurement-specific quality):")
    
    # Get new quality weights
    bh1750_qualities = SpectralDataFusion.get_sensor_quality_for_measurement(
        'BH1750', bh1750_data, spectrum_bins
    )
    
    tcs34725_qualities = SpectralDataFusion.get_sensor_quality_for_measurement(
        'TCS34725', tcs34725_data, spectrum_bins
    )
    
    # Analyze quality by wavelength ranges
    ranges = [
    (280, 450, "UV/Violet"),
        (450, 500, "Blue"), 
        (500, 580, "Green"),
        (580, 650, "Yellow/Orange"),
        (650, 700, "Red"),
    (700, 850, "Near-IR")
    ]
    
    print(f"\n{'Wavelength Range':<15} {'BH1750 Quality':<15} {'TCS34725 Quality':<17} {'Winner':<10}")
    print("-" * 65)
    
    for start, end, name in ranges:
        # Find bins in this range
        range_bins = []
        for i, (bin_start, bin_end) in enumerate(spectrum_bins):
            if bin_start >= start and bin_end <= end:
                range_bins.append(i)
        
        if range_bins:
            bh1750_avg = sum(bh1750_qualities[i] for i in range_bins) / len(range_bins)
            tcs34725_avg = sum(tcs34725_qualities[i] for i in range_bins) / len(range_bins)
            
            winner = "BH1750" if bh1750_avg > tcs34725_avg else "TCS34725"
            if abs(bh1750_avg - tcs34725_avg) < 0.05:
                winner = "Tie"
            
            print(f"{name:<15} {bh1750_avg:<15.3f} {tcs34725_avg:<17.3f} {winner:<10}")
    
    print("\n🔍 Key Improvements in New System:")
    print("✅ BH1750 gets appropriate credit for lux accuracy in visible range")
    print("✅ TCS34725 gets higher quality in RGB bands where it excels")
    print("✅ Both sensors get minimal quality outside their capabilities")
    print("✅ Quality varies by wavelength, not fixed per sensor")
    
    print("\n💡 Practical Impact:")
    print("• For lux estimation: BH1750 now contributes meaningfully")
    print("• For color analysis: TCS34725 maintains its RGB strengths")
    print("• For IR analysis: Both sensors appropriately devalued")
    print("• Overall fusion: More accurate confidence estimates")
    
    # Show a specific example
    print(f"\n📋 Example - Visible Light Range (500-580nm Green):")
    green_bins = [i for i, (start, end) in enumerate(spectrum_bins) if 500 <= start < 580]
    if green_bins:
        bh1750_green = sum(bh1750_qualities[i] for i in green_bins) / len(green_bins)
        tcs34725_green = sum(tcs34725_qualities[i] for i in green_bins) / len(green_bins)
        
        print(f"  BH1750 quality: {bh1750_green:.3f} (was 0.200)")
        print(f"  TCS34725 quality: {tcs34725_green:.3f} (was 0.500)")
        print(f"  Quality improvement: {((bh1750_green - 0.2) / 0.2 * 100):+.1f}% for BH1750")
    
    print("\n🎯 Result: More accurate sensor fusion that respects each sensor's strengths!")

if __name__ == "__main__":
    demonstrate_quality_improvements()