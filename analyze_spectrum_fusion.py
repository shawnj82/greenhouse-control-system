#!/usr/bin/env python3
"""
Example script demonstrating spectral data fusion for light histogram creation.
Shows how to combine TCS34725 and TSL2591 data to estimate spectrum at midpoint.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control.spectral_fusion import SpectralDataFusion, estimate_midpoint_spectrum
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


def demo_spectrum_fusion():
    """Demonstrate spectrum fusion with example sensor data, including 3-sensor comparison."""
    
    # Example sensor readings (in the format your system now returns)
    tcs34725_reading = {
        'sensor_type': 'TCS34725',
        'raw_color_data': {
            'red_raw': 1200,
            'green_raw': 1800, 
            'blue_raw': 800,
            'clear_raw': 4000,
            'lux': 450.5,
            'color_temperature_k': 4200
        },
        'timestamp': 1697299200.0
    }
    
    tsl2591_reading = {
        'sensor_type': 'TSL2591', 
        'raw_spectrum_data': {
            'lux': 425.3,
            'infrared': 180.0,
            'visible': 340.0,
            'full_spectrum': 520.0
        },
        'timestamp': 1697299201.0
    }
    
    # Add third sensor
    bh1750_reading = {
        'sensor_type': 'BH1750',
        'raw_lux_data': {
            'lux': 390.2
        },
        'timestamp': 1697299202.0
    }
    
    # Sensor positions
    tcs34725_pos = (0, 0)      # TCS34725 at origin
    tsl2591_pos = (2, 0)       # TSL2591 2 units away in X direction
    bh1750_pos = (0, 3)        # BH1750 3 units away in Y direction
    
    print("=== Spectral Data Fusion Demo ===")
    print(f"TCS34725 position: {tcs34725_pos}")
    print(f"TSL2591 position: {tsl2591_pos}")
    print(f"BH1750 position: {bh1750_pos} (NEW)")
    
    # Test different target positions
    target_positions = [
        (1, 0),     # Original midpoint
        (1, 1),     # Center of triangle  
        (0, 1.5)    # Between TCS and BH1750
    ]
    
    results = {}
    
    for target_pos in target_positions:
        print(f"\nTarget position: {target_pos}")
        
        # 2-sensor fusion (original)
        result_2sensor = estimate_midpoint_spectrum(
            tcs34725_reading, tcs34725_pos,
            tsl2591_reading, tsl2591_pos
        )
        
        # 3-sensor fusion
        sensors_data = [tcs34725_reading, tsl2591_reading, bh1750_reading]
        positions = [tcs34725_pos, tsl2591_pos, bh1750_pos]
        
        result_3sensor = SpectralDataFusion.fuse_sensor_spectra(
            sensors_data, positions, target_pos
        )
        histogram_3sensor = SpectralDataFusion.create_histogram_data(result_3sensor)
        
        # Store results for plotting
        results[target_pos] = {
            '2sensor': result_2sensor,
            '3sensor': {'fused_spectrum': result_3sensor, 'histogram': histogram_3sensor}
        }
        
        # Display comparison
        fusion_summary_2 = result_2sensor['fusion_summary']
        quality_2 = fusion_summary_2['quality_score']
        quality_3 = histogram_3sensor.get('interpolation_quality', 0)
        
        print(f"  2-sensor quality: {quality_2:.3f}")
        print(f"  3-sensor quality: {quality_3:.3f}")
        print(f"  Quality change: {quality_3 - quality_2:+.3f}")
        print(f"  Spatial weights: {[f'{w:.3f}' for w in result_3sensor['spatial_weights']]}")
    
    return results


def plot_comparison_analysis(results):
    """Create comprehensive plots comparing 2-sensor vs 3-sensor fusion."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Set up the figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # Color scheme
    colors_2sensor = ['#2E86AB', '#A23B72', '#F18F01']  # Blue, Purple, Orange
    colors_3sensor = ['#006D77', '#83C5BE', '#FFDDD2']  # Teal, Light Teal, Peach
    
    plot_idx = 1
    
    for i, (target_pos, data) in enumerate(results.items()):
        # Extract data
        hist_2 = data['2sensor']['histogram']
        hist_3 = data['3sensor']['histogram']
        
        # Quality comparison subplot
        ax1 = plt.subplot(3, 3, plot_idx)
        qualities = [hist_2['interpolation_quality'], hist_3['interpolation_quality']]
        bars = ax1.bar(['2-Sensor', '3-Sensor'], qualities, 
                      color=[colors_2sensor[i], colors_3sensor[i]], alpha=0.8)
        ax1.set_ylabel('Quality Score')
        ax1.set_title(f'Position {target_pos}: Quality Comparison')
        ax1.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar, quality in zip(bars, qualities):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{quality:.3f}', ha='center', va='bottom', fontweight='bold')
        
        plot_idx += 1
        
        # Spectrum intensity comparison
        ax2 = plt.subplot(3, 3, plot_idx)
        wavelengths = hist_2['wavelengths']
        intensities_2 = hist_2['intensities']
        intensities_3 = hist_3['intensities']
        
        ax2.plot(wavelengths, intensities_2, 'o-', color=colors_2sensor[i], 
                label='2-Sensor', linewidth=2, markersize=4)
        ax2.plot(wavelengths, intensities_3, 's-', color=colors_3sensor[i], 
                label='3-Sensor', linewidth=2, markersize=4)
        ax2.set_xlabel('Wavelength (nm)')
        ax2.set_ylabel('Intensity')
        ax2.set_title(f'Position {target_pos}: Spectrum Comparison')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plot_idx += 1
        
        # Confidence comparison
        ax3 = plt.subplot(3, 3, plot_idx)
        confidences_2 = hist_2['confidences']
        confidences_3 = hist_3['confidences']
        
        ax3.plot(wavelengths, confidences_2, 'o-', color=colors_2sensor[i], 
                label='2-Sensor', linewidth=2, markersize=4)
        ax3.plot(wavelengths, confidences_3, 's-', color=colors_3sensor[i], 
                label='3-Sensor', linewidth=2, markersize=4)
        ax3.set_xlabel('Wavelength (nm)')
        ax3.set_ylabel('Confidence')
        ax3.set_title(f'Position {target_pos}: Confidence Comparison')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        plot_idx += 1
    
    plt.tight_layout()
    
    # Save the plot
    filename = 'spectrum_fusion_3sensor_comparison.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Comparison plot saved as: {filename}")
    
    plt.show()
    
    return filename

def plot_sensor_layout(target_positions):
    """Plot the sensor layout and target positions."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Sensor positions
    tcs34725_pos = (0, 0)
    tsl2591_pos = (2, 0)
    bh1750_pos = (0, 3)
    
    # Plot sensors
    ax.scatter(*tcs34725_pos, s=200, c='red', marker='o', label='TCS34725 (RGB)', zorder=5)
    ax.scatter(*tsl2591_pos, s=200, c='blue', marker='s', label='TSL2591 (Full Spectrum)', zorder=5)
    ax.scatter(*bh1750_pos, s=200, c='green', marker='^', label='BH1750 (Lux)', zorder=5)
    
    # Plot target positions
    for i, target_pos in enumerate(target_positions):
        ax.scatter(*target_pos, s=100, c='orange', marker='x', zorder=5)
        ax.annotate(f'Target {i+1}\n{target_pos}', target_pos, 
                   xytext=(10, 10), textcoords='offset points', 
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # Draw coverage areas (approximate)
    circle1 = plt.Circle(tcs34725_pos, 1.5, fill=False, color='red', linestyle='--', alpha=0.5)
    circle2 = plt.Circle(tsl2591_pos, 1.5, fill=False, color='blue', linestyle='--', alpha=0.5)
    circle3 = plt.Circle(bh1750_pos, 1.5, fill=False, color='green', linestyle='--', alpha=0.5)
    ax.add_patch(circle1)
    ax.add_patch(circle2)
    ax.add_patch(circle3)
    
    # Connect sensors to show triangulation
    triangle_x = [tcs34725_pos[0], tsl2591_pos[0], bh1750_pos[0], tcs34725_pos[0]]
    triangle_y = [tcs34725_pos[1], tsl2591_pos[1], bh1750_pos[1], tcs34725_pos[1]]
    ax.plot(triangle_x, triangle_y, 'k--', alpha=0.3, linewidth=1)
    
    ax.set_xlabel('X Position (units)')
    ax.set_ylabel('Y Position (units)')
    ax.set_title('Sensor Layout and Target Positions\n3-Sensor Triangulation Analysis')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')
    
    # Set reasonable axis limits
    ax.set_xlim(-1, 3)
    ax.set_ylim(-1, 4)
    
    # Save the plot
    filename = 'sensor_layout_3sensor.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Sensor layout plot saved as: {filename}")
    
    plt.show()
    
    return filename


def analyze_sensor_coverage():
    """Analyze spectral coverage of different sensor types."""
    print("\n=== Sensor Spectral Coverage Analysis ===")
    
    wavelength_maps = SpectralDataFusion.SENSOR_WAVELENGTH_MAPS
    
    for sensor_type, channels in wavelength_maps.items():
        print(f"\n{sensor_type}:")
        total_range = [1000, 0]  # min, max
        
        for channel, (min_wl, max_wl) in channels.items():
            print(f"  {channel}: {min_wl}-{max_wl} nm")
            total_range[0] = min(total_range[0], min_wl)
            total_range[1] = max(total_range[1], max_wl)
        
        coverage = total_range[1] - total_range[0]
        print(f"  Total coverage: {total_range[0]}-{total_range[1]} nm ({coverage} nm span)")
        
        # Calculate spectral resolution
        num_channels = len([ch for ch in channels.keys() if 'raw' in ch or 'ch_' in ch or ch in ['violet', 'indigo', 'blue']])
        if num_channels > 1:
            avg_resolution = coverage / num_channels
            print(f"  Average resolution: {avg_resolution:.1f} nm/channel")


if __name__ == "__main__":
    print("3-Sensor Spectral Data Fusion Demo")
    print("=" * 50)
    
    # Run the spectrum fusion demo
    results = demo_spectrum_fusion()
    
    # Plot the results
    print("\n=== Creating Visualizations ===")
    
    # Plot sensor layout
    target_positions = list(results.keys())
    layout_file = plot_sensor_layout(target_positions)
    
    # Plot comparison analysis
    comparison_file = plot_comparison_analysis(results)
    
    print(f"\nGenerated plots:")
    print(f"  1. Sensor layout: {layout_file}")
    print(f"  2. Fusion comparison: {comparison_file}")
    
    # Summary analysis
    print("\n=== 3-Sensor Integration Summary ===")
    print("Key Findings:")
    
    for target_pos, data in results.items():
        quality_2 = data['2sensor']['histogram']['interpolation_quality']
        quality_3 = data['3sensor']['histogram']['interpolation_quality']
        quality_change = quality_3 - quality_2
        
        print(f"\nTarget {target_pos}:")
        print(f"  Quality change: {quality_change:+.3f} ({quality_change/quality_2*100:+.1f}%)")
        
        if quality_change > 0:
            print(f"  ✓ Third sensor improves interpolation quality")
        else:
            print(f"  ⚠ Third sensor reduces quality (spatial dilution effect)")
    
    print("\nConclusions:")
    print("- Adding a third sensor provides triangulation capability")
    print("- Quality impact varies by target position relative to sensor triangle")
    print("- Optimal positioning balances sensor proximity with triangulation benefits")
    print("- BH1750's lower quality rating (0.2) can dilute overall fusion quality")
    print("- Strategic sensor placement crucial for multi-sensor optimization")