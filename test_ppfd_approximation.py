#!/usr/bin/env python3
"""Test script to demonstrate the RGB-based PPFD approximation."""

from sensors.spectral_sensors import TCS34725Color

def test_ppfd_approximation():
    """Test PPFD approximation with different light scenarios."""
    
    sensor = TCS34725Color()
    
    print("PPFD Approximation Test - RGB Spectral Analysis")
    print("=" * 60)
    
    # Test scenarios with different RGB characteristics
    scenarios = [
        {
            "name": "Warm White LED (3000K)",
            "data": {
                "red_raw": 5000, "green_raw": 3500, "blue_raw": 2000,
                "lux": 1000, "color_temperature_k": 3000
            }
        },
        {
            "name": "Cool White LED (6500K)", 
            "data": {
                "red_raw": 3000, "green_raw": 4000, "blue_raw": 5500,
                "lux": 1000, "color_temperature_k": 6500
            }
        },
        {
            "name": "Red-Heavy Grow Light",
            "data": {
                "red_raw": 8000, "green_raw": 2000, "blue_raw": 1500,
                "lux": 1000, "color_temperature_k": 2700
            }
        },
        {
            "name": "Blue-Heavy Aquarium Light",
            "data": {
                "red_raw": 1000, "green_raw": 2500, "blue_raw": 7000,
                "lux": 1000, "color_temperature_k": 8000
            }
        },
        {
            "name": "Green-Heavy (Poor for Plants)",
            "data": {
                "red_raw": 1500, "green_raw": 7000, "blue_raw": 1500,
                "lux": 1000, "color_temperature_k": 5500
            }
        }
    ]
    
    for scenario in scenarios:
        data = scenario["data"]
        ppfd = sensor.approximate_ppfd(data)
        
        # Calculate RGB percentages for display
        total_rgb = data["red_raw"] + data["green_raw"] + data["blue_raw"]
        r_pct = (data["red_raw"] / total_rgb) * 100
        g_pct = (data["green_raw"] / total_rgb) * 100
        b_pct = (data["blue_raw"] / total_rgb) * 100
        
        conversion_factor = ppfd / data["lux"]
        
        print(f"\n{scenario['name']}:")
        print(f"  RGB Distribution: R={r_pct:.1f}% G={g_pct:.1f}% B={b_pct:.1f}%")
        print(f"  Color Temperature: {data['color_temperature_k']}K")
        print(f"  Lux: {data['lux']}")
        print(f"  PPFD: {ppfd:.2f} μmol/m²/s")
        print(f"  Conversion Factor: {conversion_factor:.4f} μmol/m²/s per lux")
        
        # Calculate efficiency relative to baseline
        baseline_factor = 0.0185  # Standard white LED
        efficiency = (conversion_factor / baseline_factor) * 100
        print(f"  PAR Efficiency: {efficiency:.1f}% of standard white LED")

if __name__ == "__main__":
    test_ppfd_approximation()