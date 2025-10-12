#!/usr/bin/env python3
"""
Demonstration of Ambient Light Aware Calibration Behavior.
Shows how the system adapts to different lighting conditions.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from control.ambient_light_handler import AmbientAwareCalibrator, AmbientLightLevel

def demonstrate_ambient_scenarios():
    """Demonstrate calibration behavior under different ambient light scenarios."""
    
    print("🌅 AMBIENT LIGHT CALIBRATION BEHAVIOR DEMONSTRATION")
    print("=" * 70)
    
    # Mock sensor configuration
    sensors_config = {
        "sensor_1": {"type": "BH1750", "zone_key": "A1"},
        "sensor_2": {"type": "TSL2591", "zone_key": "A2"},
        "sensor_3": {"type": "VEML7700", "zone_key": "B1"}
    }
    
    calibrator = AmbientAwareCalibrator(sensors_config)
    
    # Define different ambient light scenarios
    scenarios = [
        {
            "name": "🌙 Nighttime Greenhouse (Ideal Conditions)",
            "description": "Complete darkness, artificial lights only",
            "readings": {"sensor_1": 0.5, "sensor_2": 1.2, "sensor_3": 0.8},
            "expected_behavior": "Perfect calibration conditions"
        },
        {
            "name": "🌆 Early Morning/Late Evening",
            "description": "Low ambient light, some natural illumination",
            "readings": {"sensor_1": 45, "sensor_2": 52, "sensor_3": 38},
            "expected_behavior": "Excellent calibration with minor adjustments"
        },
        {
            "name": "☁️ Overcast Day",
            "description": "Moderate ambient light, stable conditions",
            "readings": {"sensor_1": 350, "sensor_2": 380, "sensor_3": 320},
            "expected_behavior": "Good calibration with longer measurement times"
        },
        {
            "name": "⛅ Partly Cloudy Day",
            "description": "Variable ambient light due to moving clouds",
            "readings": {"sensor_1": 850, "sensor_2": 1200, "sensor_3": 650},
            "expected_behavior": "Challenging - high variation reduces accuracy"
        },
        {
            "name": "☀️ Bright Sunny Day",
            "description": "High ambient light, stable but overwhelming",
            "readings": {"sensor_1": 3500, "sensor_2": 4200, "sensor_3": 3800},
            "expected_behavior": "Poor calibration - artificial lights lost in noise"
        },
        {
            "name": "🌞 Midday Sun (Peak Conditions)",
            "description": "Very high ambient light, calibration not recommended",
            "readings": {"sensor_1": 12000, "sensor_2": 15000, "sensor_3": 11500},
            "expected_behavior": "Calibration deferred - wait for better conditions"
        },
        {
            "name": "🌤️ Variable Morning Light",
            "description": "Sunrise conditions with changing light",
            "readings": {"sensor_1": 150, "sensor_2": 800, "sensor_3": 300},
            "expected_behavior": "High variation - may defer calibration"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 SCENARIO {i}: {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"   Expected: {scenario['expected_behavior']}")
        print("-" * 50)
        
        # Analyze ambient conditions
        conditions = calibrator.ambient_analyzer.analyze_current_conditions(scenario['readings'])
        should_calibrate, reason = calibrator.should_calibrate_now(scenario['readings'])
        params = calibrator.get_adaptive_calibration_params(scenario['readings'])
        
        # Display analysis
        print(f"📊 Ambient Analysis:")
        print(f"   Light Level: {conditions.level.value.upper()}")
        print(f"   Average Lux: {conditions.average_lux:.1f}")
        print(f"   Variation: {conditions.variation_coefficient:.2f}")
        print(f"   Feasibility: {conditions.calibration_feasibility:.2f}")
        print(f"   Weather: {conditions.weather_condition}")
        print(f"   Time of Day: {conditions.time_of_day}")
        
        print(f"\n🎯 Calibration Decision:")
        print(f"   Should Calibrate: {'✅ YES' if should_calibrate else '❌ NO'}")
        print(f"   Reason: {reason}")
        print(f"   Strategy: {conditions.recommended_strategy}")
        
        if should_calibrate:
            adjustments = params['calibration_adjustments']
            constraints = params['optimization_constraints']
            measurement = params['measurement_settings']
            
            print(f"\n⚙️ Calibration Adaptations:")
            print(f"   Baseline Time: {adjustments['baseline_measurement_time']:.1f}s")
            print(f"   Light Test Time: {adjustments['light_measurement_time']:.1f}s")
            print(f"   Measurement Repeats: {adjustments['measurement_repeats']}")
            print(f"   Stabilization Delay: {adjustments['stabilization_delay']:.1f}s")
            print(f"   Outlier Threshold: {adjustments['outlier_rejection_threshold']:.1f}")
            
            print(f"\n📐 Measurement Settings:")
            print(f"   Integration Time: {measurement['integration_time']}")
            print(f"   Gain: {measurement['gain']}")
            print(f"   Differential Mode: {measurement['differential_mode']}")
            print(f"   High Resolution: {measurement['high_resolution']}")
            
            print(f"\n🎚️ Optimization Constraints:")
            print(f"   Min Effect Threshold: {constraints['min_light_effect_threshold']:.1f} lux")
            print(f"   Confidence Threshold: {constraints['confidence_threshold']:.1f}")
            print(f"   Power Efficiency Weight: {constraints['power_efficiency_weight']:.1f}")
        else:
            recommendations = calibrator.get_calibration_schedule_recommendations()
            print(f"\n💡 Recommendations:")
            for tip in recommendations['preparation_tips'][:2]:
                print(f"   • {tip}")
        
        # Show how light detection would vary
        print(f"\n🔍 Light Detection Analysis:")
        demonstrate_light_detection_under_conditions(scenario['readings'], conditions)
        
        print("\n" + "=" * 70)
    
    # Summary comparison
    print(f"\n📈 CALIBRATION FEASIBILITY COMPARISON")
    print("-" * 50)
    for scenario in scenarios:
        conditions = calibrator.ambient_analyzer.analyze_current_conditions(scenario['readings'])
        feasibility_bar = "█" * int(conditions.calibration_feasibility * 20)
        feasibility_empty = "░" * (20 - int(conditions.calibration_feasibility * 20))
        print(f"{scenario['name'][:25]:<25} │{feasibility_bar}{feasibility_empty}│ {conditions.calibration_feasibility:.2f}")

def demonstrate_light_detection_under_conditions(readings, conditions):
    """Show how light detection varies under different ambient conditions."""
    
    # Simulate a 50W LED light effect under different conditions
    base_light_effect = 200  # lux at close range in dark conditions
    
    # Calculate actual detectable effect based on ambient conditions
    avg_ambient = sum(readings.values()) / len(readings)
    
    # Signal-to-noise calculation
    if avg_ambient < 50:
        # Dark conditions - excellent detection
        detectable_effect = base_light_effect
        detection_quality = "Excellent"
        confidence = 0.95
    elif avg_ambient < 500:
        # Moderate ambient - good detection with some reduction
        detectable_effect = base_light_effect * 0.8
        detection_quality = "Good"
        confidence = 0.85
    elif avg_ambient < 2000:
        # Bright ambient - reduced detection
        detectable_effect = base_light_effect * 0.4
        detection_quality = "Reduced"
        confidence = 0.60
    elif avg_ambient < 5000:
        # Very bright - poor detection
        detectable_effect = base_light_effect * 0.15
        detection_quality = "Poor"
        confidence = 0.30
    else:
        # Extremely bright - minimal detection
        detectable_effect = base_light_effect * 0.05
        detection_quality = "Minimal"
        confidence = 0.10
    
    # Calculate signal-to-noise ratio
    if avg_ambient > 0:
        snr = detectable_effect / (avg_ambient * 0.1)  # Assume 10% noise
    else:
        snr = float('inf')
    
    print(f"   50W LED Light Detection:")
    print(f"   • Detectable Effect: {detectable_effect:.1f} lux")
    print(f"   • Signal-to-Noise: {snr:.1f}")
    print(f"   • Detection Quality: {detection_quality}")
    print(f"   • Confidence: {confidence:.0%}")
    
    # Show percentage of lights that would be detectable
    light_powers = [25, 50, 75, 100, 150]  # Watts
    detectable_count = 0
    
    for power in light_powers:
        scaled_effect = detectable_effect * (power / 50)  # Scale by power
        if scaled_effect > avg_ambient * 0.05:  # Must be >5% of ambient to detect
            detectable_count += 1
    
    detection_rate = detectable_count / len(light_powers)
    print(f"   • Lights Detectable: {detectable_count}/{len(light_powers)} ({detection_rate:.0%})")

def main():
    """Main demonstration function."""
    try:
        demonstrate_ambient_scenarios()
        
        print(f"\n🎯 KEY TAKEAWAYS:")
        print("1. **Dark conditions (night)**: Perfect for calibration")
        print("2. **Dawn/dusk**: Excellent with minor adjustments")
        print("3. **Overcast days**: Good calibration possible")
        print("4. **Sunny conditions**: Poor accuracy, may defer")
        print("5. **Variable light**: High variation reduces reliability")
        print("\n💡 The system automatically adapts measurement parameters")
        print("   and provides intelligent scheduling recommendations!")
        
    except Exception as e:
        print(f"❌ Error in demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())