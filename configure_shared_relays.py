#!/usr/bin/env python3
"""
Shared Relay Configuration and Testing Tool

This tool helps you set up and test shared relay configurations for cost-effective
light control when multiple lights can be controlled together.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from control.enhanced_relay import EnhancedLightController, load_relay_groups_config, save_relay_groups_config


def print_header():
    """Print tool header and explanation."""
    print("💰 Shared Relay Configuration Tool")
    print("=" * 50)
    print()
    print("🔧 SHARED RELAY BENEFITS:")
    print("   • Reduce hardware costs - fewer relay boards needed")
    print("   • Simplify wiring for lights in same area")
    print("   • Lower GPIO pin usage on Raspberry Pi")
    print("   • Perfect for lights that work together")
    print()
    print("⚠️  SHARED RELAY LIMITATIONS:")
    print("   • All lights in group turn on/off together")
    print("   • No individual control within the group")
    print("   • Total power must be within relay rating")
    print()
    print("💡 IDEAL USE CASES:")
    print("   • Lights in same growing zone")
    print("   • Backup/redundant lights")
    print("   • Seed starting area lights")
    print("   • Cost-sensitive installations")
    print()


def load_lights_config(data_dir: str = "data") -> Dict:
    """Load lights configuration."""
    lights_file = Path(data_dir) / "lights.json"
    if lights_file.exists():
        with open(lights_file, 'r') as f:
            return json.load(f).get('lights', {})
    return {}


def display_current_configuration(data_dir: str = "data"):
    """Display current light and relay configuration."""
    print("📋 CURRENT CONFIGURATION")
    print("-" * 30)
    
    lights_config = load_lights_config(data_dir)
    relay_groups_config = load_relay_groups_config(data_dir)
    
    print(f"Total lights configured: {len(lights_config)}")
    print(f"Light groups configured: {len(relay_groups_config)}")
    print()
    
    # Show individual lights
    individual_lights = []
    grouped_lights = set()
    
    for group_config in relay_groups_config.values():
        grouped_lights.update(group_config.get('lights', []))
    
    for light_id in lights_config.keys():
        if light_id not in grouped_lights:
            individual_lights.append(light_id)
    
    print(f"🔆 INDIVIDUAL LIGHTS ({len(individual_lights)}):")
    for light_id in individual_lights:
        light = lights_config[light_id]
        pin = light.get('relay_pin') or light.get('gpio_pin', 'No pin')
        power = light.get('power_watts', 0)
        print(f"   • {light.get('name', light_id)} (Pin: {pin}, {power}W)")
    
    print()
    print(f"👥 LIGHT GROUPS ({len(relay_groups_config)}):")
    for group_id, group in relay_groups_config.items():
        lights = group.get('lights', [])
        pin = group.get('relay_pin', 'No pin')
        total_power = sum(lights_config.get(lid, {}).get('power_watts', 0) for lid in lights)
        print(f"   • {group.get('description', group_id)}")
        print(f"     - Relay Pin: {pin}")
        print(f"     - Lights: {', '.join(lights)} ({len(lights)} lights)")
        print(f"     - Total Power: {total_power}W")
        print(f"     - Reasoning: {group.get('cost_reasoning', 'Not specified')}")
        print()


def suggest_relay_groups(data_dir: str = "data") -> Dict:
    """Analyze lights and suggest potential relay groups."""
    lights_config = load_lights_config(data_dir)
    
    if not lights_config:
        print("❌ No lights configuration found!")
        return {}
    
    controller = EnhancedLightController(lights_config, {})
    suggestions = controller.optimize_relay_grouping(max_lights_per_group=3)
    
    print("🧠 RELAY GROUPING SUGGESTIONS")
    print("-" * 30)
    
    if not suggestions['potential_groups']:
        print("No beneficial groupings found with current configuration.")
        return suggestions
    
    print(f"Potential relay savings: {suggestions['estimated_savings']} relays")
    print(f"Cost savings: {suggestions['cost_savings_percent']:.1f}%")
    print()
    
    for i, suggestion in enumerate(suggestions['potential_groups'], 1):
        print(f"💡 SUGGESTION {i}: {suggestion['description']}")
        print(f"   Lights: {', '.join(suggestion['lights'])}")
        print(f"   Light count: {suggestion['light_count']}")
        print(f"   Total power: {suggestion['total_power_watts']}W")
        print(f"   Relays saved: {suggestion['relays_saved']}")
        print()
    
    return suggestions


def create_relay_group_interactive(data_dir: str = "data"):
    """Interactive relay group creation."""
    lights_config = load_lights_config(data_dir)
    relay_groups_config = load_relay_groups_config(data_dir)
    
    print("🛠️  CREATE NEW RELAY GROUP")
    print("-" * 25)
    
    # Show available lights
    grouped_lights = set()
    for group in relay_groups_config.values():
        grouped_lights.update(group.get('lights', []))
    
    available_lights = [lid for lid in lights_config.keys() if lid not in grouped_lights]
    
    if not available_lights:
        print("❌ No available lights to group (all are already grouped or configured)")
        return
    
    print("Available lights:")
    for i, light_id in enumerate(available_lights, 1):
        light = lights_config[light_id]
        power = light.get('power_watts', 0)
        zone = light.get('zone_key', 'No zone')
        print(f"   {i}. {light.get('name', light_id)} ({power}W, Zone: {zone})")
    
    print()
    
    # Get group details
    try:
        group_id = input("Enter group ID (e.g., 'seed_area_lights'): ").strip()
        if not group_id:
            print("❌ Group ID cannot be empty")
            return
        
        if group_id in relay_groups_config:
            print(f"❌ Group ID '{group_id}' already exists")
            return
        
        description = input("Enter description: ").strip()
        if not description:
            description = f"Light group {group_id}"
        
        relay_pin = input("Enter relay GPIO pin number: ").strip()
        try:
            relay_pin = int(relay_pin)
        except ValueError:
            print("❌ Invalid pin number")
            return
        
        print("\nSelect lights for this group (enter numbers separated by commas):")
        selected_indices = input("Light numbers: ").strip().split(',')
        
        selected_lights = []
        total_power = 0
        for idx_str in selected_indices:
            try:
                idx = int(idx_str.strip()) - 1
                if 0 <= idx < len(available_lights):
                    light_id = available_lights[idx]
                    selected_lights.append(light_id)
                    total_power += lights_config[light_id].get('power_watts', 0)
                else:
                    print(f"❌ Invalid selection: {idx_str}")
                    return
            except ValueError:
                print(f"❌ Invalid number: {idx_str}")
                return
        
        if len(selected_lights) < 2:
            print("❌ Need at least 2 lights for a group")
            return
        
        # Power check
        if total_power > 500:  # Configurable limit
            confirm = input(f"⚠️  High power ({total_power}W). Continue? (y/N): ")
            if confirm.lower() != 'y':
                return
        
        cost_reasoning = input("Why group these lights together? ").strip()
        if not cost_reasoning:
            cost_reasoning = "Cost savings through shared relay control"
        
        # Create group configuration
        new_group = {
            'description': description,
            'relay_pin': relay_pin,
            'active_high': True,
            'lights': selected_lights,
            'cost_reasoning': cost_reasoning,
            'power_total_watts': total_power,
            'created_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Add to configuration
        relay_groups_config[group_id] = new_group
        save_relay_groups_config(relay_groups_config, data_dir)
        
        print()
        print("✅ RELAY GROUP CREATED SUCCESSFULLY!")
        print(f"   Group: {description}")
        print(f"   Lights: {', '.join(selected_lights)}")
        print(f"   Relay Pin: {relay_pin}")
        print(f"   Total Power: {total_power}W")
        print(f"   Configuration saved to relay_groups.json")
        
    except KeyboardInterrupt:
        print("\n❌ Group creation cancelled")
    except Exception as e:
        print(f"❌ Error creating group: {e}")


def test_relay_groups(data_dir: str = "data"):
    """Test relay group functionality."""
    lights_config = load_lights_config(data_dir)
    relay_groups_config = load_relay_groups_config(data_dir)
    
    if not relay_groups_config:
        print("❌ No relay groups configured to test")
        return
    
    print("🧪 TESTING RELAY GROUPS")
    print("-" * 22)
    
    controller = EnhancedLightController(lights_config, relay_groups_config)
    
    # Test each group
    for group_id, group_config in relay_groups_config.items():
        lights = group_config.get('lights', [])
        description = group_config.get('description', group_id)
        
        print(f"\n🔬 Testing: {description}")
        print(f"   Lights in group: {', '.join(lights)}")
        
        try:
            # Test turning on first light in group
            first_light = lights[0]
            print(f"   Turning ON {first_light}...")
            success = controller.turn_on_light(first_light)
            
            if success:
                # Check states of all lights in group
                states = controller.get_all_light_states()
                group_states = {lid: states.get(lid, False) for lid in lights}
                print(f"   Group states: {group_states}")
                
                if all(group_states.values()):
                    print("   ✅ All lights in group turned ON (correct shared behavior)")
                else:
                    print("   ❌ Not all lights turned on - check configuration")
            else:
                print("   ❌ Failed to turn on light")
            
            time.sleep(2)
            
            # Test turning off
            print(f"   Turning OFF {first_light}...")
            controller.turn_off_light(first_light)
            
            states = controller.get_all_light_states()
            group_states = {lid: states.get(lid, True) for lid in lights}
            print(f"   Group states: {group_states}")
            
            if not any(group_states.values()):
                print("   ✅ All lights in group turned OFF (correct shared behavior)")
            else:
                print("   ❌ Some lights still on - check configuration")
                
        except Exception as e:
            print(f"   ❌ Error testing group: {e}")
        
        time.sleep(1)
    
    # Test individual control vs group behavior
    print(f"\n🔀 TESTING GROUP BEHAVIOR:")
    all_lights = []
    for group in relay_groups_config.values():
        all_lights.extend(group.get('lights', []))
    
    if len(all_lights) >= 2:
        light1, light2 = all_lights[0], all_lights[1]
        
        print(f"   Testing individual light requests...")
        print(f"   Requesting {light1} ON, {light2} OFF...")
        
        controller.turn_on_light(light1)
        controller.turn_off_light(light2)
        
        states = controller.get_all_light_states()
        print(f"   Resulting states: {light1}={states.get(light1)}, {light2}={states.get(light2)}")
        
        if light1 in controller.light_to_group and light2 in controller.light_to_group:
            if controller.light_to_group[light1] == controller.light_to_group[light2]:
                print("   ✅ Lights in same group share state (expected)")
            else:
                print("   ✅ Lights in different groups have independent control")
        
        controller.turn_off_all_lights()
    
    controller.cleanup()
    print("\n✅ Relay group testing completed!")


def get_relay_usage_report(data_dir: str = "data"):
    """Generate comprehensive relay usage report."""
    lights_config = load_lights_config(data_dir)
    relay_groups_config = load_relay_groups_config(data_dir)
    
    controller = EnhancedLightController(lights_config, relay_groups_config)
    report = controller.get_relay_usage_report()
    
    print("📊 RELAY USAGE EFFICIENCY REPORT")
    print("-" * 35)
    print()
    print(f"💡 Total lights: {report['total_lights']}")
    print(f"🔧 Total relays used: {report['total_relays_used']}")
    print(f"💰 Relays saved: {report['relays_saved']}")
    print(f"📈 Cost savings: {report['cost_savings_percent']:.1f}%")
    print(f"⚡ Efficiency ratio: {report['efficiency_ratio']:.2f}")
    print()
    
    print("📋 BREAKDOWN:")
    print(f"   Individual relays: {report['lights_with_individual_relays']}")
    print(f"   Grouped lights: {report['lights_in_groups']}")
    print(f"   Light groups: {report['light_groups']}")
    print()
    
    if report['group_details']:
        print("👥 GROUP EFFICIENCY:")
        for group_id, details in report['group_details'].items():
            efficiency = details['cost_efficiency']['efficiency_ratio']
            print(f"   • {details['description']}: {efficiency} lights per relay")
    
    controller.cleanup()


def main_menu():
    """Main interactive menu."""
    data_dir = "data"
    
    while True:
        print("\n" + "="*50)
        print("💰 SHARED RELAY CONFIGURATION TOOL")
        print("="*50)
        print("1. 📋 View current configuration")
        print("2. 🧠 Get relay grouping suggestions")
        print("3. 🛠️  Create new relay group")
        print("4. 🧪 Test relay groups")
        print("5. 📊 Relay usage efficiency report")
        print("6. ❌ Exit")
        print()
        
        try:
            choice = input("Select option (1-6): ").strip()
            
            if choice == '1':
                display_current_configuration(data_dir)
            elif choice == '2':
                suggest_relay_groups(data_dir)
            elif choice == '3':
                create_relay_group_interactive(data_dir)
            elif choice == '4':
                test_relay_groups(data_dir)
            elif choice == '5':
                get_relay_usage_report(data_dir)
            elif choice == '6':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select 1-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    print_header()
    main_menu()