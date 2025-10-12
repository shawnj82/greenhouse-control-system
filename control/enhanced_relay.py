"""Enhanced relay control system supporting shared relays between multiple lights.

This module provides:
1. Individual relay control per light (original functionality)
2. Shared relay control for multiple lights on same relay
3. Light group management for cost-effective relay sharing
4. Intelligent group switching with status tracking
"""

import json
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from pathlib import Path

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False


class SharedRelay:
    """A relay that can control multiple lights as a group."""
    
    def __init__(self, pin: int, light_ids: List[str], active_high: bool = True):
        self.pin = pin
        self.light_ids = set(light_ids)
        self.active_high = active_high
        self.is_on = False
        
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self.off()
    
    def on(self):
        """Turn on all lights controlled by this relay."""
        if not _HAS_GPIO:
            light_list = ", ".join(self.light_ids)
            print(f"[MOCK] Shared Relay {self.pin} ON (Controls: {light_list})")
        else:
            GPIO.output(self.pin, GPIO.HIGH if self.active_high else GPIO.LOW)
        
        self.is_on = True
    
    def off(self):
        """Turn off all lights controlled by this relay."""
        if not _HAS_GPIO:
            light_list = ", ".join(self.light_ids)
            print(f"[MOCK] Shared Relay {self.pin} OFF (Controls: {light_list})")
        else:
            GPIO.output(self.pin, GPIO.LOW if self.active_high else GPIO.HIGH)
        
        self.is_on = False
    
    def add_light(self, light_id: str):
        """Add a light to this shared relay group."""
        self.light_ids.add(light_id)
    
    def remove_light(self, light_id: str):
        """Remove a light from this shared relay group."""
        self.light_ids.discard(light_id)
    
    def get_controlled_lights(self) -> Set[str]:
        """Get all light IDs controlled by this relay."""
        return self.light_ids.copy()
    
    def cleanup(self):
        """Clean up GPIO resources."""
        if _HAS_GPIO:
            GPIO.cleanup(self.pin)


class IndividualRelay:
    """Traditional individual relay controlling one light."""
    
    def __init__(self, pin: int, light_id: str, active_high: bool = True):
        self.pin = pin
        self.light_id = light_id
        self.active_high = active_high
        self.is_on = False
        
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self.off()
    
    def on(self):
        """Turn on the light."""
        if not _HAS_GPIO:
            print(f"[MOCK] Individual Relay {self.pin} ON (Light: {self.light_id})")
        else:
            GPIO.output(self.pin, GPIO.HIGH if self.active_high else GPIO.LOW)
        
        self.is_on = True
    
    def off(self):
        """Turn off the light."""
        if not _HAS_GPIO:
            print(f"[MOCK] Individual Relay {self.pin} OFF (Light: {self.light_id})")
        else:
            GPIO.output(self.pin, GPIO.LOW if self.active_high else GPIO.HIGH)
        
        self.is_on = False
    
    def cleanup(self):
        """Clean up GPIO resources."""
        if _HAS_GPIO:
            GPIO.cleanup(self.pin)


class LightGroup:
    """Represents a group of lights that share a relay."""
    
    def __init__(self, group_id: str, light_ids: List[str], relay_pin: int, 
                 description: str = "", active_high: bool = True):
        self.group_id = group_id
        self.light_ids = set(light_ids)
        self.relay = SharedRelay(relay_pin, light_ids, active_high)
        self.description = description
        self.desired_states = {light_id: False for light_id in light_ids}
        self.created_at = datetime.now()
    
    def set_light_desired_state(self, light_id: str, should_be_on: bool):
        """Set desired state for a specific light in the group."""
        if light_id in self.light_ids:
            self.desired_states[light_id] = should_be_on
    
    def get_group_decision(self) -> bool:
        """Decide if the shared relay should be on based on individual light desires."""
        # Relay is on if ANY light in the group wants to be on
        return any(self.desired_states.values())
    
    def apply_group_decision(self) -> Dict[str, bool]:
        """Apply the group decision to the relay and return actual states."""
        group_should_be_on = self.get_group_decision()
        
        if group_should_be_on:
            self.relay.on()
        else:
            self.relay.off()
        
        # All lights in the group have the same actual state
        actual_states = {}
        for light_id in self.light_ids:
            actual_states[light_id] = group_should_be_on
        
        return actual_states
    
    def get_status_report(self) -> Dict:
        """Get detailed status of the light group."""
        return {
            'group_id': self.group_id,
            'description': self.description,
            'relay_pin': self.relay.pin,
            'relay_is_on': self.relay.is_on,
            'light_count': len(self.light_ids),
            'lights': list(self.light_ids),
            'desired_states': self.desired_states.copy(),
            'group_decision': self.get_group_decision(),
            'created_at': self.created_at.isoformat(),
            'cost_efficiency': {
                'lights_per_relay': len(self.light_ids),
                'potential_relay_savings': len(self.light_ids) - 1,
                'efficiency_ratio': len(self.light_ids)  # Higher is better
            }
        }
    
    def add_light(self, light_id: str):
        """Add a new light to this group."""
        self.light_ids.add(light_id)
        self.desired_states[light_id] = False
        self.relay.add_light(light_id)
    
    def remove_light(self, light_id: str):
        """Remove a light from this group."""
        self.light_ids.discard(light_id)
        self.desired_states.pop(light_id, None)
        self.relay.remove_light(light_id)


class EnhancedLightController:
    """Enhanced light controller supporting both individual and shared relay control."""
    
    def __init__(self, lights_config: Dict, relay_groups_config: Optional[Dict] = None):
        self.lights_config = lights_config
        self.individual_relays = {}  # light_id -> IndividualRelay
        self.light_groups = {}       # group_id -> LightGroup
        self.light_to_group = {}     # light_id -> group_id
        self.light_to_individual = {}  # light_id -> relay
        
        # Load relay groups configuration
        self.relay_groups_config = relay_groups_config or {}
        
        self._initialize_relay_system()
    
    def _initialize_relay_system(self):
        """Initialize both individual and shared relay systems."""
        
        # First, set up any defined light groups
        for group_id, group_config in self.relay_groups_config.items():
            light_ids = group_config.get('lights', [])
            relay_pin = group_config.get('relay_pin')
            description = group_config.get('description', f"Light group {group_id}")
            active_high = group_config.get('active_high', True)
            
            if relay_pin and light_ids:
                # Validate that all lights exist in lights_config
                valid_lights = [lid for lid in light_ids if lid in self.lights_config]
                if valid_lights:
                    group = LightGroup(group_id, valid_lights, relay_pin, description, active_high)
                    self.light_groups[group_id] = group
                    
                    # Map lights to their group
                    for light_id in valid_lights:
                        self.light_to_group[light_id] = group_id
                    
                    print(f"Created light group '{group_id}': {len(valid_lights)} lights on relay pin {relay_pin}")
        
        # Then set up individual relays for lights not in groups
        for light_id, light_config in self.lights_config.items():
            if light_id not in self.light_to_group:
                # This light is not in a group, check for individual relay
                relay_pin = light_config.get('relay_pin') or light_config.get('gpio_pin')
                if relay_pin:
                    active_high = light_config.get('active_high', True)
                    relay = IndividualRelay(relay_pin, light_id, active_high)
                    self.individual_relays[light_id] = relay
                    self.light_to_individual[light_id] = relay
                    print(f"Created individual relay for light '{light_id}' on pin {relay_pin}")
    
    def turn_on_light(self, light_id: str) -> bool:
        """Turn on a specific light (handles both individual and grouped lights)."""
        if light_id in self.light_to_group:
            # Light is in a group
            group_id = self.light_to_group[light_id]
            group = self.light_groups[group_id]
            group.set_light_desired_state(light_id, True)
            actual_states = group.apply_group_decision()
            return actual_states.get(light_id, False)
        
        elif light_id in self.individual_relays:
            # Light has individual relay
            self.individual_relays[light_id].on()
            return True
        
        else:
            print(f"Warning: No relay control configured for light {light_id}")
            return False
    
    def turn_off_light(self, light_id: str) -> bool:
        """Turn off a specific light (handles both individual and grouped lights)."""
        if light_id in self.light_to_group:
            # Light is in a group
            group_id = self.light_to_group[light_id]
            group = self.light_groups[group_id]
            group.set_light_desired_state(light_id, False)
            actual_states = group.apply_group_decision()
            return not actual_states.get(light_id, True)  # Return True if successfully off
        
        elif light_id in self.individual_relays:
            # Light has individual relay
            self.individual_relays[light_id].off()
            return True
        
        else:
            print(f"Warning: No relay control configured for light {light_id}")
            return False
    
    def turn_on_lights(self, light_ids: List[str]) -> Dict[str, bool]:
        """Turn on multiple lights and return success status for each."""
        results = {}
        for light_id in light_ids:
            results[light_id] = self.turn_on_light(light_id)
        return results
    
    def turn_off_lights(self, light_ids: List[str]) -> Dict[str, bool]:
        """Turn off multiple lights and return success status for each."""
        results = {}
        for light_id in light_ids:
            results[light_id] = self.turn_off_light(light_id)
        return results
    
    def turn_off_all_lights(self):
        """Turn off all lights (both individual and grouped)."""
        # Turn off all individual lights
        for relay in self.individual_relays.values():
            relay.off()
        
        # Turn off all light groups
        for group in self.light_groups.values():
            for light_id in group.light_ids:
                group.set_light_desired_state(light_id, False)
            group.apply_group_decision()
    
    def get_light_state(self, light_id: str) -> Optional[bool]:
        """Get the current actual state of a light."""
        if light_id in self.light_to_group:
            group_id = self.light_to_group[light_id]
            group = self.light_groups[group_id]
            return group.relay.is_on
        
        elif light_id in self.individual_relays:
            return self.individual_relays[light_id].is_on
        
        return None
    
    def get_all_light_states(self) -> Dict[str, bool]:
        """Get current states of all lights."""
        states = {}
        
        # Get states from individual relays
        for light_id, relay in self.individual_relays.items():
            states[light_id] = relay.is_on
        
        # Get states from groups
        for group in self.light_groups.values():
            for light_id in group.light_ids:
                states[light_id] = group.relay.is_on
        
        return states
    
    def get_group_status(self) -> Dict[str, Dict]:
        """Get status of all light groups."""
        return {
            group_id: group.get_status_report() 
            for group_id, group in self.light_groups.items()
        }
    
    def get_relay_usage_report(self) -> Dict:
        """Get a comprehensive report of relay usage and efficiency."""
        individual_count = len(self.individual_relays)
        total_lights = len(self.lights_config)
        grouped_lights = sum(len(group.light_ids) for group in self.light_groups.values())
        total_relays_used = individual_count + len(self.light_groups)
        
        # Calculate efficiency
        if not self.light_groups:
            relays_saved = 0
            efficiency_ratio = 1.0
        else:
            relays_saved = grouped_lights - len(self.light_groups)
            potential_relays = total_lights  # If every light had its own relay
            efficiency_ratio = total_relays_used / potential_relays if potential_relays > 0 else 1.0
        
        return {
            'total_lights': total_lights,
            'lights_with_individual_relays': individual_count,
            'lights_in_groups': grouped_lights,
            'light_groups': len(self.light_groups),
            'total_relays_used': total_relays_used,
            'relays_saved': relays_saved,
            'efficiency_ratio': efficiency_ratio,
            'cost_savings_percent': (relays_saved / total_lights * 100) if total_lights > 0 else 0,
            'group_details': self.get_group_status()
        }
    
    def create_light_group(self, group_id: str, light_ids: List[str], 
                          relay_pin: int, description: str = "") -> bool:
        """Create a new light group dynamically."""
        # Validate lights exist and aren't already controlled
        valid_lights = []
        for light_id in light_ids:
            if light_id not in self.lights_config:
                print(f"Warning: Light {light_id} not found in configuration")
                continue
            
            if light_id in self.light_to_group or light_id in self.light_to_individual:
                print(f"Warning: Light {light_id} already has relay control")
                continue
            
            valid_lights.append(light_id)
        
        if not valid_lights:
            print(f"No valid lights for group {group_id}")
            return False
        
        # Remove any individual relays for these lights
        for light_id in valid_lights:
            if light_id in self.individual_relays:
                self.individual_relays[light_id].cleanup()
                del self.individual_relays[light_id]
                del self.light_to_individual[light_id]
        
        # Create the group
        group = LightGroup(group_id, valid_lights, relay_pin, description)
        self.light_groups[group_id] = group
        
        # Update mappings
        for light_id in valid_lights:
            self.light_to_group[light_id] = group_id
        
        print(f"Created light group '{group_id}' with {len(valid_lights)} lights")
        return True
    
    def remove_light_group(self, group_id: str) -> bool:
        """Remove a light group and convert lights back to individual control."""
        if group_id not in self.light_groups:
            return False
        
        group = self.light_groups[group_id]
        
        # Convert lights back to individual control if they have relay pins
        for light_id in group.light_ids:
            # Remove from group mapping
            self.light_to_group.pop(light_id, None)
            
            # Check if light has individual relay pin configured
            light_config = self.lights_config.get(light_id, {})
            relay_pin = light_config.get('relay_pin') or light_config.get('gpio_pin')
            
            if relay_pin:
                # Create individual relay
                active_high = light_config.get('active_high', True)
                relay = IndividualRelay(relay_pin, light_id, active_high)
                self.individual_relays[light_id] = relay
                self.light_to_individual[light_id] = relay
        
        # Clean up and remove group
        group.relay.cleanup()
        del self.light_groups[group_id]
        
        print(f"Removed light group '{group_id}'")
        return True
    
    def optimize_relay_grouping(self, max_lights_per_group: int = 4) -> Dict:
        """Suggest optimal relay grouping based on location and usage patterns."""
        suggestions = {
            'current_efficiency': self.get_relay_usage_report(),
            'potential_groups': [],
            'estimated_savings': 0
        }
        
        # Find lights that could be grouped
        ungrouped_lights = [
            light_id for light_id in self.lights_config.keys()
            if light_id not in self.light_to_group
        ]
        
        # Group by zone/location
        zone_lights = {}
        for light_id in ungrouped_lights:
            light_config = self.lights_config[light_id]
            zone_key = light_config.get('zone_key', 'unknown')
            position = light_config.get('position', {})
            row = position.get('row', 0)
            
            # Create grouping key based on zone and row
            group_key = f"{zone_key}_row_{row}"
            
            if group_key not in zone_lights:
                zone_lights[group_key] = []
            zone_lights[group_key].append(light_id)
        
        # Suggest groups
        potential_relays_saved = 0
        for group_key, lights in zone_lights.items():
            if len(lights) >= 2 and len(lights) <= max_lights_per_group:
                # Calculate power compatibility
                total_power = sum(
                    self.lights_config[lid].get('power_watts', 0) 
                    for lid in lights
                )
                
                suggestion = {
                    'suggested_group_id': f"group_{group_key}",
                    'lights': lights,
                    'light_count': len(lights),
                    'location': group_key,
                    'total_power_watts': total_power,
                    'relays_saved': len(lights) - 1,
                    'description': f"Lights in {group_key.replace('_', ' ')}"
                }
                
                suggestions['potential_groups'].append(suggestion)
                potential_relays_saved += len(lights) - 1
        
        suggestions['estimated_savings'] = potential_relays_saved
        suggestions['cost_savings_percent'] = (
            potential_relays_saved / len(ungrouped_lights) * 100 
            if ungrouped_lights else 0
        )
        
        return suggestions
    
    def apply_optimization_suggestions(self, optimization_result: Dict, 
                                     auto_assign_pins: bool = False) -> Dict:
        """Apply the relay grouping optimization suggestions."""
        results = {
            'groups_created': 0,
            'relays_saved': 0,
            'errors': []
        }
        
        base_pin = 25  # Starting pin for auto-assignment
        
        for suggestion in optimization_result['potential_groups']:
            group_id = suggestion['suggested_group_id']
            lights = suggestion['lights']
            description = suggestion['description']
            
            if auto_assign_pins:
                # Auto-assign relay pin
                relay_pin = base_pin
                base_pin += 1
            else:
                # Would need manual pin assignment
                print(f"Manual pin assignment needed for group {group_id}")
                continue
            
            try:
                success = self.create_light_group(group_id, lights, relay_pin, description)
                if success:
                    results['groups_created'] += 1
                    results['relays_saved'] += suggestion['relays_saved']
                else:
                    results['errors'].append(f"Failed to create group {group_id}")
            
            except Exception as e:
                results['errors'].append(f"Error creating group {group_id}: {e}")
        
        return results
    
    def cleanup(self):
        """Clean up all GPIO resources."""
        for relay in self.individual_relays.values():
            relay.cleanup()
        
        for group in self.light_groups.values():
            group.relay.cleanup()


def load_relay_groups_config(data_dir: str = "data") -> Dict:
    """Load relay groups configuration from file."""
    config_file = Path(data_dir) / "relay_groups.json"
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f).get('relay_groups', {})
    
    return {}


def save_relay_groups_config(relay_groups_config: Dict, data_dir: str = "data"):
    """Save relay groups configuration to file."""
    config_file = Path(data_dir) / "relay_groups.json"
    
    config_data = {
        'relay_groups': relay_groups_config,
        'last_updated': datetime.now().isoformat(),
        'description': 'Configuration for shared relay control of multiple lights'
    }
    
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=2)


# Backward compatibility wrapper
class LightController(EnhancedLightController):
    """Backward compatible light controller that loads relay groups automatically."""
    
    def __init__(self, lights_config: Dict, data_dir: str = "data"):
        # Load relay groups configuration
        relay_groups_config = load_relay_groups_config(data_dir)
        super().__init__(lights_config, relay_groups_config)