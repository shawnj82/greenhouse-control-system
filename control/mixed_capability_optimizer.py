"""Intelligent optimization engine for mixed sensor and light capabilities.

This module provides sophisticated algorithms that adapt their optimization
strategies based on what sensors and lights are actually available in each zone,
providing the best possible results with the hardware at hand.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import json

from control.light_optimizer import LightOptimizer


class OptimizationStrategy(Enum):
    """Different optimization strategies based on available capabilities."""
    FULL_SPECTRUM = "full_spectrum"          # All color channels + intensity
    BASIC_COLOR = "basic_color"              # RGB/IR ratios + intensity  
    INTENSITY_ONLY = "intensity_only"        # Just brightness matching
    BEST_EFFORT = "best_effort"              # Whatever we can measure
    MANUAL_FALLBACK = "manual_fallback"      # No optimization possible


@dataclass
class ZoneTarget:
    """Target specifications for a zone with graceful degradation."""
    zone_key: str
    
    # Primary targets (ideal)
    target_intensity: Optional[float] = None
    target_par: Optional[float] = None
    target_color_temp: Optional[float] = None
    target_spectrum_ratios: Optional[Dict[str, float]] = None
    
    # Fallback targets (if primary not achievable)
    min_intensity: Optional[float] = None
    max_intensity: Optional[float] = None
    acceptable_color_range: Optional[Tuple[float, float]] = None
    
    # Priority weights
    intensity_priority: float = 1.0
    color_priority: float = 0.8
    efficiency_priority: float = 0.5
    
    # Constraints
    max_power_consumption: Optional[float] = None
    required_lights: List[str] = None  # Lights that must be on
    forbidden_lights: List[str] = None  # Lights that must be off


@dataclass
class OptimizationResult:
    """Result of zone optimization with capability-aware feedback."""
    zone_key: str
    strategy_used: OptimizationStrategy
    success: bool
    
    # Results
    optimal_lights: Dict[str, bool]
    predicted_intensity: Optional[float] = None
    predicted_color_temp: Optional[float] = None
    predicted_spectrum: Optional[Dict[str, float]] = None
    power_consumption: Optional[float] = None
    
    # Quality metrics
    intensity_accuracy: Optional[float] = None  # How close we got to target
    color_accuracy: Optional[float] = None
    confidence_score: float = 0.0
    
    # Feedback
    limitations: List[str] = None
    suggestions: List[str] = None
    fallback_used: bool = False


class MixedCapabilityOptimizer:
    """Advanced optimizer that adapts to mixed sensor/light capabilities."""
    
    def __init__(self, adaptive_calibration_data: Dict):
        self.calibration_data = adaptive_calibration_data
        self.zone_capabilities = adaptive_calibration_data.get('zone_capabilities', {})
        self.base_calibration = adaptive_calibration_data.get('base_calibration', {})
        self.zone_analysis = adaptive_calibration_data.get('zone_specific_analysis', {})
        
        # Initialize base optimizer for fallback
        if self.base_calibration:
            self.base_optimizer = LightOptimizer(self.base_calibration)
        else:
            self.base_optimizer = None
    
    def optimize_zones(self, zone_targets: List[ZoneTarget]) -> List[OptimizationResult]:
        """Optimize multiple zones with mixed capabilities."""
        results = []
        
        for target in zone_targets:
            try:
                result = self.optimize_single_zone(target)
                results.append(result)
            except Exception as e:
                # Create error result
                error_result = OptimizationResult(
                    zone_key=target.zone_key,
                    strategy_used=OptimizationStrategy.MANUAL_FALLBACK,
                    success=False,
                    optimal_lights={},
                    limitations=[f"Optimization failed: {str(e)}"],
                    suggestions=["Check sensor and light configuration for this zone"]
                )
                results.append(error_result)
        
        return results
    
    def optimize_single_zone(self, target: ZoneTarget) -> OptimizationResult:
        """Optimize a single zone based on its capabilities."""
        zone_key = target.zone_key
        capabilities = self.zone_capabilities.get(zone_key)
        
        if not capabilities:
            return OptimizationResult(
                zone_key=zone_key,
                strategy_used=OptimizationStrategy.MANUAL_FALLBACK,
                success=False,
                optimal_lights={},
                limitations=["Zone not found in calibration data"],
                suggestions=["Run adaptive calibration to analyze this zone"]
            )
        
        # Determine optimization strategy
        strategy = self._select_optimization_strategy(capabilities, target)
        
        # Execute optimization based on strategy
        if strategy == OptimizationStrategy.FULL_SPECTRUM:
            return self._optimize_full_spectrum(target, capabilities)
        elif strategy == OptimizationStrategy.BASIC_COLOR:
            return self._optimize_basic_color(target, capabilities)
        elif strategy == OptimizationStrategy.INTENSITY_ONLY:
            return self._optimize_intensity_only(target, capabilities)
        elif strategy == OptimizationStrategy.BEST_EFFORT:
            return self._optimize_best_effort(target, capabilities)
        else:
            return self._manual_fallback(target, capabilities)
    
    def _select_optimization_strategy(self, capabilities: Dict, target: ZoneTarget) -> OptimizationStrategy:
        """Select the best optimization strategy for the zone's capabilities."""
        color_quality = capabilities.get('color_measurement_quality', 'none')
        spectrum_control = capabilities.get('light_spectrum_control', 'none')
        can_measure_intensity = capabilities.get('can_measure_intensity', False)
        has_lights = capabilities.get('has_controllable_lights', False)
        
        if not has_lights or not can_measure_intensity:
            return OptimizationStrategy.MANUAL_FALLBACK
        
        # Check if we have targets that require color measurement
        has_color_targets = any([
            target.target_color_temp is not None,
            target.target_spectrum_ratios is not None,
            target.acceptable_color_range is not None
        ])
        
        if color_quality == 'excellent' and spectrum_control in ['excellent', 'good'] and has_color_targets:
            return OptimizationStrategy.FULL_SPECTRUM
        elif color_quality in ['good', 'basic'] and spectrum_control != 'none' and has_color_targets:
            return OptimizationStrategy.BASIC_COLOR
        elif can_measure_intensity and (target.target_intensity or target.target_par):
            return OptimizationStrategy.INTENSITY_ONLY
        elif can_measure_intensity:
            return OptimizationStrategy.BEST_EFFORT
        else:
            return OptimizationStrategy.MANUAL_FALLBACK
    
    def _optimize_full_spectrum(self, target: ZoneTarget, capabilities: Dict) -> OptimizationResult:
        """Full spectrum optimization with color and intensity control."""
        zone_lights = [l['id'] for l in capabilities['lights']]
        zone_sensors = [s['id'] for s in capabilities['sensors']]
        
        # Build optimization problem
        objective_weights = {
            'intensity': target.intensity_priority,
            'color': target.color_priority,
            'efficiency': target.efficiency_priority
        }
        
        # Use advanced optimization from base optimizer but constrain to zone
        zone_targets = {}
        if target.target_par:
            zone_targets[target.zone_key] = target.target_par
        elif target.target_intensity:
            zone_targets[target.zone_key] = target.target_intensity
        
        if zone_targets and self.base_optimizer:
            try:
                optimal_all = self.base_optimizer.multi_objective_optimization(
                    zone_targets, power_weight=target.efficiency_priority
                )
                
                # Filter to zone lights only
                optimal_lights = {light_id: optimal_all.get(light_id, False) 
                                for light_id in zone_lights}
                
                # Predict results
                predicted_metrics = self._predict_zone_results(
                    target.zone_key, optimal_lights, capabilities
                )
                
                # Calculate accuracy
                intensity_accuracy = None
                if target.target_intensity and predicted_metrics.get('intensity'):
                    intensity_accuracy = 1.0 - abs(predicted_metrics['intensity'] - target.target_intensity) / target.target_intensity
                    intensity_accuracy = max(0.0, min(1.0, intensity_accuracy))
                
                color_accuracy = None
                if target.target_color_temp and predicted_metrics.get('color_temp'):
                    color_diff = abs(predicted_metrics['color_temp'] - target.target_color_temp)
                    color_accuracy = max(0.0, 1.0 - color_diff / 3000)  # Normalize by reasonable range
                
                confidence = self._calculate_confidence_score(capabilities, 'full_spectrum')
                
                return OptimizationResult(
                    zone_key=target.zone_key,
                    strategy_used=OptimizationStrategy.FULL_SPECTRUM,
                    success=True,
                    optimal_lights=optimal_lights,
                    predicted_intensity=predicted_metrics.get('intensity'),
                    predicted_color_temp=predicted_metrics.get('color_temp'),
                    predicted_spectrum=predicted_metrics.get('spectrum'),
                    power_consumption=predicted_metrics.get('power'),
                    intensity_accuracy=intensity_accuracy,
                    color_accuracy=color_accuracy,
                    confidence_score=confidence,
                    limitations=[],
                    suggestions=self._generate_suggestions(target, capabilities, predicted_metrics)
                )
                
            except Exception as e:
                # Fall back to simpler strategy
                return self._optimize_basic_color(target, capabilities)
        
        # Fallback if no base optimizer
        return self._optimize_intensity_only(target, capabilities)
    
    def _optimize_basic_color(self, target: ZoneTarget, capabilities: Dict) -> OptimizationResult:
        """Basic color optimization with limited color control."""
        zone_lights = [l['id'] for l in capabilities['lights']]
        
        # Simple heuristic-based optimization
        optimal_lights = {}
        
        # Start with all lights off
        for light_id in zone_lights:
            optimal_lights[light_id] = False
        
        # Turn on lights based on simple rules
        light_configs = {l['id']: l['config'] for l in capabilities['lights']}
        
        # Sort lights by estimated effectiveness
        sorted_lights = sorted(zone_lights, key=lambda lid: 
                             light_configs[lid].get('power_watts', 0), reverse=True)
        
        # Simple greedy approach: turn on most powerful lights first
        target_intensity = target.target_intensity or target.target_par or 200
        current_predicted = 0
        
        for light_id in sorted_lights:
            if current_predicted < target_intensity:
                optimal_lights[light_id] = True
                # Rough estimate of light contribution
                power = light_configs[light_id].get('power_watts', 50)
                current_predicted += power * 2  # Rough lux per watt estimate
        
        predicted_metrics = self._predict_zone_results(
            target.zone_key, optimal_lights, capabilities
        )
        
        intensity_accuracy = None
        if target.target_intensity and predicted_metrics.get('intensity'):
            intensity_accuracy = 1.0 - abs(predicted_metrics['intensity'] - target.target_intensity) / target.target_intensity
            intensity_accuracy = max(0.0, min(1.0, intensity_accuracy))
        
        confidence = self._calculate_confidence_score(capabilities, 'basic_color')
        
        return OptimizationResult(
            zone_key=target.zone_key,
            strategy_used=OptimizationStrategy.BASIC_COLOR,
            success=True,
            optimal_lights=optimal_lights,
            predicted_intensity=predicted_metrics.get('intensity'),
            predicted_color_temp=predicted_metrics.get('color_temp'),
            intensity_accuracy=intensity_accuracy,
            confidence_score=confidence,
            limitations=["Limited color control - basic intensity optimization only"],
            suggestions=self._generate_suggestions(target, capabilities, predicted_metrics)
        )
    
    def _optimize_intensity_only(self, target: ZoneTarget, capabilities: Dict) -> OptimizationResult:
        """Intensity-only optimization when color control is not available."""
        zone_lights = [l['id'] for l in capabilities['lights']]
        zone_sensors = [s['id'] for s in capabilities['sensors']]
        
        # Get calibration effects for this zone
        zone_effects = {}
        light_effects = self.base_calibration.get('light_effects', {})
        baseline = self.base_calibration.get('baseline', {})
        
        for light_id in zone_lights:
            if light_id in light_effects:
                zone_effect = 0
                sensor_count = 0
                for sensor_id in zone_sensors:
                    if sensor_id in light_effects[light_id]:
                        zone_effect += light_effects[light_id][sensor_id]
                        sensor_count += 1
                if sensor_count > 0:
                    zone_effects[light_id] = zone_effect / sensor_count
        
        # Simple greedy optimization for intensity
        target_intensity = target.target_intensity or target.target_par or 200
        current_intensity = sum(baseline.get(sid, 0) for sid in zone_sensors) / len(zone_sensors) if zone_sensors else 0
        
        optimal_lights = {}
        remaining_target = target_intensity - current_intensity
        
        # Sort lights by effectiveness (lux per power)
        light_effectiveness = []
        for light_id in zone_lights:
            effect = zone_effects.get(light_id, 0)
            power = capabilities['lights'][0]['config'].get('power_watts', 50)  # Simplified
            effectiveness = effect / power if power > 0 else 0
            light_effectiveness.append((light_id, effect, effectiveness))
        
        light_effectiveness.sort(key=lambda x: x[2], reverse=True)
        
        # Greedy selection
        for light_id, effect, effectiveness in light_effectiveness:
            if remaining_target > 0 and effect > 10:  # Minimum useful effect
                optimal_lights[light_id] = True
                remaining_target -= effect
            else:
                optimal_lights[light_id] = False
        
        predicted_metrics = self._predict_zone_results(
            target.zone_key, optimal_lights, capabilities
        )
        
        intensity_accuracy = None
        if target.target_intensity and predicted_metrics.get('intensity'):
            intensity_accuracy = 1.0 - abs(predicted_metrics['intensity'] - target.target_intensity) / target.target_intensity
            intensity_accuracy = max(0.0, min(1.0, intensity_accuracy))
        
        confidence = self._calculate_confidence_score(capabilities, 'intensity_only')
        
        return OptimizationResult(
            zone_key=target.zone_key,
            strategy_used=OptimizationStrategy.INTENSITY_ONLY,
            success=True,
            optimal_lights=optimal_lights,
            predicted_intensity=predicted_metrics.get('intensity'),
            intensity_accuracy=intensity_accuracy,
            confidence_score=confidence,
            limitations=["No color control available - intensity optimization only"],
            suggestions=["Consider adding color-capable sensors (TSL2591, AS7341) for better control"]
        )
    
    def _optimize_best_effort(self, target: ZoneTarget, capabilities: Dict) -> OptimizationResult:
        """Best-effort optimization with minimal capabilities."""
        zone_lights = [l['id'] for l in capabilities['lights']]
        
        # Very simple heuristic: turn on half the lights
        optimal_lights = {}
        light_count = len(zone_lights)
        lights_to_turn_on = max(1, light_count // 2)
        
        for i, light_id in enumerate(zone_lights):
            optimal_lights[light_id] = i < lights_to_turn_on
        
        predicted_metrics = self._predict_zone_results(
            target.zone_key, optimal_lights, capabilities
        )
        
        confidence = self._calculate_confidence_score(capabilities, 'best_effort')
        
        return OptimizationResult(
            zone_key=target.zone_key,
            strategy_used=OptimizationStrategy.BEST_EFFORT,
            success=True,
            optimal_lights=optimal_lights,
            predicted_intensity=predicted_metrics.get('intensity'),
            confidence_score=confidence,
            limitations=["Very limited optimization capabilities - basic heuristic used"],
            suggestions=[
                "Add more sensors for better measurement",
                "Verify light configurations",
                "Consider manual fine-tuning"
            ]
        )
    
    def _manual_fallback(self, target: ZoneTarget, capabilities: Dict) -> OptimizationResult:
        """Manual fallback when optimization is not possible."""
        zone_lights = [l['id'] for l in capabilities['lights']]
        
        # Provide manual light list
        manual_lights = {}
        for light_id in zone_lights:
            manual_lights[light_id] = False  # Default off
        
        limitations = []
        suggestions = []
        
        if not capabilities.get('has_controllable_lights'):
            limitations.append("No controllable lights in this zone")
            suggestions.append("Add relay-controlled lights")
        
        if not capabilities.get('can_measure_intensity'):
            limitations.append("No light sensors in this zone")
            suggestions.append("Add at least one light intensity sensor (BH1750, TSL2591)")
        
        return OptimizationResult(
            zone_key=target.zone_key,
            strategy_used=OptimizationStrategy.MANUAL_FALLBACK,
            success=False,
            optimal_lights=manual_lights,
            confidence_score=0.0,
            limitations=limitations,
            suggestions=suggestions
        )
    
    def _predict_zone_results(self, zone_key: str, optimal_lights: Dict[str, bool], 
                            capabilities: Dict) -> Dict:
        """Predict the results of a light combination for a zone."""
        zone_sensors = [s['id'] for s in capabilities['sensors']]
        
        # Get baseline
        baseline = self.base_calibration.get('baseline', {})
        light_effects = self.base_calibration.get('light_effects', {})
        
        predicted_intensity = 0
        sensor_count = 0
        
        for sensor_id in zone_sensors:
            sensor_intensity = baseline.get(sensor_id, 0)
            
            # Add effects from active lights
            for light_id, is_on in optimal_lights.items():
                if is_on and light_id in light_effects and sensor_id in light_effects[light_id]:
                    sensor_intensity += light_effects[light_id][sensor_id]
            
            predicted_intensity += sensor_intensity
            sensor_count += 1
        
        if sensor_count > 0:
            predicted_intensity /= sensor_count
        
        # Calculate power consumption
        power_consumption = 0
        light_configs = {l['id']: l['config'] for l in capabilities['lights']}
        for light_id, is_on in optimal_lights.items():
            if is_on and light_id in light_configs:
                power_consumption += light_configs[light_id].get('power_watts', 0)
        
        return {
            'intensity': predicted_intensity,
            'power': power_consumption,
            'color_temp': None,  # Would need spectral analysis
            'spectrum': None     # Would need spectral analysis
        }
    
    def _calculate_confidence_score(self, capabilities: Dict, strategy: str) -> float:
        """Calculate confidence score based on capabilities and strategy used."""
        base_scores = {
            'full_spectrum': 0.9,
            'basic_color': 0.7,
            'intensity_only': 0.5,
            'best_effort': 0.3,
            'manual_fallback': 0.0
        }
        
        base_score = base_scores.get(strategy, 0.0)
        
        # Adjust based on actual capabilities
        sensor_count = len(capabilities.get('sensors', []))
        light_count = len(capabilities.get('lights', []))
        
        # More sensors and lights increase confidence
        count_bonus = min(0.2, (sensor_count + light_count) * 0.05)
        
        # Color measurement quality affects confidence
        color_quality = capabilities.get('color_measurement_quality', 'none')
        color_bonus = {
            'excellent': 0.1,
            'good': 0.05,
            'basic': 0.02,
            'none': 0.0
        }.get(color_quality, 0.0)
        
        return min(1.0, base_score + count_bonus + color_bonus)
    
    def _generate_suggestions(self, target: ZoneTarget, capabilities: Dict, 
                            predicted_metrics: Dict) -> List[str]:
        """Generate helpful suggestions based on optimization results."""
        suggestions = []
        
        # Check if we met the targets reasonably well
        if target.target_intensity and predicted_metrics.get('intensity'):
            error = abs(predicted_metrics['intensity'] - target.target_intensity)
            if error > target.target_intensity * 0.2:  # More than 20% error
                suggestions.append(f"Target intensity miss by {error:.0f} lux - consider adding more lights")
        
        # Check sensor coverage
        sensor_count = len(capabilities.get('sensors', []))
        if sensor_count < 2:
            suggestions.append("Consider adding more sensors for better accuracy")
        
        # Check color capabilities
        color_quality = capabilities.get('color_measurement_quality', 'none')
        if color_quality == 'none' and (target.target_color_temp or target.target_spectrum_ratios):
            suggestions.append("Add color-capable sensors (TSL2591, AS7341) for spectrum control")
        
        # Check light diversity
        light_count = len(capabilities.get('lights', []))
        if light_count < 2:
            suggestions.append("Consider adding more lights for better control granularity")
        
        return suggestions


def create_zone_target(zone_key: str, **kwargs) -> ZoneTarget:
    """Helper function to create zone targets with sensible defaults."""
    return ZoneTarget(zone_key=zone_key, **kwargs)


def main():
    """Example usage of mixed capability optimizer."""
    # This would normally use real adaptive calibration data
    sample_adaptive_data = {
        'zone_capabilities': {
            '2-2': {
                'sensors': [{'id': 'ls-1', 'config': {'type': 'TSL2591'}}],
                'lights': [{'id': 'light-1', 'config': {'power_watts': 100}}],
                'can_measure_intensity': True,
                'can_measure_color': True,
                'color_measurement_quality': 'basic',
                'has_controllable_lights': True,
                'light_spectrum_control': 'good',
                'optimization_capability': 'good'
            }
        },
        'base_calibration': {
            'baseline': {'ls-1': 50},
            'light_effects': {'light-1': {'ls-1': 150}}
        }
    }
    
    optimizer = MixedCapabilityOptimizer(sample_adaptive_data)
    
    # Create sample targets
    targets = [
        create_zone_target('2-2', target_intensity=200, target_color_temp=4000)
    ]
    
    # Optimize
    results = optimizer.optimize_zones(targets)
    
    for result in results:
        print(f"Zone {result.zone_key}: {result.strategy_used.value}")
        print(f"  Success: {result.success}")
        print(f"  Optimal lights: {result.optimal_lights}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        if result.limitations:
            print(f"  Limitations: {result.limitations}")
        if result.suggestions:
            print(f"  Suggestions: {result.suggestions}")


if __name__ == "__main__":
    main()