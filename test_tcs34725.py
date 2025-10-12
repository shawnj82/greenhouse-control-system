#!/usr/bin/env python3
"""
TCS34725 RGB Color Sensor Test Script

This script helps you test and understand the TCS34725 color sensor capabilities.
Run this after wiring up your TCS34725 to see what light qualities it can measure.
"""

import time
import sys
from sensors.spectral_sensors import TCS34725Color

def print_header():
    """Print information about TCS34725 capabilities."""
    print("🌈 TCS34725 RGB Color Sensor Test")
    print("=" * 50)
    print()
    print("📊 LIGHT QUALITIES THE TCS34725 CAN MEASURE:")
    print("   • Red light intensity (raw counts)")
    print("   • Green light intensity (raw counts)")
    print("   • Blue light intensity (raw counts)")
    print("   • Clear/Total light (raw counts)")
    print("   • Color Temperature (Kelvin) - warmth/coolness of light")
    print("   • Illuminance (Lux) - brightness level")
    print("   • RGB Ratios (percentages) - color balance")
    print()
    print("💡 PRACTICAL APPLICATIONS:")
    print("   • Detect grow light color spectrum")
    print("   • Measure color temperature (warm vs cool white)")
    print("   • Monitor light color consistency") 
    print("   • Identify colored LED channels")
    print("   • Calculate RGB color balance")
    print()
    print("🔌 WIRING (I2C Connection):")
    print("   • VCC/VIN → 3.3V or 5V")
    print("   • GND → Ground")
    print("   • SDA → GPIO 2 (Raspberry Pi)")
    print("   • SCL → GPIO 3 (Raspberry Pi)")
    print("   • Default I2C Address: 0x29")
    print()
    print("📈 Starting measurements...")
    print("=" * 50)

def analyze_light_type(color_data):
    """Analyze the light type based on color readings."""
    if not color_data:
        return "❌ No data"
    
    # Get color temperature
    temp_k = color_data.get('color_temperature_k', 0)
    lux = color_data.get('lux', 0)
    
    # Get RGB ratios
    r = color_data.get('red_raw', 0)
    g = color_data.get('green_raw', 0)
    b = color_data.get('blue_raw', 0)
    
    total_rgb = r + g + b
    if total_rgb == 0:
        return "🌑 No light detected"
    
    r_pct = (r / total_rgb) * 100
    g_pct = (g / total_rgb) * 100
    b_pct = (b / total_rgb) * 100
    
    analysis = []
    
    # Brightness level
    if lux < 1:
        analysis.append("🌑 Very dim")
    elif lux < 10:
        analysis.append("🌘 Dim")
    elif lux < 100:
        analysis.append("🌖 Moderate")
    elif lux < 1000:
        analysis.append("🌞 Bright")
    else:
        analysis.append("☀️ Very bright")
    
    # Color temperature analysis
    if temp_k > 0:
        if temp_k < 3000:
            analysis.append("🔥 Very warm white")
        elif temp_k < 4000:
            analysis.append("🌅 Warm white")
        elif temp_k < 5000:
            analysis.append("💡 Neutral white")
        elif temp_k < 6500:
            analysis.append("☁️ Cool white")
        else:
            analysis.append("❄️ Daylight/cold white")
    
    # Color dominance
    dominant_color = max([('Red', r_pct), ('Green', g_pct), ('Blue', b_pct)], key=lambda x: x[1])
    if dominant_color[1] > 40:
        analysis.append(f"🎨 {dominant_color[0]}-dominant")
    elif dominant_color[1] > 35:
        analysis.append(f"🎨 {dominant_color[0]}-tinted")
    
    # RGB balance
    rgb_std = ((r_pct - 33.33)**2 + (g_pct - 33.33)**2 + (b_pct - 33.33)**2)**0.5
    if rgb_std < 5:
        analysis.append("⚖️ Well-balanced RGB")
    elif rgb_std > 15:
        analysis.append("🌈 Strongly colored")
    
    return " | ".join(analysis)

def format_reading(color_data):
    """Format sensor reading for display."""
    if not color_data:
        return "❌ Failed to read sensor"
    
    # Calculate RGB ratios
    sensor = TCS34725Color()
    ratios = sensor.calculate_rgb_ratios(color_data)
    
    lines = [
        f"🔴 Red:   {color_data['red_raw']:>6} ({ratios.get('red_percent', 0):5.1f}%)",
        f"🟢 Green: {color_data['green_raw']:>6} ({ratios.get('green_percent', 0):5.1f}%)",
        f"🔵 Blue:  {color_data['blue_raw']:>6} ({ratios.get('blue_percent', 0):5.1f}%)",
        f"⚪ Clear: {color_data['clear_raw']:>6}",
        f"🌡️  Temp:  {color_data['color_temperature_k']:>6.0f}K",
        f"💡 Lux:   {color_data['lux']:>6.1f}",
        f"📊 Analysis: {analyze_light_type(color_data)}"
    ]
    return "\n".join(lines)

def test_sensor():
    """Test the TCS34725 sensor."""
    print_header()
    
    # Initialize sensor
    print("🔧 Initializing TCS34725 sensor...")
    sensor = TCS34725Color()
    
    if not sensor.sensor:
        print("❌ Failed to initialize TCS34725!")
        print("   Check wiring and I2C connection.")
        print("   Make sure sensor is powered and connected to I2C bus.")
        return False
    
    print("✅ TCS34725 initialized successfully!")
    print()
    
    try:
        print("📊 Live readings (Ctrl+C to stop):")
        print("-" * 50)
        
        reading_count = 0
        while True:
            # Read sensor
            color_data = sensor.read_color()
            
            # Display reading
            print(f"\n📷 Reading #{reading_count + 1}:")
            print(format_reading(color_data))
            print("-" * 50)
            
            reading_count += 1
            time.sleep(2)  # Wait 2 seconds between readings
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopped after {reading_count} readings.")
        print("✅ TCS34725 test completed!")
        return True

def main():
    """Main function."""
    try:
        success = test_sensor()
        if success:
            print("\n💡 TIP: Try testing different light sources:")
            print("   • Incandescent bulb (warm, red-heavy)")
            print("   • LED grow lights (often red/blue heavy)")
            print("   • Fluorescent (cool, even spectrum)")
            print("   • Sunlight (balanced, high color temp)")
            print("   • Individual colored LEDs")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()