"""Advanced light optimization algorithms for precision light control.

This module provides sophisticated algorithms for determining optimal light
combinations to achieve target illumination levels across different zones.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize
import json


class LightOptimizer:
    """Advanced optimization algorithms for light control."""
    
    def __init__(self, calibration_data: Dict):
        self.calibration_data = calibration_data
        self.light_effects = calibration_data.get('light_effects', {})
        self.baseline = calibration_data.get('baseline', {})
        self.sensor_zones = calibration_data.get('sensor_zones', {})
        
        # Build optimization matrices
        self._build_matrices()
    
    def _build_matrices(self):
        """Build matrices for linear optimization."""
        self.light_ids = list(self.light_effects.keys())
        self.sensor_ids = list(self.baseline.keys())
        
        # Create effect matrix: rows = sensors, cols = lights
        self.effect_matrix = np.zeros((len(self.sensor_ids), len(self.light_ids)))
        
        for i, sensor_id in enumerate(self.sensor_ids):
            for j, light_id in enumerate(self.light_ids):
                effect = self.light_effects.get(light_id, {}).get(sensor_id, 0)
                self.effect_matrix[i, j] = effect
        
        # Create baseline vector
        self.baseline_vector = np.array([
            self.baseline.get(sensor_id, 0) for sensor_id in self.sensor_ids
        ])
        
        # Create zone mapping
        self.zone_to_sensor_indices = {}
        for i, sensor_id in enumerate(self.sensor_ids):
            zone_key = self.sensor_zones.get(sensor_id)
            if zone_key:
                if zone_key not in self.zone_to_sensor_indices:
                    self.zone_to_sensor_indices[zone_key] = []
                self.zone_to_sensor_indices[zone_key].append(i)
    
    def linear_programming_optimization(self, target_zones: Dict[str, float], 
                                      weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Use linear programming to find optimal light intensities."""
        try:
            from scipy.optimize import linprog
        except ImportError:
            print("scipy not available, falling back to basic optimization")
            return self.greedy_optimization(target_zones)
        
        if not self.zone_to_sensor_indices:
            return {}
        
        # Build constraint matrices for zone targets
        num_lights = len(self.light_ids)
        A_eq = []
        b_eq = []
        
        for zone_key, target_lux in target_zones.items():
            if zone_key in self.zone_to_sensor_indices:
                sensor_indices = self.zone_to_sensor_indices[zone_key]
                
                # Average constraint for sensors in this zone
                zone_constraint = np.zeros(num_lights)
                for sensor_idx in sensor_indices:
                    zone_constraint += self.effect_matrix[sensor_idx, :]
                zone_constraint /= len(sensor_indices)
                
                A_eq.append(zone_constraint)
                
                # Calculate target minus baseline average for this zone
                baseline_avg = np.mean([self.baseline_vector[i] for i in sensor_indices])
                b_eq.append(target_lux - baseline_avg)
        
        if not A_eq:
            return {}
        
        A_eq = np.array(A_eq)
        b_eq = np.array(b_eq)
        
        # Objective: minimize total power consumption (or uniform distribution)
        c = np.ones(num_lights)  # Equal weight to all lights
        
        # Bounds: lights can be 0 (off) to 1 (on)
        bounds = [(0, 1) for _ in range(num_lights)]
        
        # Solve
        result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        
        if result.success:
            solution = {}
            for i, light_id in enumerate(self.light_ids):
                # Convert to binary on/off (threshold at 0.5)
                solution[light_id] = result.x[i] > 0.5
            return solution
        else:
            print("Linear programming failed, using greedy approach")
            return self.greedy_optimization(target_zones)
    
    def weighted_least_squares_optimization(self, target_zones: Dict[str, float],
                                          zone_weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Use weighted least squares to find optimal light combination."""
        if not self.zone_to_sensor_indices:
            return {}
        
        # Default weights
        if zone_weights is None:
            zone_weights = {zone: 1.0 for zone in target_zones.keys()}
        
        def objective_function(light_states):
            """Calculate weighted error for given light states."""
            total_error = 0
            
            # Calculate predicted illumination
            light_binary = (light_states > 0.5).astype(float)
            predicted = self.baseline_vector + self.effect_matrix @ light_binary
            
            for zone_key, target_lux in target_zones.items():
                if zone_key in self.zone_to_sensor_indices:
                    sensor_indices = self.zone_to_sensor_indices[zone_key]
                    
                    # Average predicted lux for this zone
                    zone_predicted = np.mean(predicted[sensor_indices])
                    
                    # Weighted squared error
                    weight = zone_weights.get(zone_key, 1.0)
                    error = weight * (zone_predicted - target_lux) ** 2
                    total_error += error
            
            return total_error
        
        # Initial guess: all lights off
        x0 = np.zeros(len(self.light_ids))
        
        # Bounds: 0 to 1 for each light
        bounds = [(0, 1) for _ in range(len(self.light_ids))]
        
        # Optimize
        result = minimize(objective_function, x0, bounds=bounds, method='L-BFGS-B')
        
        if result.success:
            solution = {}
            for i, light_id in enumerate(self.light_ids):
                # Convert to binary on/off
                solution[light_id] = result.x[i] > 0.5
            return solution
        else:
            print("Weighted least squares failed, using greedy approach")
            return self.greedy_optimization(target_zones)
    
    def greedy_optimization(self, target_zones: Dict[str, float]) -> Dict[str, bool]:
        """Greedy algorithm that iteratively adds lights to minimize error."""
        if not self.zone_to_sensor_indices:
            return {}
        
        current_lights = {light_id: False for light_id in self.light_ids}
        
        for iteration in range(len(self.light_ids)):
            best_light = None
            best_error = float('inf')
            
            # Try turning on each currently off light
            for light_id in self.light_ids:
                if current_lights[light_id]:
                    continue  # Already on
                
                # Test this light combination
                test_lights = current_lights.copy()
                test_lights[light_id] = True
                
                error = self._calculate_zone_error(test_lights, target_zones)
                
                if error < best_error:
                    best_error = error
                    best_light = light_id
            
            # If we found an improvement, apply it
            if best_light and best_error < self._calculate_zone_error(current_lights, target_zones):
                current_lights[best_light] = True
            else:
                break  # No improvement possible
        
        return current_lights
    
    def _calculate_zone_error(self, light_states: Dict[str, bool], 
                            target_zones: Dict[str, float]) -> float:
        """Calculate total error for given light states and target zones."""
        total_error = 0
        
        for zone_key, target_lux in target_zones.items():
            if zone_key in self.zone_to_sensor_indices:
                sensor_indices = self.zone_to_sensor_indices[zone_key]
                
                # Calculate predicted lux for each sensor in this zone
                zone_predictions = []
                for sensor_idx in sensor_indices:
                    sensor_id = self.sensor_ids[sensor_idx]
                    predicted_lux = self.baseline.get(sensor_id, 0)
                    
                    # Add effects from active lights
                    for light_id, is_on in light_states.items():
                        if is_on:
                            effect = self.light_effects.get(light_id, {}).get(sensor_id, 0)
                            predicted_lux += effect
                    
                    zone_predictions.append(predicted_lux)
                
                # Average prediction for the zone
                if zone_predictions:
                    zone_avg = sum(zone_predictions) / len(zone_predictions)
                    error = abs(zone_avg - target_lux)
                    total_error += error
        
        return total_error
    
    def multi_objective_optimization(self, target_zones: Dict[str, float],
                                   power_weight: float = 0.1) -> Dict[str, bool]:
        """Optimize for both light targets and power consumption."""
        
        def objective_function(light_states):
            """Multi-objective function combining accuracy and power consumption."""
            # Convert to binary
            light_binary = (light_states > 0.5).astype(float)
            
            # Light accuracy error
            accuracy_error = 0
            for zone_key, target_lux in target_zones.items():
                if zone_key in self.zone_to_sensor_indices:
                    sensor_indices = self.zone_to_sensor_indices[zone_key]
                    
                    # Calculate predicted illumination for this zone
                    zone_lux = 0
                    for sensor_idx in sensor_indices:
                        predicted = self.baseline_vector[sensor_idx]
                        predicted += np.dot(self.effect_matrix[sensor_idx, :], light_binary)
                        zone_lux += predicted
                    
                    zone_lux /= len(sensor_indices)
                    accuracy_error += (zone_lux - target_lux) ** 2
            
            # Power consumption penalty
            power_penalty = power_weight * np.sum(light_binary)
            
            return accuracy_error + power_penalty
        
        # Initial guess
        x0 = np.zeros(len(self.light_ids))
        
        # Bounds
        bounds = [(0, 1) for _ in range(len(self.light_ids))]
        
        # Optimize
        result = minimize(objective_function, x0, bounds=bounds, method='L-BFGS-B')
        
        if result.success:
            solution = {}
            for i, light_id in enumerate(self.light_ids):
                solution[light_id] = result.x[i] > 0.5
            return solution
        else:
            return self.greedy_optimization(target_zones)
    
    def analyze_calibration_quality(self) -> Dict[str, float]:
        """Analyze the quality of calibration data."""
        if not self.light_effects:
            return {"error": "No calibration data available"}
        
        analysis = {}
        
        # Check for sensor coverage
        analysis['num_sensors'] = len(self.sensor_ids)
        analysis['num_lights'] = len(self.light_ids)
        
        # Check for sensor responsiveness
        responsive_sensors = 0
        for sensor_id in self.sensor_ids:
            max_effect = max([
                abs(self.light_effects.get(light_id, {}).get(sensor_id, 0))
                for light_id in self.light_ids
            ])
            if max_effect > 10:  # Threshold for meaningful response
                responsive_sensors += 1
        
        analysis['responsive_sensors'] = responsive_sensors
        analysis['sensor_coverage_ratio'] = responsive_sensors / len(self.sensor_ids) if self.sensor_ids else 0
        
        # Check for light effectiveness
        effective_lights = 0
        for light_id in self.light_ids:
            total_effect = sum([
                abs(self.light_effects.get(light_id, {}).get(sensor_id, 0))
                for sensor_id in self.sensor_ids
            ])
            if total_effect > 50:  # Threshold for meaningful light effect
                effective_lights += 1
        
        analysis['effective_lights'] = effective_lights
        analysis['light_effectiveness_ratio'] = effective_lights / len(self.light_ids) if self.light_ids else 0
        
        # Overall quality score
        quality_score = (analysis['sensor_coverage_ratio'] + analysis['light_effectiveness_ratio']) / 2
        analysis['overall_quality'] = quality_score
        
        return analysis


def test_optimization():
    """Test the optimization algorithms with sample data."""
    # Sample calibration data
    sample_data = {
        'baseline': {'sensor1': 50, 'sensor2': 45, 'sensor3': 55},
        'light_effects': {
            'light1': {'sensor1': 100, 'sensor2': 80, 'sensor3': 20},
            'light2': {'sensor1': 30, 'sensor2': 120, 'sensor3': 60},
            'light3': {'sensor1': 10, 'sensor2': 40, 'sensor3': 150}
        },
        'sensor_zones': {'sensor1': 'zone_a', 'sensor2': 'zone_b', 'sensor3': 'zone_c'}
    }
    
    optimizer = LightOptimizer(sample_data)
    
    # Test targets
    targets = {'zone_a': 200, 'zone_b': 180, 'zone_c': 220}
    
    print("Testing optimization algorithms:")
    
    # Test greedy
    greedy_result = optimizer.greedy_optimization(targets)
    print(f"Greedy result: {greedy_result}")
    
    # Test weighted least squares
    wls_result = optimizer.weighted_least_squares_optimization(targets)
    print(f"Weighted LS result: {wls_result}")
    
    # Test multi-objective
    multi_result = optimizer.multi_objective_optimization(targets, power_weight=0.2)
    print(f"Multi-objective result: {multi_result}")
    
    # Analyze quality
    quality = optimizer.analyze_calibration_quality()
    print(f"Calibration quality: {quality}")


if __name__ == "__main__":
    test_optimization()