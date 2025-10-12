#!/usr/bin/env python3
"""
Demonstration of DLI tracking and configurable decision-making features.
"""

import json
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from control.light_decision_engine import LightDecisionEngine, DLITracker

def demonstrate_dli_and_config_features():
    """Demonstrate the new DLI tracking and configuration features."""
    
    print("🌱 DLI TRACKING & CONFIGURABLE LIGHT CONTROL DEMONSTRATION")
    print("=" * 80)
    
    # Load configurations
    data_dir = Path('data')
    
    # Load test configurations
    zones_config = load_zones_config()
    lights_config = load_lights_config()
    sensors_config = load_sensors_config()
    calibration_data = load_calibration_data()
    
    # Initialize decision engine
    decision_engine = LightDecisionEngine(
        calibration_data=calibration_data,
        zones_config=zones_config,
        lights_config=lights_config,
        sensors_config=sensors_config
    )
    
    print("📊 CURRENT CONFIGURATION")
    print("-" * 40)
    
    # Display time-of-use pricing
    print("⚡ Time-of-Use Energy Pricing:")
    for tier, config in decision_engine.time_of_use_pricing.items():
        hours_range = f"{min(config['hours']):02d}:00 - {max(config['hours']):02d}:59"
        print(f"   {tier.title()}: {config['multiplier']}x cost ({hours_range})")
    
    print(f"\n💰 Base Energy Cost: ${decision_engine.decision_params['energy_cost_per_kwh']:.3f}/kWh")
    
    # Display growth schedules
    print("\n🌿 Growth Schedules:")
    for crop, schedule in decision_engine.growth_schedules.items():
        print(f"   {crop.title()}:")
        print(f"     Light Period: {schedule['preferred_start_time']} - {schedule['preferred_end_time']}")
        print(f"     Target DLI: {schedule['target_dli']} mol/m²/day")
        print(f"     Duration: {schedule['light_hours_per_day']} hours")
    
    # Display zone-specific DLI configurations
    print("\n🏭 Zone-Specific DLI Configuration:")
    for zone_key, zone_config in zones_config.get('zones', {}).items():
        dli_config = zone_config.get('dli_config', {})
        print(f"   {zone_key} ({zone_config.get('crop_type', 'unknown')}):")
        print(f"     Target DLI: {dli_config.get('target_dli', 'from crop schedule')} mol/m²/day")
        print(f"     Light Period: {dli_config.get('morning_start_time', 'from schedule')} - {dli_config.get('evening_end_time', 'from schedule')}")
        print(f"     Priority: {dli_config.get('priority', 'medium')}")
    
    print("\n" + "=" * 80)
    print("📈 DLI TRACKING SIMULATION")
    print("-" * 40)
    
    # Simulate DLI tracking throughout a day
    simulate_daily_dli_tracking(decision_engine)
    
    print("\n" + "=" * 80)
    print("🧠 DECISION MAKING WITH DLI FACTORS")
    print("-" * 40)
    
    # Demonstrate decision making at different DLI progress levels
    demonstrate_dli_decision_scenarios(decision_engine)
    
    print("\n" + "=" * 80)
    print("⚙️ CONFIGURATION MANAGEMENT")
    print("-" * 40)
    
    # Demonstrate configuration updates
    demonstrate_configuration_updates(decision_engine)

def simulate_daily_dli_tracking(decision_engine):
    """Simulate DLI tracking throughout a day."""
    
    # Get today's date
    today = date.today()
    
    # Simulate readings throughout the day
    start_time = datetime.combine(today, datetime.min.time().replace(hour=6))
    
    print("🌅 Simulating DLI accumulation throughout the day...")
    print()
    
    for hour_offset in [0, 2, 4, 6, 8, 10, 12]:  # Every 2 hours from 6 AM
        current_time = start_time + timedelta(hours=hour_offset)
        
        # Simulate light readings for each zone
        sensor_readings = {
            'sensor_1': 800 + hour_offset * 50,  # Gradual increase
            'sensor_2': 900 + hour_offset * 60,
            'sensor_3': 750 + hour_offset * 45
        }
        
        # Make decisions (this will update DLI tracking)
        decisions = decision_engine.make_light_decisions(sensor_readings, current_time)
        
        # Get current DLI status
        dli_status = decision_engine.get_dli_status()
        
        print(f"⏰ {current_time.strftime('%I:%M %p')}:")
        
        for zone_key, status in dli_status.items():
            crop_type = status['crop_type']
            current_dli = status['current_dli']
            target_dli = status['target_dli']
            progress = status['progress_percent']
            remaining_hours = status['remaining_hours']
            
            # Find decisions for lights in this zone
            zone_lights = [d for d in decisions if decision_engine.lights_config.get(d.light_id, {}).get('zone_key') == zone_key]
            lights_on = sum(1 for d in zone_lights if d.should_be_on)
            
            status_icon = "✅" if status['is_target_met'] else "🔄" if progress > 70 else "⚠️"
            
            print(f"   {status_icon} {zone_key} ({crop_type}): {current_dli:.1f}/{target_dli:.1f} mol/m² ({progress:.0f}%)")
            print(f"       Lights ON: {lights_on}/{len(zone_lights)} | Remaining: {remaining_hours:.1f}h")
        
        print()

def demonstrate_dli_decision_scenarios(decision_engine):
    """Demonstrate how DLI affects decision making."""
    
    scenarios = [
        {
            "name": "Early Morning - Low DLI",
            "time": datetime.now().replace(hour=7, minute=0),
            "description": "Start of day, DLI accumulation just beginning"
        },
        {
            "name": "Mid-Day - Moderate DLI",
            "time": datetime.now().replace(hour=14, minute=0),
            "description": "DLI targets partially met, balance efficiency vs. completion"
        },
        {
            "name": "Late Evening - High DLI",
            "time": datetime.now().replace(hour=20, minute=0),
            "description": "DLI targets mostly met, avoid over-exposure"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 {scenario['name']}")
        print(f"   {scenario['description']}")
        print("-" * 60)
        
        # Sensor readings that would produce different DLI levels
        sensor_readings = {
            'sensor_1': 600, 'sensor_2': 650, 'sensor_3': 550
        }
        
        # Make decisions
        decisions = decision_engine.make_light_decisions(sensor_readings, scenario['time'])
        
        # Get DLI status
        dli_status = decision_engine.get_dli_status()
        
        # Display results
        lights_on = [d for d in decisions if d.should_be_on]
        total_power = sum(d.power_consumption for d in lights_on)
        
        print(f"💡 Decision Summary:")
        print(f"   Lights ON: {len(lights_on)}/{len(decisions)}")
        print(f"   Total Power: {total_power:.1f}W")
        
        print(f"\n📊 DLI Influence on Decisions:")
        for zone_key, status in dli_status.items():
            zone_decisions = [d for d in decisions if decision_engine.lights_config.get(d.light_id, {}).get('zone_key') == zone_key]
            zone_lights_on = [d for d in zone_decisions if d.should_be_on]
            
            # Check if DLI was a contributing factor
            dli_factors = []
            for decision in zone_decisions:
                if decision.contributing_factors:
                    for factor in decision.contributing_factors:
                        if 'DLI' in factor:
                            dli_factors.append(factor)
            
            print(f"   {zone_key}: {len(zone_lights_on)}/{len(zone_decisions)} lights ON")
            print(f"     DLI Progress: {status['progress_percent']:.0f}% ({status['current_dli']:.1f}/{status['target_dli']:.1f})")
            if dli_factors:
                print(f"     DLI Factors: {', '.join(dli_factors[:2])}")

def demonstrate_configuration_updates(decision_engine):
    """Demonstrate configuration management capabilities."""
    
    print("🔧 Configuration Update Examples:")
    print()
    
    # Example 1: Update time-of-use pricing
    print("1. Update Time-of-Use Pricing:")
    new_pricing = {
        'off_peak': {'multiplier': 0.8, 'hours': list(range(23, 24)) + list(range(0, 7))},
        'standard': {'multiplier': 1.2, 'hours': list(range(7, 17))},
        'peak': {'multiplier': 2.5, 'hours': list(range(17, 23))}
    }
    
    print("   Before:", decision_engine.time_of_use_pricing['peak']['multiplier'])
    decision_engine.update_time_of_use_pricing(new_pricing)
    print("   After:", decision_engine.time_of_use_pricing['peak']['multiplier'])
    
    # Example 2: Update growth schedule
    print("\n2. Update Growth Schedule for Lettuce:")
    new_schedule = {
        'light_hours_per_day': 16,
        'preferred_start_time': '05:30',
        'preferred_end_time': '21:30',
        'intensity_curve': 'aggressive_ramp',
        'target_dli': 16.0
    }
    
    print(f"   Before DLI target: {decision_engine.growth_schedules['lettuce']['target_dli']}")
    decision_engine.update_growth_schedule('lettuce', new_schedule)
    print(f"   After DLI target: {decision_engine.growth_schedules['lettuce']['target_dli']}")
    
    # Example 3: Update energy cost
    print("\n3. Update Base Energy Cost:")
    print(f"   Before: ${decision_engine.decision_params['energy_cost_per_kwh']:.3f}/kWh")
    decision_engine.update_energy_cost(0.15)
    print(f"   After: ${decision_engine.decision_params['energy_cost_per_kwh']:.3f}/kWh")
    
    print("\n✅ All configuration updates saved to file automatically!")

def load_zones_config():
    """Load zones configuration."""
    zones_file = Path('data/zones.json')
    if zones_file.exists():
        with open(zones_file, 'r') as f:
            return json.load(f)
    return {"grid_size": {"rows": 4, "cols": 6}, "zones": {}}

def load_lights_config():
    """Load lights configuration."""
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
            "gpio_pin": 18,
            "max_ppfd": 200
        },
        "grow_panel_1": {
            "name": "High-Power Grow Panel 1", 
            "type": "GROW_PANEL",
            "zone_key": "A2",
            "power_watts": 100,
            "gpio_pin": 19,
            "max_ppfd": 300
        },
        "basic_light_1": {
            "name": "Basic White LED 1",
            "type": "LED_BASIC", 
            "zone_key": "B1",
            "power_watts": 25,
            "gpio_pin": 20,
            "max_ppfd": 150
        },
        "rgb_array_1": {
            "name": "RGB LED Array 1",
            "type": "RGB_ARRAY",
            "zone_key": "B2",
            "power_watts": 60,
            "gpio_pin": 21,
            "max_ppfd": 250
        }
    }

def load_sensors_config():
    """Load sensors configuration."""
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

def load_calibration_data():
    """Load calibration data."""
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
            "rgb_array_1": {"sensor_1": 120, "sensor_2": 110, "sensor_3": 100}
        },
        "sensor_zones": {"sensor_1": "A1", "sensor_2": "A2", "sensor_3": "B1"}
    }

def main():
    """Main demonstration function."""
    try:
        demonstrate_dli_and_config_features()
        
        print(f"\n🎯 KEY NEW FEATURES:")
        print("1. **Daily Light Integral (DLI)**: Tracks cumulative light per zone/day")
        print("2. **Configurable Time-of-Use**: Customizable energy pricing periods")
        print("3. **Zone-Specific Timing**: Individual morning start times per zone")
        print("4. **Real-Time DLI Decisions**: Light intensity based on DLI progress")
        print("5. **Configuration Management**: Save/load all settings automatically")
        
        print(f"\n💡 DLI helps ensure optimal daily light exposure while")
        print("   configurable pricing and timing adapt to your specific needs!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error in demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())