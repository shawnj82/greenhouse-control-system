#!/usr/bin/env python3
"""
Demonstration of 3D distance-based spatial weighting for greenhouse light modeling.
Shows how accounting for light height (6ft) and sensor height (3ft) affects fusion weights.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion
import math

def demonstrate_3d_distance_weighting():
    """Show how 3D distance modeling affects spatial weights in realistic greenhouse setup."""
    
    print("🌱 3D Greenhouse Light Distance Modeling")
    print("=" * 60)
    print("Setup: Lights at 6ft height, Sensors at 3ft height")
    print("Baseline vertical distance: 3ft between lights and sensors")
    print()
    
    # Test sensor positions (in grid units, assume 1 unit = 1 foot)
    sensor_positions = [
        (0, 0, "TCS34725"),  # Origin sensor
        (2, 0, "TSL2591"),   # 2 feet away horizontally  
        (0, 3, "BH1750"),    # 3 feet away horizontally
        (4, 0, "Remote"),    # 4 feet away horizontally
        (1, 1, "Diagonal")   # sqrt(2) feet away diagonally
    ]
    
    target_positions = [
        (1, 0, "Midpoint TCS-TSL"),
        (0, 1.5, "Midpoint TCS-BH1750"), 
        (1, 1, "Triangle Center"),
        (0, 0, "At TCS34725"),
        (6, 0, "Far Position")
    ]
    
    print("📏 Distance Comparison: 2D vs 3D")
    print(f"{'Position':<15} {'2D Distance':<12} {'3D Distance':<12} {'Weight Change':<12}")
    print("-" * 60)
    
    for x, y, name in sensor_positions:
        target_x, target_y = 1, 0  # Reference target position
        
        # 2D distance (old method)
        dist_2d = math.sqrt((target_x - x)**2 + (target_y - y)**2)
        weight_2d = 1.0 / (dist_2d**2 + 0.01)
        
        # 3D distance (new method)  
        dist_3d = SpectralDataFusion.calculate_3d_light_distance(
            (x, y), (target_x, target_y), light_height_ft=6.0, sensor_height_ft=3.0
        )
        weight_3d = 1.0 / (dist_3d**2 + 0.01)
        
        weight_change = (weight_3d - weight_2d) / weight_2d * 100 if weight_2d > 0 else 0
        
        print(f"{name:<15} {dist_2d:<8.2f}ft   {dist_3d:<8.2f}ft   {weight_change:>+7.1f}%")
    
    print("\n🔍 Key Insights:")
    print("• In-zone sensors (0 horizontal distance) now have 3.0ft baseline distance")
    print("• 1 unit away: 2D=1.0ft vs 3D=3.16ft (much more realistic)")
    print("• Far sensors get relatively higher weights (less dramatic falloff)")
    print("• Weight distribution more balanced across nearby sensors")
    
    # Detailed analysis for 3-sensor setup
    print(f"\n📊 3-Sensor Weight Analysis")
    print("Sensors: TCS34725 (0,0), TSL2591 (2,0), BH1750 (0,3)")
    
    sensors_data = [
        {'sensor_type': 'TCS34725', 'raw_color_data': {'lux': 450}},
        {'sensor_type': 'TSL2591', 'raw_spectrum_data': {'lux': 425}},
        {'sensor_type': 'BH1750', 'raw_lux_data': {'lux': 520}}
    ]
    
    positions = [(0, 0), (2, 0), (0, 3)]
    
    for target_x, target_y, target_name in target_positions:
        print(f"\n🎯 Target: {target_name} at ({target_x}, {target_y})")
        
        # Calculate 2D weights (old method)
        weights_2d = []
        for pos in positions:
            dist = math.sqrt((target_x - pos[0])**2 + (target_y - pos[1])**2)
            weight = 1.0 / (dist**2 + 0.01)
            weights_2d.append(weight)
        
        total_2d = sum(weights_2d)
        weights_2d_norm = [w/total_2d for w in weights_2d]
        
        # Calculate 3D weights (new method)
        weights_3d = SpectralDataFusion.calculate_light_intensity_weights(
            sensors_data, positions, (target_x, target_y)
        )
        
        print(f"  2D weights: {[f'{w:.3f}' for w in weights_2d_norm]}")
        print(f"  3D weights: {[f'{w:.3f}' for w in weights_3d]}")
        
        # Show distances for context
        distances_3d = []
        for pos in positions:
            dist_3d = SpectralDataFusion.calculate_3d_light_distance(
                pos, (target_x, target_y)
            )
            distances_3d.append(dist_3d)
        
        print(f"  3D distances: {[f'{d:.2f}ft' for d in distances_3d]}")
        
        # Calculate weight changes
        changes = []
        for w2d, w3d in zip(weights_2d_norm, weights_3d):
            change = (w3d - w2d) / w2d * 100 if w2d > 0 else 0
            changes.append(change)
        
        print(f"  Weight changes: {[f'{c:+.1f}%' for c in changes]}")
    
    print(f"\n💡 Practical Impact:")
    print("✅ More realistic light intensity modeling")
    print("✅ Better weight distribution for nearby sensors") 
    print("✅ Accounts for actual greenhouse geometry")
    print("✅ Follows inverse square law of light physics")
    print("✅ Baseline 3ft distance prevents extreme weight dominance")

if __name__ == "__main__":
    demonstrate_3d_distance_weighting()