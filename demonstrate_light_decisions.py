#!/usr/bin/env python3
"""
Demonstration of Intelligent Light Decision Making System.
Shows how the system decides whether to turn lights on/off based on multiple factors.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from control.light_decision_engine import LightDecisionEngine, LightDecisionReason

def demonstrate_decision_scenarios():
    """Demonstrate light decision making under different scenarios."""
    
    print("🧠 INTELLIGENT LIGHT DECISION MAKING DEMONSTRATION")
    print("=" * 80)
    
    # Load test configurations
    data_dir = Path('data')
    
    # Load existing test data or create mock data
    zones_config = load_or_create_zones_config()
    lights_config = load_or_create_lights_config()
    sensors_config = load_or_create_sensors_config()
    calibration_data = load_or_create_calibration_data()
    
    # Initialize decision engine
    decision_engine = LightDecisionEngine(
        calibration_data=calibration_data,
        zones_config=zones_config,
        lights_config=lights_config,
        sensors_config=sensors_config
    )
    
    # Define different scenarios
    scenarios = [
        {
            "name": "🌅 Morning Startup (6:00 AM)",
            "time": datetime.now().replace(hour=6, minute=0),
            "sensor_readings": {"sensor_1": 25, "sensor_2": 30, "sensor_3": 20},
            "description": "Early morning, plants need light to start photosynthesis"
        },
        {
            "name": "☀️ Sunny Midday (12:00 PM)",
            "time": datetime.now().replace(hour=12, minute=0),
            "sensor_readings": {"sensor_1": 5000, "sensor_2": 5500, "sensor_3": 4800},
            "description": "Bright natural light, artificial lights may not be needed"
        },
        {
            "name": "🌤️ Cloudy Afternoon (3:00 PM)",
            "time": datetime.now().replace(hour=15, minute=0),
            "sensor_readings": {"sensor_1": 800, "sensor_2": 750, "sensor_3": 900},
            "description": "Moderate natural light, may need supplemental artificial light"
        },
        {
            "name": "🌆 Evening Peak Growth (6:00 PM)",
            "time": datetime.now().replace(hour=18, minute=0),
            "sensor_readings": {"sensor_1": 100, "sensor_2": 120, "sensor_3": 80},
            "description": "Peak energy rates but important growth time"
        },
        {
            "name": "🌙 Night Rest Period (10:00 PM)",
            "time": datetime.now().replace(hour=22, minute=0),
            "sensor_readings": {"sensor_1": 5, "sensor_2": 8, "sensor_3": 3},
            "description": "Night time, most plants should rest"
        },
        {
            "name": "⚡ Peak Energy Rates (7:00 PM)",
            "time": datetime.now().replace(hour=19, minute=0),
            "sensor_readings": {"sensor_1": 50, "sensor_2": 45, "sensor_3": 60},
            "description": "High electricity costs, energy efficiency is critical"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 SCENARIO {i}: {scenario['name']}")
        print(f"   Time: {scenario['time'].strftime('%I:%M %p')}")
        print(f"   Context: {scenario['description']}")
        print("-" * 60)
        
        # Make decisions for this scenario
        decisions = decision_engine.make_light_decisions(
            scenario['sensor_readings'], 
            scenario['time']
        )
        
        # Display summary
        lights_on = [d for d in decisions if d.should_be_on]
        total_power = sum(d.power_consumption for d in lights_on)
        avg_confidence = sum(d.confidence for d in decisions) / len(decisions)
        
        print(f"📊 Decision Summary:")
        print(f"   Lights ON: {len(lights_on)}/{len(decisions)}")
        print(f"   Total Power: {total_power:.1f}W")
        print(f"   Average Confidence: {avg_confidence:.0%}")
        
        # Group decisions by reason
        reason_counts = {}
        for decision in decisions:
            reason = decision.primary_reason.value.replace('_', ' ').title()
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        print(f"\n🎯 Decision Reasons:")
        for reason, count in reason_counts.items():
            print(f"   {reason}: {count} lights")
        
        # Show individual light decisions
        print(f"\n💡 Individual Light Decisions:")
        for decision in decisions:
            light_name = lights_config[decision.light_id].get('name', decision.light_id)
            status = "ON" if decision.should_be_on else "OFF"
            
            if decision.should_be_on:
                status += f" ({decision.intensity_percent:.0f}%)"
            
            confidence_bar = "█" * int(decision.confidence * 10)
            confidence_empty = "░" * (10 - int(decision.confidence * 10))
            
            print(f"   {light_name:<25} │ {status:<12} │ {confidence_bar}{confidence_empty} │ {decision.confidence:.0%}")
            
            # Show key factors for lights that are on
            if decision.should_be_on and decision.contributing_factors:
                main_factors = decision.contributing_factors[:2]  # Show top 2 factors
                factors_text = ", ".join(main_factors)
                if len(factors_text) > 50:
                    factors_text = factors_text[:47] + "..."
                print(f"     └─ {factors_text}")
        
        # Show energy and efficiency analysis
        print(f"\n⚡ Energy Analysis:")
        energy_cost = total_power * decision_engine.decision_params['energy_cost_per_kwh'] / 1000
        energy_multiplier = decision_engine._get_energy_cost_multiplier(scenario['time'].hour)
        actual_cost = energy_cost * energy_multiplier
        
        print(f"   Base Energy Cost: ${energy_cost:.3f}/hour")
        print(f"   Time-of-Use Multiplier: {energy_multiplier:.1f}x")
        print(f"   Actual Cost: ${actual_cost:.3f}/hour")
        
        if energy_multiplier > 1.5:
            print(f"   💰 High energy rates - efficiency prioritized")
        
        print("\n" + "=" * 80)
    
    # Demonstrate decision explanations
    print(f"\n📖 DETAILED DECISION EXPLANATIONS")
    print("=" * 60)
    
    # Pick an interesting scenario for detailed explanation
    evening_scenario = scenarios[3]  # Evening peak growth
    evening_decisions = decision_engine.make_light_decisions(
        evening_scenario['sensor_readings'], 
        evening_scenario['time']
    )
    
    for decision in evening_decisions[:2]:  # Show first 2 lights
        light_name = lights_config[decision.light_id].get('name', decision.light_id)
        print(f"\n🔍 Detailed Decision for: {light_name}")
        print("-" * 40)
        
        explanation = decision_engine.get_decision_explanation(decision.light_id, decision)
        print(explanation)

def load_or_create_zones_config():
    """Load zones config or create mock data."""
    zones_file = Path('data/zones.json')
    if zones_file.exists():
        with open(zones_file, 'r') as f:
            return json.load(f)
    
    # Mock zones config
    return {
        "grid_size": {"rows": 4, "cols": 6},
        "zones": {
            "A1": {
                "name": "Lettuce Section",
                "crop_type": "lettuce",
                "growth_stage": "vegetative",
                "light_spectrum": {"par_target": 180, "color_temperature": 4000}
            },
            "A2": {
                "name": "Basil Garden", 
                "crop_type": "basil",
                "growth_stage": "flowering",
                "light_spectrum": {"par_target": 220, "color_temperature": 4500}
            },
            "B1": {
                "name": "Tomato Seedlings",
                "crop_type": "tomatoes", 
                "growth_stage": "seedling",
                "light_spectrum": {"par_target": 150, "color_temperature": 3800}
            }
        }
    }

def load_or_create_lights_config():
    """Load lights config or create mock data."""
    lights_file = Path('data/lights.json')
    if lights_file.exists():
        with open(lights_file, 'r') as f:
            return json.load(f).get('lights', {})
    
    # Mock lights config
    return {
        "led_strip_1": {
            "name": "Full Spectrum LED Strip 1",
            "type": "LED_STRIP",
            "zone_key": "A1",
            "power_watts": 45,
            "gpio_pin": 18
        },
        "grow_panel_1": {
            "name": "High-Power Grow Panel 1", 
            "type": "GROW_PANEL",
            "zone_key": "A2",
            "power_watts": 100,
            "gpio_pin": 19
        },
        "basic_light_1": {
            "name": "Basic White LED 1",
            "type": "LED_BASIC", 
            "zone_key": "B1",
            "power_watts": 25,
            "gpio_pin": 20
        },
        "backup_light_1": {
            "name": "Backup Light",
            "type": "LED_BASIC",
            "zone_key": None,
            "power_watts": 30,
            "gpio_pin": 22
        }
    }

def load_or_create_sensors_config():
    """Load sensors config or create mock data."""
    sensors_file = Path('data/light_sensors.json')
    if sensors_file.exists():
        with open(sensors_file, 'r') as f:
            return json.load(f).get('sensors', {})
    
    # Mock sensors config
    return {
        "sensor_1": {"name": "BH1750 Sensor A1", "type": "BH1750", "zone_key": "A1"},
        "sensor_2": {"name": "TSL2591 Sensor A2", "type": "TSL2591", "zone_key": "A2"},
        "sensor_3": {"name": "VEML7700 Sensor B1", "type": "VEML7700", "zone_key": "B1"}
    }

def load_or_create_calibration_data():
    """Load calibration data or create mock data."""
    cal_file = Path('data/light_calibration.json')
    if cal_file.exists():
        with open(cal_file, 'r') as f:
            return json.load(f)
    
    # Mock calibration data
    return {
        "timestamp": datetime.now().isoformat(),
        "baseline": {"sensor_1": 10, "sensor_2": 15, "sensor_3": 8},
        "light_effects": {
            "led_strip_1": {"sensor_1": 150, "sensor_2": 80, "sensor_3": 60},
            "grow_panel_1": {"sensor_1": 100, "sensor_2": 200, "sensor_3": 90},
            "basic_light_1": {"sensor_1": 70, "sensor_2": 60, "sensor_3": 120},
            "backup_light_1": {"sensor_1": 80, "sensor_2": 70, "sensor_3": 85}
        },
        "sensor_zones": {"sensor_1": "A1", "sensor_2": "A2", "sensor_3": "B1"}
    }

def main():
    """Main demonstration function."""
    try:
        demonstrate_decision_scenarios()
        
        print(f"\n🎯 KEY DECISION FACTORS:")
        print("1. **Plant Requirements**: Crop type, growth stage, and light schedule")
        print("2. **Ambient Conditions**: Natural light levels and time of day")
        print("3. **Energy Efficiency**: Time-of-use pricing and power consumption")
        print("4. **Sensor Feedback**: Current light levels and historical performance")
        print("5. **Zone Optimization**: Avoiding conflicts and maximizing efficiency")
        print("6. **Confidence Scoring**: Reliability of each decision")
        
        print(f"\n💡 The decision engine considers all these factors simultaneously")
        print("   to make intelligent, context-aware light control decisions!")
        
    except Exception as e:
        print(f"❌ Error in demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())