"""Adaptive zone calibration system for mixed sensor and light capabilities.

This module handles the complexity of different zones having different sensor
and lighting capabilities, providing best-effort optimization based on
available hardware and measurements.
"""
import json
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path

from control.light_optimizer import LightOptimizer


class ZoneCapabilityAnalyzer:
    """Analyzes and maps the capabilities available in each zone."""
    
    def __init__(self, zones_config: Dict, lights_config: Dict, sensors_config: Dict):
        self.zones_config = zones_config
        self.lights_config = lights_config
        self.sensors_config = sensors_config
        
        self.zone_capabilities = {}
        self.zone_sensors = {}
        self.zone_lights = {}
        
        self._analyze_zone_capabilities()
    
    def _analyze_zone_capabilities(self):
        """Analyze what capabilities each zone has."""
        # Map sensors to zones
        for sensor_id, sensor_config in self.sensors_config.items():
            zone_key = sensor_config.get('zone_key')
            if zone_key:
                if zone_key not in self.zone_sensors:
                    self.zone_sensors[zone_key] = []
                self.zone_sensors[zone_key].append({
                    'id': sensor_id,
                    'config': sensor_config,
                    'capabilities': self._get_sensor_capabilities(sensor_config)
                })
        
        # Map lights to zones based on position overlap
        grid_size = self.zones_config.get('grid_size', {'rows': 24, 'cols': 12})
        for light_id, light_config in self.lights_config.items():
            light_position = light_config.get('position', {})
            if light_position:
                affected_zones = self._get_light_affected_zones(light_position, grid_size)
                for zone_key in affected_zones:
                    if zone_key not in self.zone_lights:
                        self.zone_lights[zone_key] = []
                    self.zone_lights[zone_key].append({
                        'id': light_id,
                        'config': light_config,
                        'capabilities': self._get_light_capabilities(light_config)
                    })
        
        # Determine overall zone capabilities
        for zone_key in set(list(self.zone_sensors.keys()) + list(self.zone_lights.keys())):
            zone_sensors = self.zone_sensors.get(zone_key, [])
            zone_lights = self.zone_lights.get(zone_key, [])
            
            self.zone_capabilities[zone_key] = {
                'sensors': zone_sensors,
                'lights': zone_lights,
                'can_measure_intensity': any(s['capabilities']['measures_intensity'] for s in zone_sensors),
                'can_measure_color': any(s['capabilities']['measures_color'] != 'none' for s in zone_sensors),
                'color_measurement_quality': self._assess_color_measurement_quality(zone_sensors),
                'has_controllable_lights': len(zone_lights) > 0,
                'light_spectrum_control': self._assess_spectrum_control(zone_lights),
                'optimization_capability': self._assess_optimization_capability(zone_sensors, zone_lights)
            }
    
    def _get_sensor_capabilities(self, sensor_config: Dict) -> Dict:
        """Determine capabilities of a sensor based on its type."""
        sensor_type = sensor_config.get('type', '').upper()
        
        # Define capabilities for each sensor type
        capabilities_map = {
            'BH1750': {
                'measures_intensity': True,
                'measures_color': 'none',
                'spectral_channels': ['broadband'],
                'precision': 'high',
                'dynamic_range': 'medium'
            },
            'TSL2561': {
                'measures_intensity': True,
                'measures_color': 'basic',
                'spectral_channels': ['broadband', 'ir'],
                'precision': 'medium',
                'dynamic_range': 'medium'
            },
            'TSL2591': {
                'measures_intensity': True,
                'measures_color': 'basic',
                'spectral_channels': ['visible', 'infrared', 'full_spectrum'],
                'precision': 'high',
                'dynamic_range': 'high'
            },
            'VEML7700': {
                'measures_intensity': True,
                'measures_color': 'none',
                'spectral_channels': ['broadband'],
                'precision': 'high',
                'dynamic_range': 'high'
            },
            'AS7341': {
                'measures_intensity': True,
                'measures_color': 'full',
                'spectral_channels': ['violet', 'indigo', 'blue', 'cyan', 'green', 'yellow', 'orange', 'red', 'nir'],
                'precision': 'very_high',
                'dynamic_range': 'high'
            },
            'TCS34725': {
                'measures_intensity': True,
                'measures_color': 'rgb',
                'spectral_channels': ['red', 'green', 'blue', 'clear'],
                'precision': 'medium',
                'dynamic_range': 'medium'
            }
        }
        
        return capabilities_map.get(sensor_type, {
            'measures_intensity': False,
            'measures_color': 'none',
            'spectral_channels': [],
            'precision': 'unknown',
            'dynamic_range': 'unknown'
        })
    
    def _get_light_capabilities(self, light_config: Dict) -> Dict:
        """Determine capabilities of a light fixture."""
        light_type = light_config.get('type', '')
        spectrum = light_config.get('spectrum', {})
        
        # Assess spectrum control capabilities
        has_spectrum_data = bool(spectrum)
        spectrum_diversity = len([k for k, v in spectrum.items() if k.endswith('_percent') and v > 5])
        
        return {
            'type': light_type,
            'has_relay_control': 'relay_pin' in light_config,
            'has_dimming': light_config.get('dimming_level') is not None,
            'power_watts': light_config.get('power_watts', 0),
            'spectrum_known': has_spectrum_data,
            'spectrum_diversity': spectrum_diversity,  # Number of significant color components
            'estimated_effectiveness': self._estimate_light_effectiveness(light_config)
        }
    
    def _estimate_light_effectiveness(self, light_config: Dict) -> str:
        """Estimate how effective a light is for plant growth."""
        light_type = light_config.get('type', '').lower()
        power = light_config.get('power_watts', 0)
        spectrum = light_config.get('spectrum', {})
        
        # Basic heuristics for effectiveness
        if 'led' in light_type and power > 100:
            return 'high'
        elif 'led' in light_type and power > 50:
            return 'medium'
        elif 'fluorescent' in light_type and power > 30:
            return 'medium'
        elif power > 20:
            return 'low'
        else:
            return 'very_low'
    
    def _get_light_affected_zones(self, light_position: Dict, grid_size: Dict) -> Set[str]:
        """Determine which zones a light affects based on its position."""
        affected_zones = set()
        
        row = light_position.get('row', 0)
        col = light_position.get('col', 0)
        row_span = light_position.get('row_span', 1)
        col_span = light_position.get('col_span', 1)
        
        # Light affects zones within its coverage area and nearby zones
        # Add some overlap for light spillover
        coverage_buffer = 2  # zones around the light that get significant illumination
        
        for r in range(max(0, row - coverage_buffer), 
                      min(grid_size.get('rows', 24), row + row_span + coverage_buffer)):
            for c in range(max(0, col - coverage_buffer),
                          min(grid_size.get('cols', 12), col + col_span + coverage_buffer)):
                zone_key = f"{r}-{c}"
                affected_zones.add(zone_key)
        
        return affected_zones
    
    def _assess_color_measurement_quality(self, zone_sensors: List[Dict]) -> str:
        """Assess the quality of color measurement in a zone."""
        if not zone_sensors:
            return 'none'
        
        color_capabilities = [s['capabilities']['measures_color'] for s in zone_sensors]
        
        if 'full' in color_capabilities:
            return 'excellent'
        elif 'rgb' in color_capabilities:
            return 'good'
        elif 'basic' in color_capabilities:
            return 'basic'
        else:
            return 'none'
    
    def _assess_spectrum_control(self, zone_lights: List[Dict]) -> str:
        """Assess the spectrum control capabilities in a zone."""
        if not zone_lights:
            return 'none'
        
        total_spectrum_diversity = sum(l['capabilities']['spectrum_diversity'] for l in zone_lights)
        controllable_lights = sum(1 for l in zone_lights if l['capabilities']['has_relay_control'])
        
        if total_spectrum_diversity >= 6 and controllable_lights >= 2:
            return 'excellent'
        elif total_spectrum_diversity >= 3 and controllable_lights >= 1:
            return 'good'
        elif controllable_lights >= 1:
            return 'basic'
        else:
            return 'none'
    
    def _assess_optimization_capability(self, zone_sensors: List[Dict], zone_lights: List[Dict]) -> str:
        """Assess overall optimization capability for a zone."""
        if not zone_sensors or not zone_lights:
            return 'none'
        
        color_quality = self._assess_color_measurement_quality(zone_sensors)
        spectrum_control = self._assess_spectrum_control(zone_lights)
        
        quality_scores = {
            'none': 0, 'basic': 1, 'good': 2, 'excellent': 3
        }
        
        avg_score = (quality_scores.get(color_quality, 0) + quality_scores.get(spectrum_control, 0)) / 2
        
        if avg_score >= 2.5:
            return 'excellent'
        elif avg_score >= 1.5:
            return 'good'
        elif avg_score >= 0.5:
            return 'basic'
        else:
            return 'limited'
    
    def get_zone_summary(self) -> Dict:
        """Get a summary of all zone capabilities."""
        summary = {
            'total_zones': len(self.zone_capabilities),
            'zones_with_sensors': len(self.zone_sensors),
            'zones_with_lights': len(self.zone_lights),
            'capability_distribution': {
                'excellent': 0,
                'good': 0,
                'basic': 0,
                'limited': 0,
                'none': 0
            },
            'zones': {}
        }
        
        for zone_key, capabilities in self.zone_capabilities.items():
            opt_capability = capabilities['optimization_capability']
            summary['capability_distribution'][opt_capability] += 1
            
            summary['zones'][zone_key] = {
                'optimization_capability': opt_capability,
                'sensor_count': len(capabilities['sensors']),
                'light_count': len(capabilities['lights']),
                'can_measure_color': capabilities['can_measure_color'],
                'color_measurement_quality': capabilities['color_measurement_quality'],
                'light_spectrum_control': capabilities['light_spectrum_control']
            }
        
        return summary


class AdaptiveZoneCalibrator:
    """Calibration system that adapts to each zone's capabilities."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        
        # Load configurations
        self.zones_config = self._load_json('zones.json')
        self.lights_config = self._load_json('lights.json').get('lights', {})
        self.sensors_config = self._load_json('light_sensors.json').get('sensors', {})
        
        # Initialize analyzers
        self.capability_analyzer = ZoneCapabilityAnalyzer(
            self.zones_config, self.lights_config, self.sensors_config
        )
        
        # Don't initialize base calibrator to avoid circular import
        self.base_calibrator = None
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON configuration file."""
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}
    
    def _create_mock_calibration_data(self) -> Dict:
        """Create mock calibration data for testing without full calibration."""
        # Create baseline readings (all lights off)
        baseline = {}
        for sensor_id in self.sensors_config.keys():
            baseline[sensor_id] = 50.0  # Mock baseline reading
        
        # Create light effects (change in sensor readings when each light is on)
        light_effects = {}
        for light_id in self.lights_config.keys():
            light_effects[light_id] = {}
            for sensor_id in self.sensors_config.keys():
                # Mock effect based on light power and sensor position
                light_power = self.lights_config[light_id].get('power_watts', 50)
                effect = min(200.0, light_power * 2.5)  # Simple power-based effect
                light_effects[light_id][sensor_id] = effect
        
        return {
            'timestamp': datetime.now().isoformat(),
            'calibration_type': 'mock_adaptive',
            'baseline': baseline,
            'light_effects': light_effects,
            'sensor_capabilities': {
                sensor_id: {'type': sensor_config.get('type', 'unknown')}
                for sensor_id, sensor_config in self.sensors_config.items()
            }
        }
    
    def run_adaptive_calibration(self) -> Dict:
        """Run calibration adapted to each zone's capabilities."""
        print("Starting adaptive zone calibration...")
        
        # Get zone capabilities
        zone_summary = self.capability_analyzer.get_zone_summary()
        print(f"Analyzing {zone_summary['total_zones']} zones:")
        for capability, count in zone_summary['capability_distribution'].items():
            if count > 0:
                print(f"  {capability}: {count} zones")
        
        # Create mock calibration data for testing
        # In production, this would be provided by the main calibrator
        calibration_data = self._create_mock_calibration_data()
        
        # Enhance with zone-specific analysis
        zone_specific_data = self._analyze_zones_individually(calibration_data)
        
        # Combine results
        adaptive_calibration = {
            'timestamp': datetime.now().isoformat(),
            'calibration_type': 'adaptive_zone',
            'base_calibration': calibration_data,
            'zone_capabilities': self.capability_analyzer.zone_capabilities,
            'zone_summary': zone_summary,
            'zone_specific_analysis': zone_specific_data,
            'optimization_strategies': self._generate_zone_strategies()
        }
        
        # Save adaptive calibration data
        self._save_json(adaptive_calibration, 'adaptive_calibration.json')
        
        print("Adaptive zone calibration complete!")
        return adaptive_calibration
    
    def _analyze_zones_individually(self, calibration_data: Dict) -> Dict:
        """Analyze each zone individually based on its capabilities."""
        zone_analysis = {}
        
        for zone_key, capabilities in self.capability_analyzer.zone_capabilities.items():
            zone_sensors = [s['id'] for s in capabilities['sensors']]
            zone_lights = [l['id'] for l in capabilities['lights']]
            
            analysis = {
                'zone_key': zone_key,
                'sensors': zone_sensors,
                'lights': zone_lights,
                'capabilities': capabilities,
                'measurement_data': {},
                'light_effects': {},
                'optimization_potential': self._assess_zone_optimization_potential(capabilities),
                'recommendations': []
            }
            
            # Extract relevant calibration data for this zone
            baseline = calibration_data.get('baseline', {})
            light_effects = calibration_data.get('light_effects', {})
            
            # Zone-specific sensor data
            for sensor_id in zone_sensors:
                if sensor_id in baseline:
                    analysis['measurement_data'][sensor_id] = {
                        'baseline': baseline[sensor_id],
                        'sensor_type': self.sensors_config[sensor_id].get('type'),
                        'capabilities': capabilities['sensors'][0]['capabilities']  # Simplified
                    }
            
            # Zone-specific light effects
            for light_id in zone_lights:
                if light_id in light_effects:
                    zone_effects = {}
                    for sensor_id in zone_sensors:
                        if sensor_id in light_effects[light_id]:
                            zone_effects[sensor_id] = light_effects[light_id][sensor_id]
                    
                    if zone_effects:
                        analysis['light_effects'][light_id] = zone_effects
            
            # Generate zone-specific recommendations
            analysis['recommendations'] = self._generate_zone_recommendations(analysis)
            
            zone_analysis[zone_key] = analysis
        
        return zone_analysis
    
    def _assess_zone_optimization_potential(self, capabilities: Dict) -> str:
        """Assess how well we can optimize this specific zone."""
        sensor_count = len(capabilities['sensors'])
        light_count = len(capabilities['lights'])
        color_quality = capabilities['color_measurement_quality']
        spectrum_control = capabilities['light_spectrum_control']
        
        if sensor_count == 0 or light_count == 0:
            return 'impossible'
        elif color_quality in ['excellent', 'good'] and spectrum_control in ['excellent', 'good']:
            return 'excellent'
        elif color_quality != 'none' and spectrum_control != 'none':
            return 'good'
        elif sensor_count >= 1 and light_count >= 1:
            return 'basic'
        else:
            return 'limited'
    
    def _generate_zone_recommendations(self, zone_analysis: Dict) -> List[Dict]:
        """Generate specific recommendations for a zone."""
        recommendations = []
        capabilities = zone_analysis['capabilities']
        zone_key = zone_analysis['zone_key']
        
        # Sensor recommendations
        if not capabilities['can_measure_intensity']:
            recommendations.append({
                'type': 'sensor_upgrade',
                'priority': 'high',
                'message': f"Zone {zone_key} needs at least one light intensity sensor"
            })
        elif capabilities['color_measurement_quality'] == 'none':
            recommendations.append({
                'type': 'sensor_upgrade',
                'priority': 'medium',
                'message': f"Zone {zone_key} would benefit from color-capable sensors (TSL2591, AS7341)"
            })
        
        # Light recommendations
        if not capabilities['has_controllable_lights']:
            recommendations.append({
                'type': 'light_upgrade',
                'priority': 'high',
                'message': f"Zone {zone_key} needs controllable lights with relay switches"
            })
        elif capabilities['light_spectrum_control'] == 'none':
            recommendations.append({
                'type': 'light_upgrade',
                'priority': 'medium',
                'message': f"Zone {zone_key} would benefit from diverse spectrum lighting"
            })
        
        # Optimization recommendations
        opt_potential = zone_analysis['optimization_potential']
        if opt_potential == 'excellent':
            recommendations.append({
                'type': 'optimization',
                'priority': 'low',
                'message': f"Zone {zone_key} has excellent optimization capabilities - fully automated control possible"
            })
        elif opt_potential == 'basic':
            recommendations.append({
                'type': 'optimization',
                'priority': 'medium',
                'message': f"Zone {zone_key} has basic capabilities - intensity control possible, limited color control"
            })
        
        return recommendations
    
    def _generate_zone_strategies(self) -> Dict:
        """Generate optimization strategies for different zone capability levels."""
        return {
            'excellent': {
                'description': 'Full spectrum and intensity optimization',
                'methods': ['multi_objective', 'linear', 'weighted_ls'],
                'targets': ['intensity', 'color_temperature', 'spectrum_ratios', 'par_effectiveness']
            },
            'good': {
                'description': 'Good spectrum control with some color optimization',
                'methods': ['multi_objective', 'greedy'],
                'targets': ['intensity', 'basic_color_ratios', 'par_effectiveness']
            },
            'basic': {
                'description': 'Intensity optimization with limited color control',
                'methods': ['greedy', 'weighted_ls'],
                'targets': ['intensity', 'total_par']
            },
            'limited': {
                'description': 'Best-effort intensity matching',
                'methods': ['greedy'],
                'targets': ['intensity']
            },
            'impossible': {
                'description': 'No optimization possible - manual control only',
                'methods': [],
                'targets': []
            }
        }
    
    def optimize_zone_specific_targets(self, zone_targets: Dict[str, Dict]) -> Dict:
        """Optimize for zone-specific targets with adaptive strategies."""
        optimization_results = {}
        
        for zone_key, targets in zone_targets.items():
            zone_capabilities = self.capability_analyzer.zone_capabilities.get(zone_key)
            if not zone_capabilities:
                optimization_results[zone_key] = {
                    'status': 'error',
                    'message': 'Zone not found or has no capabilities'
                }
                continue
            
            opt_capability = zone_capabilities['optimization_capability']
            strategy = self._generate_zone_strategies()[opt_capability]
            
            if not strategy['methods']:
                optimization_results[zone_key] = {
                    'status': 'impossible',
                    'message': 'No optimization possible for this zone',
                    'manual_lights': [l['id'] for l in zone_capabilities['lights']]
                }
                continue
            
            # Adapt targets based on capabilities
            adapted_targets = self._adapt_targets_to_capabilities(targets, zone_capabilities)
            
            # Run optimization using best available method
            try:
                zone_lights = [l['id'] for l in zone_capabilities['lights']]
                optimal_combination = self._optimize_zone_lights(
                    zone_key, adapted_targets, zone_lights, strategy['methods'][0]
                )
                
                optimization_results[zone_key] = {
                    'status': 'success',
                    'strategy': opt_capability,
                    'method': strategy['methods'][0],
                    'original_targets': targets,
                    'adapted_targets': adapted_targets,
                    'optimal_lights': optimal_combination,
                    'capabilities_used': strategy['targets']
                }
                
            except Exception as e:
                optimization_results[zone_key] = {
                    'status': 'error',
                    'message': str(e),
                    'fallback_method': 'manual'
                }
        
        return optimization_results
    
    def _adapt_targets_to_capabilities(self, targets: Dict, capabilities: Dict) -> Dict:
        """Adapt optimization targets based on zone capabilities."""
        adapted = {}
        
        # Always try to match intensity if we can measure it
        if 'intensity' in targets and capabilities['can_measure_intensity']:
            adapted['intensity'] = targets['intensity']
        
        # Only include color targets if we can measure color
        color_quality = capabilities['color_measurement_quality']
        if color_quality != 'none' and 'color_temperature' in targets:
            adapted['color_temperature'] = targets['color_temperature']
        
        if color_quality in ['good', 'excellent'] and 'spectrum_ratios' in targets:
            adapted['spectrum_ratios'] = targets['spectrum_ratios']
        
        # Include PAR if we have any measurement capability
        if capabilities['can_measure_intensity'] and 'par_target' in targets:
            adapted['par_target'] = targets['par_target']
        
        return adapted
    
    def _optimize_zone_lights(self, zone_key: str, targets: Dict, 
                            zone_lights: List[str], method: str) -> Dict[str, bool]:
        """Optimize lights for a specific zone using available method."""
        # This is a simplified version - in practice, you'd use the full optimizer
        # but filter to only consider lights and sensors in this zone
        
        # For now, delegate to the base optimizer but filter results
        zones_data = {zone_key: {'light_spectrum': targets}}
        
        # Use a simple optimization instead of base calibrator
        optimal_all = self._simple_zone_optimization(zone_key, targets, zone_lights)
        
        # Filter to only lights that affect this zone
        optimal_zone = {}
        for light_id in zone_lights:
            optimal_zone[light_id] = optimal_all.get(light_id, False)
        
        return optimal_zone
    
    def _simple_zone_optimization(self, zone_key: str, targets: Dict, zone_lights: List[str]) -> Dict:
        """Simple optimization for zone without full calibrator dependency."""
        optimal_lights = {}
        
        # Simple heuristic: turn on lights that match the requirements
        target_par = targets.get('par_target', 0)
        
        if target_par > 0:
            # Turn on lights based on power requirements
            total_power_needed = target_par * 0.5  # Simple conversion
            current_power = 0
            
            # Sort lights by power efficiency
            sorted_lights = sorted(zone_lights, 
                                 key=lambda lid: self.lights_config.get(lid, {}).get('power_watts', 50))
            
            for light_id in sorted_lights:
                if current_power < total_power_needed:
                    optimal_lights[light_id] = True
                    current_power += self.lights_config.get(light_id, {}).get('power_watts', 50)
                else:
                    optimal_lights[light_id] = False
        else:
            # Turn off all lights if no target
            for light_id in zone_lights:
                optimal_lights[light_id] = False
        
        return optimal_lights
    
    def _save_json(self, data: Dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_zone_status_report(self) -> Dict:
        """Generate a comprehensive status report for all zones."""
        zone_summary = self.capability_analyzer.get_zone_summary()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': zone_summary,
            'zone_details': {},
            'recommendations': {
                'high_priority': [],
                'medium_priority': [],
                'low_priority': []
            }
        }
        
        for zone_key, capabilities in self.capability_analyzer.zone_capabilities.items():
            zone_detail = {
                'zone_key': zone_key,
                'status': capabilities['optimization_capability'],
                'sensors': len(capabilities['sensors']),
                'lights': len(capabilities['lights']),
                'capabilities': {
                    'intensity_measurement': capabilities['can_measure_intensity'],
                    'color_measurement': capabilities['color_measurement_quality'],
                    'spectrum_control': capabilities['light_spectrum_control']
                }
            }
            
            # Add specific sensor and light info
            zone_detail['sensor_details'] = [
                {
                    'id': s['id'],
                    'type': s['config'].get('type'),
                    'capabilities': s['capabilities']
                } for s in capabilities['sensors']
            ]
            
            zone_detail['light_details'] = [
                {
                    'id': l['id'],
                    'type': l['config'].get('type'),
                    'power': l['config'].get('power_watts'),
                    'capabilities': l['capabilities']
                } for l in capabilities['lights']
            ]
            
            report['zone_details'][zone_key] = zone_detail
        
        return report


def main():
    """Example usage of adaptive zone calibration."""
    calibrator = AdaptiveZoneCalibrator()
    
    # Generate status report
    status_report = calibrator.get_zone_status_report()
    print("Zone Status Report:")
    print(json.dumps(status_report, indent=2))
    
    # Run adaptive calibration
    adaptive_data = calibrator.run_adaptive_calibration()
    print(f"\nAdaptive calibration completed for {len(adaptive_data['zone_capabilities'])} zones")


if __name__ == "__main__":
    main()