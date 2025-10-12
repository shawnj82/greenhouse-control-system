"""
Ambient Light Handling for Adaptive Calibration System.
Manages calibration behavior based on ambient light conditions.
"""

import json
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass

class AmbientLightLevel(Enum):
    """Classification of ambient light levels."""
    DARK = "dark"                    # 0-50 lux
    DIM = "dim"                      # 50-200 lux  
    MODERATE = "moderate"            # 200-1000 lux
    BRIGHT = "bright"                # 1000-5000 lux
    VERY_BRIGHT = "very_bright"      # 5000+ lux

@dataclass
class AmbientConditions:
    """Ambient light conditions and their impact on calibration."""
    level: AmbientLightLevel
    average_lux: float
    variation_coefficient: float  # How much light varies across sensors
    time_of_day: str
    season_factor: float
    weather_condition: str
    calibration_feasibility: float  # 0.0 to 1.0
    recommended_strategy: str

class AmbientLightAnalyzer:
    """Analyzes ambient light conditions and their impact on calibration."""
    
    def __init__(self, sensors_config: Dict):
        self.sensors_config = sensors_config
        self.light_thresholds = {
            AmbientLightLevel.DARK: (0, 50),
            AmbientLightLevel.DIM: (50, 200),
            AmbientLightLevel.MODERATE: (200, 1000),
            AmbientLightLevel.BRIGHT: (1000, 5000),
            AmbientLightLevel.VERY_BRIGHT: (5000, float('inf'))
        }
    
    def analyze_current_conditions(self, sensor_readings: Dict[str, float]) -> AmbientConditions:
        """Analyze current ambient light conditions."""
        if not sensor_readings:
            # No readings available - assume dark conditions
            return self._create_default_conditions()
        
        # Calculate statistics
        lux_values = [reading for reading in sensor_readings.values() if reading is not None]
        if not lux_values:
            return self._create_default_conditions()
        
        average_lux = sum(lux_values) / len(lux_values)
        max_lux = max(lux_values)
        min_lux = min(lux_values)
        
        # Calculate variation coefficient
        if average_lux > 0:
            variance = sum((x - average_lux) ** 2 for x in lux_values) / len(lux_values)
            std_dev = variance ** 0.5
            variation_coefficient = std_dev / average_lux
        else:
            variation_coefficient = 0.0
        
        # Classify ambient light level
        light_level = self._classify_light_level(average_lux)
        
        # Assess calibration feasibility
        feasibility = self._calculate_calibration_feasibility(
            light_level, average_lux, variation_coefficient
        )
        
        # Determine recommended strategy
        strategy = self._recommend_strategy(light_level, feasibility, variation_coefficient)
        
        # Estimate time and conditions
        time_of_day = self._estimate_time_of_day(average_lux)
        season_factor = self._estimate_season_factor(average_lux)
        weather = self._estimate_weather(average_lux, variation_coefficient)
        
        return AmbientConditions(
            level=light_level,
            average_lux=average_lux,
            variation_coefficient=variation_coefficient,
            time_of_day=time_of_day,
            season_factor=season_factor,
            weather_condition=weather,
            calibration_feasibility=feasibility,
            recommended_strategy=strategy
        )
    
    def _classify_light_level(self, average_lux: float) -> AmbientLightLevel:
        """Classify the ambient light level."""
        for level, (min_lux, max_lux) in self.light_thresholds.items():
            if min_lux <= average_lux < max_lux:
                return level
        return AmbientLightLevel.VERY_BRIGHT
    
    def _calculate_calibration_feasibility(self, level: AmbientLightLevel, 
                                         average_lux: float, 
                                         variation: float) -> float:
        """Calculate how feasible calibration is under current conditions."""
        base_feasibility = {
            AmbientLightLevel.DARK: 1.0,      # Perfect conditions
            AmbientLightLevel.DIM: 0.9,       # Excellent
            AmbientLightLevel.MODERATE: 0.7,  # Good
            AmbientLightLevel.BRIGHT: 0.3,    # Poor
            AmbientLightLevel.VERY_BRIGHT: 0.1 # Very poor
        }.get(level, 0.1)
        
        # Adjust for light variation (less variation = better calibration)
        variation_penalty = min(0.3, variation * 0.5)
        
        return max(0.0, base_feasibility - variation_penalty)
    
    def _recommend_strategy(self, level: AmbientLightLevel, 
                          feasibility: float, variation: float) -> str:
        """Recommend calibration strategy based on conditions."""
        if feasibility >= 0.8:
            return "full_calibration"
        elif feasibility >= 0.5:
            return "differential_calibration"  # Focus on light differences
        elif feasibility >= 0.3:
            return "power_based_estimation"    # Use power ratings + basic tests
        else:
            return "schedule_for_later"        # Wait for better conditions
    
    def _estimate_time_of_day(self, average_lux: float) -> str:
        """Estimate time of day based on light levels."""
        if average_lux < 50:
            return "night"
        elif average_lux < 500:
            return "dawn_dusk"
        elif average_lux < 2000:
            return "overcast_day"
        elif average_lux < 10000:
            return "partly_cloudy"
        else:
            return "sunny_day"
    
    def _estimate_season_factor(self, average_lux: float) -> float:
        """Estimate seasonal light factor."""
        # Higher lux could indicate summer, lower winter
        if average_lux > 5000:
            return 1.0  # Summer
        elif average_lux > 2000:
            return 0.8  # Spring/Fall
        else:
            return 0.6  # Winter
    
    def _estimate_weather(self, average_lux: float, variation: float) -> str:
        """Estimate weather conditions."""
        if average_lux < 100:
            return "night_or_indoor"
        elif variation > 0.5:
            return "partly_cloudy"  # High variation suggests moving clouds
        elif average_lux > 5000:
            return "sunny"
        elif average_lux > 1000:
            return "overcast"
        else:
            return "heavily_overcast"
    
    def _create_default_conditions(self) -> AmbientConditions:
        """Create default conditions when no sensor data available."""
        return AmbientConditions(
            level=AmbientLightLevel.DARK,
            average_lux=0.0,
            variation_coefficient=0.0,
            time_of_day="unknown",
            season_factor=0.7,
            weather_condition="unknown",
            calibration_feasibility=1.0,
            recommended_strategy="full_calibration"
        )

class AmbientAwareCalibrator:
    """Calibrator that adapts behavior based on ambient light conditions."""
    
    def __init__(self, sensors_config: Dict):
        self.ambient_analyzer = AmbientLightAnalyzer(sensors_config)
        self.calibration_history = []
    
    def should_calibrate_now(self, sensor_readings: Dict[str, float]) -> Tuple[bool, str]:
        """Determine if calibration should proceed under current conditions."""
        conditions = self.ambient_analyzer.analyze_current_conditions(sensor_readings)
        
        feasibility = conditions.calibration_feasibility
        
        if feasibility >= 0.7:
            return True, f"Good conditions for calibration ({conditions.level.value})"
        elif feasibility >= 0.4:
            return True, f"Marginal conditions - proceed with {conditions.recommended_strategy}"
        else:
            suggestion = self._suggest_better_time(conditions)
            return False, f"Poor conditions ({conditions.level.value}) - {suggestion}"
    
    def _suggest_better_time(self, conditions: AmbientConditions) -> str:
        """Suggest when to calibrate based on current conditions."""
        if conditions.level in [AmbientLightLevel.BRIGHT, AmbientLightLevel.VERY_BRIGHT]:
            if "sunny" in conditions.weather_condition:
                return "Wait for evening/night or use blackout covers"
            else:
                return "Wait for darker conditions or early morning"
        else:
            return "Current conditions acceptable for basic calibration"
    
    def get_adaptive_calibration_params(self, sensor_readings: Dict[str, float]) -> Dict:
        """Get calibration parameters adapted to ambient conditions."""
        conditions = self.ambient_analyzer.analyze_current_conditions(sensor_readings)
        
        params = {
            'ambient_conditions': {
                'level': conditions.level.value,
                'average_lux': conditions.average_lux,
                'feasibility': conditions.calibration_feasibility,
                'strategy': conditions.recommended_strategy
            },
            'calibration_adjustments': self._get_calibration_adjustments(conditions),
            'measurement_settings': self._get_measurement_settings(conditions),
            'optimization_constraints': self._get_optimization_constraints(conditions)
        }
        
        return params
    
    def _get_calibration_adjustments(self, conditions: AmbientConditions) -> Dict:
        """Get calibration adjustments based on ambient conditions."""
        adjustments = {
            'baseline_measurement_time': 2.0,  # seconds
            'light_measurement_time': 3.0,
            'stabilization_delay': 1.0,
            'measurement_repeats': 3,
            'outlier_rejection_threshold': 0.2
        }
        
        if conditions.level == AmbientLightLevel.VERY_BRIGHT:
            # Need longer measurements and more repeats in bright conditions
            adjustments.update({
                'baseline_measurement_time': 5.0,
                'light_measurement_time': 8.0,
                'stabilization_delay': 2.0,
                'measurement_repeats': 5,
                'outlier_rejection_threshold': 0.4  # More lenient due to noise
            })
        elif conditions.level == AmbientLightLevel.BRIGHT:
            adjustments.update({
                'baseline_measurement_time': 3.0,
                'light_measurement_time': 5.0,
                'measurement_repeats': 4,
                'outlier_rejection_threshold': 0.3
            })
        
        return adjustments
    
    def _get_measurement_settings(self, conditions: AmbientConditions) -> Dict:
        """Get sensor measurement settings for ambient conditions."""
        if conditions.level in [AmbientLightLevel.BRIGHT, AmbientLightLevel.VERY_BRIGHT]:
            return {
                'integration_time': 'short',  # Avoid saturation
                'gain': 'low',
                'differential_mode': True,     # Focus on changes, not absolute values
                'high_resolution': False       # Speed over precision in bright light
            }
        else:
            return {
                'integration_time': 'medium',
                'gain': 'medium', 
                'differential_mode': False,
                'high_resolution': True
            }
    
    def _get_optimization_constraints(self, conditions: AmbientConditions) -> Dict:
        """Get optimization constraints based on ambient conditions."""
        constraints = {
            'min_light_effect_threshold': 10.0,  # Minimum detectable light effect
            'confidence_threshold': 0.5,
            'power_efficiency_weight': 0.3
        }
        
        if conditions.level == AmbientLightLevel.VERY_BRIGHT:
            # In very bright conditions, need larger effects to be confident
            constraints.update({
                'min_light_effect_threshold': 100.0,
                'confidence_threshold': 0.3,  # Lower confidence acceptable
                'power_efficiency_weight': 0.6  # Prioritize power since precision is poor
            })
        elif conditions.level == AmbientLightLevel.BRIGHT:
            constraints.update({
                'min_light_effect_threshold': 50.0,
                'confidence_threshold': 0.4,
                'power_efficiency_weight': 0.4
            })
        
        return constraints
    
    def record_calibration_attempt(self, sensor_readings: Dict[str, float], 
                                 success: bool, results: Dict):
        """Record calibration attempt for learning."""
        conditions = self.ambient_analyzer.analyze_current_conditions(sensor_readings)
        
        record = {
            'timestamp': datetime.now().isoformat(),
            'ambient_conditions': conditions,
            'success': success,
            'results_quality': results.get('overall_quality', 0),
            'lessons_learned': self._extract_lessons(conditions, success, results)
        }
        
        self.calibration_history.append(record)
        
        # Keep only recent history
        if len(self.calibration_history) > 100:
            self.calibration_history = self.calibration_history[-50:]
    
    def _extract_lessons(self, conditions: AmbientConditions, 
                        success: bool, results: Dict) -> List[str]:
        """Extract lessons from calibration attempt."""
        lessons = []
        
        if not success:
            if conditions.level == AmbientLightLevel.VERY_BRIGHT:
                lessons.append("Avoid calibration in very bright conditions")
            elif conditions.variation_coefficient > 0.5:
                lessons.append("High light variation reduces calibration accuracy")
        
        if success and conditions.level != AmbientLightLevel.DARK:
            lessons.append(f"Successful calibration possible in {conditions.level.value} conditions")
        
        return lessons
    
    def get_calibration_schedule_recommendations(self) -> Dict:
        """Recommend optimal times for calibration."""
        return {
            'best_times': [
                "Late evening (after sunset)",
                "Early morning (before sunrise)", 
                "Overcast days with stable cloud cover"
            ],
            'avoid_times': [
                "Midday sun (10am-4pm)",
                "Partly cloudy days (variable light)",
                "During sunrise/sunset (changing light)"
            ],
            'preparation_tips': [
                "Consider blackout curtains for greenhouse sections",
                "Use ambient light sensors to trigger automatic calibration",
                "Schedule calibration during known low-light periods"
            ]
        }