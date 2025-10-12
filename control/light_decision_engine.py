"""
Intelligent Light Decision Making System.
Determines when and how to control lights based on multiple factors.
"""

import json
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path

class LightDecisionReason(Enum):
    """Reasons for light control decisions."""
    TARGET_REQUIREMENT = "target_requirement"
    PLANT_SCHEDULE = "plant_schedule"
    ENERGY_EFFICIENCY = "energy_efficiency"
    AMBIENT_CONDITIONS = "ambient_conditions"
    SENSOR_FEEDBACK = "sensor_feedback"
    MANUAL_OVERRIDE = "manual_override"
    EMERGENCY_RESPONSE = "emergency_response"
    MAINTENANCE_MODE = "maintenance_mode"

@dataclass
class DLIReading:
    """Represents a Daily Light Integral reading for a zone."""
    zone_key: str
    timestamp: datetime
    instantaneous_ppfd: float  # μmol/m²/s
    duration_seconds: int
    cumulative_dli: float  # mol/m²/day

class DLITracker:
    """Tracks Daily Light Integral (DLI) for each zone."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.dli_file = self.data_dir / "dli_tracking.json"
        self.daily_data: Dict[str, Dict[str, List[DLIReading]]] = {}
        self.load_daily_data()
    
    def load_daily_data(self):
        """Load DLI tracking data from file."""
        if self.dli_file.exists():
            try:
                with open(self.dli_file, 'r') as f:
                    data = json.load(f)
                    # Convert back to DLIReading objects
                    for date_str, zones in data.items():
                        self.daily_data[date_str] = {}
                        for zone_key, readings in zones.items():
                            self.daily_data[date_str][zone_key] = [
                                DLIReading(
                                    zone_key=reading['zone_key'],
                                    timestamp=datetime.fromisoformat(reading['timestamp']),
                                    instantaneous_ppfd=reading['instantaneous_ppfd'],
                                    duration_seconds=reading['duration_seconds'],
                                    cumulative_dli=reading['cumulative_dli']
                                ) for reading in readings
                            ]
            except Exception as e:
                print(f"Warning: Could not load DLI data: {e}")
                self.daily_data = {}
    
    def save_daily_data(self):
        """Save DLI tracking data to file."""
        try:
            # Convert DLIReading objects to dict for JSON serialization
            data = {}
            for date_str, zones in self.daily_data.items():
                data[date_str] = {}
                for zone_key, readings in zones.items():
                    data[date_str][zone_key] = [
                        {
                            'zone_key': reading.zone_key,
                            'timestamp': reading.timestamp.isoformat(),
                            'instantaneous_ppfd': reading.instantaneous_ppfd,
                            'duration_seconds': reading.duration_seconds,
                            'cumulative_dli': reading.cumulative_dli
                        } for reading in readings
                    ]
            
            with open(self.dli_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save DLI data: {e}")
    
    def convert_lux_to_ppfd(self, lux: float, light_type: str = "mixed") -> float:
        """Convert lux to PPFD (μmol/m²/s)."""
        # Conversion factors vary by light source
        conversion_factors = {
            "sunlight": 0.0185,  # Natural sunlight
            "led_full_spectrum": 0.016,  # Full spectrum LED
            "led_white": 0.014,  # White LED
            "fluorescent": 0.012,  # Fluorescent
            "mixed": 0.015  # Mixed/unknown sources
        }
        
        factor = conversion_factors.get(light_type, conversion_factors["mixed"])
        return lux * factor
    
    def add_reading(self, zone_key: str, lux_reading: float, timestamp: datetime = None, 
                   duration_minutes: int = 1, light_type: str = "mixed"):
        """Add a light reading and update DLI calculation."""
        if timestamp is None:
            timestamp = datetime.now()
        
        date_str = timestamp.date().isoformat()
        
        # Convert lux to PPFD
        ppfd = self.convert_lux_to_ppfd(lux_reading, light_type)
        
        # Calculate DLI contribution (mol/m²/day)
        # PPFD (μmol/m²/s) * duration (s) * 1e-6 (μmol to mol)
        duration_seconds = duration_minutes * 60
        dli_contribution = (ppfd * duration_seconds) / 1_000_000
        
        # Get existing DLI for today
        if date_str not in self.daily_data:
            self.daily_data[date_str] = {}
        
        if zone_key not in self.daily_data[date_str]:
            self.daily_data[date_str][zone_key] = []
        
        # Calculate cumulative DLI for the day
        existing_dli = sum(reading.cumulative_dli for reading in self.daily_data[date_str][zone_key])
        cumulative_dli = existing_dli + dli_contribution
        
        # Add new reading
        reading = DLIReading(
            zone_key=zone_key,
            timestamp=timestamp,
            instantaneous_ppfd=ppfd,
            duration_seconds=duration_seconds,
            cumulative_dli=cumulative_dli
        )
        
        self.daily_data[date_str][zone_key].append(reading)
        self.save_daily_data()
        
        return reading
    
    def get_daily_dli(self, zone_key: str, date_obj: date = None) -> float:
        """Get total DLI for a zone on a specific date."""
        if date_obj is None:
            date_obj = date.today()
        
        date_str = date_obj.isoformat()
        
        if date_str in self.daily_data and zone_key in self.daily_data[date_str]:
            readings = self.daily_data[date_str][zone_key]
            if readings:
                return readings[-1].cumulative_dli  # Latest cumulative value
        
        return 0.0
    
    def get_dli_progress(self, zone_key: str, target_dli: float, date_obj: date = None) -> Dict[str, float]:
        """Get DLI progress for a zone against target."""
        current_dli = self.get_daily_dli(zone_key, date_obj)
        progress_percent = (current_dli / target_dli * 100) if target_dli > 0 else 0
        remaining_dli = max(0, target_dli - current_dli)
        
        return {
            "current_dli": current_dli,
            "target_dli": target_dli,
            "progress_percent": progress_percent,
            "remaining_dli": remaining_dli,
            "is_target_met": current_dli >= target_dli
        }
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove DLI data older than specified days."""
        cutoff_date = (date.today() - timedelta(days=days_to_keep)).isoformat()
        
        dates_to_remove = [
            date_str for date_str in self.daily_data.keys()
            if date_str < cutoff_date
        ]
        
        for date_str in dates_to_remove:
            del self.daily_data[date_str]
        
        if dates_to_remove:
            self.save_daily_data()

@dataclass
class LightDecision:
    """Represents a decision about light control."""
    light_id: str
    should_be_on: bool
    intensity_percent: float  # 0-100
    confidence: float  # 0-1
    primary_reason: LightDecisionReason
    contributing_factors: List[str]
    estimated_effect: Dict[str, float]  # sensor_id -> expected lux change
    power_consumption: float
    priority_score: float
    next_evaluation_time: datetime

class LightDecisionEngine:
    """Advanced decision engine for intelligent light control."""
    
    def __init__(self, calibration_data: Dict, zones_config: Dict, 
                 lights_config: Dict, sensors_config: Dict, config_file: str = "data/light_control_config.json"):
        self.calibration_data = calibration_data
        self.zones_config = zones_config
        self.lights_config = lights_config
        self.sensors_config = sensors_config
        self.config_file = config_file
        
        # Initialize DLI tracker
        self.dli_tracker = DLITracker()
        
        # Decision history for learning
        self.decision_history = []
        self.current_light_states = {}
        
        # Load configuration
        self.config = self.load_config()
        
        # Configuration parameters (with defaults)
        self.decision_params = {
            'energy_cost_per_kwh': self.config.get('energy_cost_per_kwh', 0.12),  # $/kWh
            'par_efficiency_threshold': 0.8,  # Minimum efficiency to consider
            'ambient_override_threshold': 0.3,  # Ambient feasibility threshold
            'sensor_update_interval': 30,  # seconds
            'decision_update_interval': 300,  # 5 minutes
            'learning_weight': 0.1,  # How much to weight historical performance
        }
        
        # Time-of-use pricing (configurable)
        self.time_of_use_pricing = self.config.get('time_of_use_pricing', {
            'off_peak': {'multiplier': 1.0, 'hours': list(range(23, 24)) + list(range(0, 6))},
            'standard': {'multiplier': 1.5, 'hours': list(range(6, 16))},
            'peak': {'multiplier': 2.0, 'hours': list(range(16, 23))}
        })
        
        # Plant growth schedules (with configurable morning start times)
        default_schedules = {
            'lettuce': {
                'light_hours_per_day': 14,
                'preferred_start_time': '06:00',
                'preferred_end_time': '20:00',
                'intensity_curve': 'gradual_ramp',
                'target_dli': 14.0  # mol/m²/day
            },
            'basil': {
                'light_hours_per_day': 16,
                'preferred_start_time': '05:00',
                'preferred_end_time': '21:00',
                'intensity_curve': 'steady',
                'target_dli': 16.0
            },
            'tomatoes': {
                'light_hours_per_day': 16,
                'preferred_start_time': '06:00',
                'preferred_end_time': '22:00',
                'intensity_curve': 'high_intensity',
                'target_dli': 20.0
            },
            'herbs': {
                'light_hours_per_day': 12,
                'preferred_start_time': '07:00',
                'preferred_end_time': '19:00',
                'intensity_curve': 'gentle',
                'target_dli': 12.0
            }
        }
        self.growth_schedules = self.config.get('growth_schedules', default_schedules)
    
    def load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {self.config_file}: {e}")
        
        # Return default config
        return {
            'energy_cost_per_kwh': 0.12,
            'time_of_use_pricing': {
                'off_peak': {'multiplier': 1.0, 'hours': list(range(23, 24)) + list(range(0, 6))},
                'standard': {'multiplier': 1.5, 'hours': list(range(6, 16))},
                'peak': {'multiplier': 2.0, 'hours': list(range(16, 23))}
            },
            'growth_schedules': {}
        }
    
    def save_config(self):
        """Save current configuration to file."""
        config_data = {
            'energy_cost_per_kwh': self.decision_params['energy_cost_per_kwh'],
            'time_of_use_pricing': self.time_of_use_pricing,
            'growth_schedules': self.growth_schedules
        }
        
        try:
            Path(self.config_file).parent.mkdir(exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config to {self.config_file}: {e}")
    
    def update_growth_schedule(self, crop_type: str, schedule: Dict):
        """Update growth schedule for a crop type."""
        self.growth_schedules[crop_type] = schedule
        self.save_config()
    
    def update_time_of_use_pricing(self, pricing_config: Dict):
        """Update time-of-use pricing configuration."""
        self.time_of_use_pricing = pricing_config
        self.save_config()
    
    def update_energy_cost(self, cost_per_kwh: float):
        """Update base energy cost per kWh."""
        self.decision_params['energy_cost_per_kwh'] = cost_per_kwh
        self.save_config()
        
        # Plant growth schedules
        self.growth_schedules = {
            'lettuce': {
                'light_hours_per_day': 14,
                'preferred_start_time': '06:00',
                'preferred_end_time': '20:00',
                'intensity_curve': 'gradual_ramp'
            },
            'basil': {
                'light_hours_per_day': 16,
                'preferred_start_time': '05:00',
                'preferred_end_time': '21:00',
                'intensity_curve': 'peak_midday'
            },
            'tomatoes': {
                'light_hours_per_day': 18,
                'preferred_start_time': '04:00',
                'preferred_end_time': '22:00',
                'intensity_curve': 'extended_peak'
            },
            'herbs': {
                'light_hours_per_day': 12,
                'preferred_start_time': '07:00',
                'preferred_end_time': '19:00',
                'intensity_curve': 'steady'
            }
        }
    
    def make_light_decisions(self, current_sensor_readings: Dict[str, float],
                           current_time: Optional[datetime] = None) -> List[LightDecision]:
        """Make intelligent decisions about light control."""
        if current_time is None:
            current_time = datetime.now()
        
        decisions = []
        
        # Analyze current conditions
        conditions_analysis = self._analyze_current_conditions(
            current_sensor_readings, current_time
        )
        
        # Get zone requirements
        zone_requirements = self._calculate_zone_requirements(current_time)
        
        # For each light, make a decision
        for light_id in self.lights_config.keys():
            decision = self._make_individual_light_decision(
                light_id, 
                conditions_analysis,
                zone_requirements,
                current_sensor_readings,
                current_time
            )
            decisions.append(decision)
        
        # Optimize decisions globally
        optimized_decisions = self._optimize_decisions_globally(decisions, conditions_analysis)
        
        # Record decisions for learning
        self._record_decisions(optimized_decisions, current_sensor_readings, current_time)
        
        return optimized_decisions
    
    def _analyze_current_conditions(self, sensor_readings: Dict[str, float], 
                                  current_time: datetime) -> Dict:
        """Analyze current environmental and operational conditions."""
        # Calculate ambient light level
        ambient_readings = [r for r in sensor_readings.values() if r is not None]
        avg_ambient = sum(ambient_readings) / len(ambient_readings) if ambient_readings else 0
        
        # Time-based factors
        hour = current_time.hour
        is_daytime = 6 <= hour <= 18
        is_peak_growth_time = 8 <= hour <= 16
        
        # Energy cost factors (time-of-use pricing simulation)
        energy_cost_multiplier = self._get_energy_cost_multiplier(hour)
        
        # Ambient light classification
        if avg_ambient < 50:
            ambient_level = "dark"
            calibration_reliability = 0.95
        elif avg_ambient < 500:
            ambient_level = "dim"
            calibration_reliability = 0.85
        elif avg_ambient < 2000:
            ambient_level = "moderate"
            calibration_reliability = 0.65
        elif avg_ambient < 5000:
            ambient_level = "bright"
            calibration_reliability = 0.35
        else:
            ambient_level = "very_bright"
            calibration_reliability = 0.15
        
        return {
            'timestamp': current_time,
            'average_ambient_lux': avg_ambient,
            'ambient_level': ambient_level,
            'calibration_reliability': calibration_reliability,
            'is_daytime': is_daytime,
            'is_peak_growth_time': is_peak_growth_time,
            'energy_cost_multiplier': energy_cost_multiplier,
            'hour_of_day': hour,
            'sensor_readings': sensor_readings
        }
    
    def _calculate_zone_requirements(self, current_time: datetime) -> Dict[str, Dict]:
        """Calculate current light requirements for each zone."""
        zone_requirements = {}
        
        for zone_key, zone_config in self.zones_config.get('zones', {}).items():
            crop_type = zone_config.get('crop_type', 'herbs')
            growth_stage = zone_config.get('growth_stage', 'vegetative')
            
            # Get base requirements from zone configuration
            light_spectrum = zone_config.get('light_spectrum', {})
            base_par_target = light_spectrum.get('par_target', 200)
            
            # Apply growth schedule
            schedule = self.growth_schedules.get(crop_type, self.growth_schedules['herbs'])
            is_light_period = self._is_in_light_period(current_time, schedule)
            
            # Apply growth stage modifiers
            stage_modifiers = {
                'seedling': {'par_multiplier': 0.6, 'priority': 1.0},
                'vegetative': {'par_multiplier': 0.8, 'priority': 0.8},
                'flowering': {'par_multiplier': 1.2, 'priority': 1.0},
                'fruiting': {'par_multiplier': 1.5, 'priority': 0.9}
            }
            
            modifier = stage_modifiers.get(growth_stage, stage_modifiers['vegetative'])
            
            if is_light_period:
                target_par = base_par_target * modifier['par_multiplier']
                priority = modifier['priority']
            else:
                # During dark period, minimal or no lighting
                target_par = base_par_target * 0.1 if crop_type == 'tomatoes' else 0
                priority = 0.2
            
            zone_requirements[zone_key] = {
                'target_par': target_par,
                'target_color_temp': light_spectrum.get('color_temperature', 4000),
                'target_spectrum': {
                    'blue_percent': light_spectrum.get('blue_percent', 25),
                    'green_percent': light_spectrum.get('green_percent', 35),
                    'red_percent': light_spectrum.get('red_percent', 40)
                },
                'priority': priority,
                'crop_type': crop_type,
                'growth_stage': growth_stage,
                'is_light_period': is_light_period,
                'schedule': schedule
            }
        
        return zone_requirements
    
    def _make_individual_light_decision(self, light_id: str, conditions: Dict,
                                      zone_requirements: Dict, sensor_readings: Dict,
                                      current_time: datetime) -> LightDecision:
        """Make a decision for an individual light."""
        light_config = self.lights_config[light_id]
        zone_key = light_config.get('zone_key')
        
        # Initialize decision variables
        should_be_on = False
        intensity_percent = 0.0
        confidence = 0.5
        primary_reason = LightDecisionReason.ENERGY_EFFICIENCY
        contributing_factors = []
        
        # Factor 1: Zone Requirements
        if zone_key and zone_key in zone_requirements:
            zone_req = zone_requirements[zone_key]
            
            if zone_req['target_par'] > 0:
                # Calculate how much this light contributes to meeting the target
                light_contribution = self._calculate_light_contribution(
                    light_id, zone_key, sensor_readings
                )
                
                if light_contribution['par_contribution'] > 0:
                    should_be_on = True
                    intensity_percent = min(100.0, 
                        (zone_req['target_par'] / light_contribution['max_par_contribution']) * 100
                    )
                    primary_reason = LightDecisionReason.TARGET_REQUIREMENT
                    contributing_factors.append(f"Zone {zone_key} needs {zone_req['target_par']:.0f} PAR")
                    confidence += 0.3
        
        # Factor 2: Plant Schedule
        if zone_key and zone_key in zone_requirements:
            zone_req = zone_requirements[zone_key]
            if zone_req['is_light_period']:
                should_be_on = True
                contributing_factors.append(f"In light period for {zone_req['crop_type']}")
                confidence += 0.2
                if primary_reason == LightDecisionReason.ENERGY_EFFICIENCY:
                    primary_reason = LightDecisionReason.PLANT_SCHEDULE
            else:
                should_be_on = False
                intensity_percent = 0.0
                contributing_factors.append("Outside light period")
                confidence += 0.2
        
        # Factor 3: Daily Light Integral (DLI)
        if zone_key and zone_key in zone_requirements:
            zone_req = zone_requirements[zone_key]
            crop_type = zone_req.get('crop_type')
            
            # Get DLI target from zone config first, then growth schedule
            zone_dli_config = self.zones_config.get('zones', {}).get(zone_key, {}).get('dli_config', {})
            target_dli = zone_dli_config.get('target_dli')
            
            if not target_dli and crop_type and crop_type in self.growth_schedules:
                target_dli = self.growth_schedules[crop_type].get('target_dli', 15.0)
            elif not target_dli:
                target_dli = 15.0  # Default fallback
            
            dli_progress = self.dli_tracker.get_dli_progress(zone_key, target_dli)
            
            if not dli_progress['is_target_met'] and should_be_on:
                # Calculate how much intensity is needed to meet DLI target
                remaining_hours = self._calculate_remaining_light_hours_for_zone(current_time, zone_key)
                if remaining_hours > 0:
                    # Calculate required intensity to meet remaining DLI
                    required_intensity = self._calculate_dli_intensity_requirement(
                        dli_progress['remaining_dli'], remaining_hours, light_id
                    )
                    
                    if required_intensity > intensity_percent:
                        intensity_percent = min(100.0, required_intensity)
                        contributing_factors.append(f"DLI: {dli_progress['progress_percent']:.0f}% complete")
                        confidence += 0.2
                else:
                    # No more light hours available today, don't run
                    if not dli_progress['is_target_met']:
                        should_be_on = False
                        intensity_percent = 0.0
                        contributing_factors.append("DLI period ended for today")
            
            elif dli_progress['is_target_met'] and should_be_on:
                # Target already met, reduce intensity or turn off
                if dli_progress['progress_percent'] > 110:  # More than 10% over target
                    should_be_on = False
                    intensity_percent = 0.0
                    contributing_factors.append("DLI target exceeded")
                    primary_reason = LightDecisionReason.TARGET_REQUIREMENT
                else:
                    # Reduce intensity to maintain but not exceed target
                    intensity_percent *= 0.7
                    contributing_factors.append("DLI target met, maintaining")
            
            # Update DLI tracking with current light contribution
            if should_be_on and intensity_percent > 0:
                # Estimate current lux contribution for DLI tracking
                estimated_lux = self._estimate_light_lux_contribution(light_id, intensity_percent)
                light_type = light_config.get('type', 'LED_BASIC').lower()
                self.dli_tracker.add_reading(
                    zone_key, 
                    estimated_lux, 
                    current_time, 
                    duration_minutes=1,  # Assume 1-minute reading interval
                    light_type=light_type
                )
        
        # Factor 4: Ambient Light Conditions
        ambient_contribution = conditions['average_ambient_lux']
        if ambient_contribution > 1000:  # Bright ambient light
            # Reduce artificial light intensity
            ambient_reduction = min(0.8, ambient_contribution / 5000)
            intensity_percent *= (1 - ambient_reduction)
            contributing_factors.append(f"Reduced due to {ambient_contribution:.0f} lux ambient")
            if conditions['calibration_reliability'] < 0.3:
                confidence *= 0.5  # Low confidence in bright conditions
        
        # Factor 4: Energy Efficiency
        power_consumption = light_config.get('power_watts', 50) * (intensity_percent / 100)
        energy_cost = power_consumption * self.decision_params['energy_cost_per_kwh'] / 1000
        
        if conditions['energy_cost_multiplier'] > 1.5:  # Peak energy rates
            if intensity_percent > 50:
                intensity_percent *= 0.8  # Reduce intensity during peak rates
                contributing_factors.append("Reduced for peak energy rates")
        
        # Factor 5: Sensor Feedback
        current_light_effect = self._estimate_current_light_effect(light_id, sensor_readings)
        if should_be_on and current_light_effect['effectiveness'] < 0.5:
            confidence *= 0.7  # Reduce confidence if light seems ineffective
            contributing_factors.append("Low measured effectiveness")
        
        # Factor 6: Historical Performance
        historical_performance = self._get_historical_performance(light_id, current_time)
        if historical_performance['success_rate'] < 0.6:
            confidence *= 0.8
            contributing_factors.append("Poor historical performance")
        
        # Factor 7: Manual Overrides (check for any manual settings)
        manual_override = self._check_manual_override(light_id)
        if manual_override:
            should_be_on = manual_override['state']
            intensity_percent = manual_override['intensity']
            primary_reason = LightDecisionReason.MANUAL_OVERRIDE
            confidence = 1.0
            contributing_factors = ["Manual override active"]
        
        # Calculate priority score
        priority_score = self._calculate_priority_score(
            light_id, zone_requirements, conditions, confidence
        )
        
        # Estimate effects
        estimated_effect = self._estimate_light_effects(light_id, intensity_percent)
        
        # Calculate next evaluation time
        next_eval = current_time + timedelta(
            seconds=self.decision_params['decision_update_interval']
        )
        
        return LightDecision(
            light_id=light_id,
            should_be_on=should_be_on,
            intensity_percent=max(0.0, min(100.0, intensity_percent)),
            confidence=max(0.0, min(1.0, confidence)),
            primary_reason=primary_reason,
            contributing_factors=contributing_factors,
            estimated_effect=estimated_effect,
            power_consumption=power_consumption,
            priority_score=priority_score,
            next_evaluation_time=next_eval
        )
    
    def _optimize_decisions_globally(self, decisions: List[LightDecision], 
                                   conditions: Dict) -> List[LightDecision]:
        """Optimize decisions globally to avoid conflicts and improve efficiency."""
        optimized = decisions.copy()
        
        # Sort by priority score
        optimized.sort(key=lambda d: d.priority_score, reverse=True)
        
        # Check for power constraints
        total_power = sum(d.power_consumption for d in optimized if d.should_be_on)
        max_power_budget = 1000  # Watts - could be configurable
        
        if total_power > max_power_budget:
            # Reduce power by turning off lowest priority lights
            current_power = 0
            for decision in optimized:
                if decision.should_be_on:
                    if current_power + decision.power_consumption <= max_power_budget:
                        current_power += decision.power_consumption
                    else:
                        decision.should_be_on = False
                        decision.intensity_percent = 0.0
                        decision.contributing_factors.append("Disabled due to power budget")
                        decision.confidence *= 0.5
        
        # Check for zone conflicts (multiple lights in same zone)
        zone_lights = {}
        for decision in optimized:
            light_config = self.lights_config[decision.light_id]
            zone_key = light_config.get('zone_key')
            if zone_key:
                if zone_key not in zone_lights:
                    zone_lights[zone_key] = []
                zone_lights[zone_key].append(decision)
        
        # Optimize within each zone
        for zone_key, zone_decisions in zone_lights.items():
            if len(zone_decisions) > 1:
                self._optimize_zone_decisions(zone_decisions, zone_key)
        
        return optimized
    
    def _calculate_light_contribution(self, light_id: str, zone_key: str, 
                                    sensor_readings: Dict) -> Dict:
        """Calculate how much a light contributes to zone illumination."""
        # Get sensors in this zone
        zone_sensors = [
            sensor_id for sensor_id, sensor_config in self.sensors_config.items()
            if sensor_config.get('zone_key') == zone_key
        ]
        
        if not zone_sensors:
            return {'par_contribution': 0, 'max_par_contribution': 0}
        
        # Get light effects from calibration data
        light_effects = self.calibration_data.get('light_effects', {}).get(light_id, {})
        
        # Calculate average contribution across zone sensors
        contributions = []
        for sensor_id in zone_sensors:
            effect = light_effects.get(sensor_id, 0)
            # Convert lux to approximate PAR (rough conversion)
            par_effect = effect * 0.2  # 1 lux ≈ 0.2 PAR for LED lights
            contributions.append(par_effect)
        
        avg_contribution = sum(contributions) / len(contributions) if contributions else 0
        
        return {
            'par_contribution': avg_contribution,
            'max_par_contribution': avg_contribution,  # Simplified
            'zone_sensors': zone_sensors,
            'sensor_effects': {s: light_effects.get(s, 0) for s in zone_sensors}
        }
    
    def _is_in_light_period(self, current_time: datetime, schedule: Dict) -> bool:
        """Check if current time is within the light period for a crop."""
        start_str = schedule['preferred_start_time']
        end_str = schedule['preferred_end_time']
        
        start_hour, start_min = map(int, start_str.split(':'))
        end_hour, end_min = map(int, end_str.split(':'))
        
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        return start_minutes <= current_minutes <= end_minutes
    
    def _get_energy_cost_multiplier(self, hour: int) -> float:
        """Get energy cost multiplier based on configurable time-of-use pricing."""
        # Check each pricing tier to find which one applies
        for tier_name, tier_config in self.time_of_use_pricing.items():
            if hour in tier_config['hours']:
                return tier_config['multiplier']
        
        # Default to standard rate if not found
        return 1.5
    
    def _estimate_current_light_effect(self, light_id: str, 
                                     sensor_readings: Dict) -> Dict:
        """Estimate how effective a light currently is."""
        # This would compare expected vs actual sensor readings
        # Simplified implementation
        light_effects = self.calibration_data.get('light_effects', {}).get(light_id, {})
        
        effectiveness_scores = []
        for sensor_id, expected_effect in light_effects.items():
            current_reading = sensor_readings.get(sensor_id, 0)
            baseline = self.calibration_data.get('baseline', {}).get(sensor_id, 0)
            
            if expected_effect > 0:
                actual_above_baseline = max(0, current_reading - baseline)
                effectiveness = min(1.0, actual_above_baseline / expected_effect)
                effectiveness_scores.append(effectiveness)
        
        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0.5
        
        return {
            'effectiveness': avg_effectiveness,
            'sensor_count': len(effectiveness_scores)
        }
    
    def _get_historical_performance(self, light_id: str, current_time: datetime) -> Dict:
        """Get historical performance data for a light."""
        # Filter recent decisions for this light
        recent_decisions = [
            d for d in self.decision_history
            if d.get('light_id') == light_id and 
            (current_time - d.get('timestamp', current_time)).days <= 7
        ]
        
        if not recent_decisions:
            return {'success_rate': 0.7, 'avg_effectiveness': 0.7}  # Default
        
        success_count = sum(1 for d in recent_decisions if d.get('success', False))
        success_rate = success_count / len(recent_decisions)
        
        effectiveness_scores = [d.get('effectiveness', 0.5) for d in recent_decisions]
        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)
        
        return {
            'success_rate': success_rate,
            'avg_effectiveness': avg_effectiveness,
            'decision_count': len(recent_decisions)
        }
    
    def _check_manual_override(self, light_id: str) -> Optional[Dict]:
        """Check for any manual overrides for this light."""
        # This would check a manual override system
        # Placeholder implementation
        return None
    
    def _calculate_priority_score(self, light_id: str, zone_requirements: Dict,
                                conditions: Dict, confidence: float) -> float:
        """Calculate priority score for light decision."""
        light_config = self.lights_config[light_id]
        zone_key = light_config.get('zone_key')
        
        score = confidence  # Base score from confidence
        
        if zone_key and zone_key in zone_requirements:
            zone_req = zone_requirements[zone_key]
            score += zone_req['priority'] * 0.5
            
            if zone_req['is_light_period']:
                score += 0.3
                
            if conditions['is_peak_growth_time']:
                score += 0.2
        
        # Penalize high power consumption during peak energy times
        power_watts = light_config.get('power_watts', 50)
        if conditions['energy_cost_multiplier'] > 1.5 and power_watts > 75:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _estimate_light_effects(self, light_id: str, intensity_percent: float) -> Dict:
        """Estimate the effects of turning on a light at given intensity."""
        light_effects = self.calibration_data.get('light_effects', {}).get(light_id, {})
        
        estimated_effects = {}
        for sensor_id, base_effect in light_effects.items():
            # Scale effect by intensity
            scaled_effect = base_effect * (intensity_percent / 100.0)
            estimated_effects[sensor_id] = scaled_effect
        
        return estimated_effects
    
    def _optimize_zone_decisions(self, zone_decisions: List[LightDecision], zone_key: str):
        """Optimize decisions within a single zone."""
        # Sort by priority
        zone_decisions.sort(key=lambda d: d.priority_score, reverse=True)
        
        # For now, simple strategy: prefer highest priority light
        # Could implement more sophisticated multi-light optimization
        
        if len(zone_decisions) > 1:
            # Turn off lower priority lights if top light can handle the load
            primary = zone_decisions[0]
            if primary.confidence > 0.7 and primary.intensity_percent > 60:
                for decision in zone_decisions[1:]:
                    if decision.priority_score < primary.priority_score * 0.8:
                        decision.should_be_on = False
                        decision.intensity_percent = 0.0
                        decision.contributing_factors.append("Deferred to higher priority light in zone")
    
    def _record_decisions(self, decisions: List[LightDecision], 
                         sensor_readings: Dict, timestamp: datetime):
        """Record decisions for future learning."""
        for decision in decisions:
            record = {
                'timestamp': timestamp,
                'light_id': decision.light_id,
                'decision': {
                    'should_be_on': decision.should_be_on,
                    'intensity_percent': decision.intensity_percent,
                    'confidence': decision.confidence,
                    'primary_reason': decision.primary_reason.value,
                    'contributing_factors': decision.contributing_factors
                },
                'context': {
                    'sensor_readings': sensor_readings,
                    'estimated_effect': decision.estimated_effect
                }
            }
            self.decision_history.append(record)
        
        # Keep only recent history
        cutoff = timestamp - timedelta(days=30)
        self.decision_history = [
            r for r in self.decision_history 
            if r['timestamp'] > cutoff
        ]
    
    def get_decision_explanation(self, light_id: str, decision: LightDecision) -> str:
        """Generate human-readable explanation for a light decision."""
        light_config = self.lights_config[light_id]
        light_name = light_config.get('name', light_id)
        
        explanation = f"Light '{light_name}' decision: "
        
        if decision.should_be_on:
            explanation += f"ON at {decision.intensity_percent:.0f}% intensity"
        else:
            explanation += "OFF"
        
        explanation += f" (Confidence: {decision.confidence:.0%})"
        explanation += f"\n\nPrimary reason: {decision.primary_reason.value.replace('_', ' ').title()}"
        
        if decision.contributing_factors:
            explanation += "\n\nContributing factors:"
            for factor in decision.contributing_factors:
                explanation += f"\n• {factor}"
        
        explanation += f"\n\nExpected power consumption: {decision.power_consumption:.1f}W"
        explanation += f"\nPriority score: {decision.priority_score:.2f}"
        
        if decision.estimated_effect:
            explanation += "\n\nExpected sensor effects:"
            for sensor_id, effect in decision.estimated_effect.items():
                if abs(effect) > 0.1:
                    explanation += f"\n• {sensor_id}: {effect:+.1f} lux"
        
        return explanation
    
    def _calculate_remaining_light_hours(self, current_time: datetime, crop_type: str) -> float:
        """Calculate how many light hours remain for today for a specific crop."""
        if crop_type not in self.growth_schedules:
            return 8.0  # Default 8 hours
        
        schedule = self.growth_schedules[crop_type]
        start_time_str = schedule.get('preferred_start_time', '06:00')
        end_time_str = schedule.get('preferred_end_time', '20:00')
        
        # Parse time strings
        start_hour, start_min = map(int, start_time_str.split(':'))
        end_hour, end_min = map(int, end_time_str.split(':'))
        
        # Create datetime objects for today
        today = current_time.date()
        start_time = datetime.combine(today, datetime.min.time().replace(hour=start_hour, minute=start_min))
        end_time = datetime.combine(today, datetime.min.time().replace(hour=end_hour, minute=end_min))
        
        # Calculate remaining time
        if current_time >= end_time:
            return 0.0  # Light period ended
        elif current_time <= start_time:
            return (end_time - start_time).total_seconds() / 3600  # Full period remaining
        else:
            return (end_time - current_time).total_seconds() / 3600  # Partial period remaining
    
    def _calculate_remaining_light_hours_for_zone(self, current_time: datetime, zone_key: str) -> float:
        """Calculate how many light hours remain for today for a specific zone."""
        # First check zone-specific config
        zone_config = self.zones_config.get('zones', {}).get(zone_key, {})
        dli_config = zone_config.get('dli_config', {})
        
        start_time_str = dli_config.get('morning_start_time')
        end_time_str = dli_config.get('evening_end_time')
        
        # Fall back to crop type schedule if zone config not available
        if not start_time_str or not end_time_str:
            crop_type = zone_config.get('crop_type')
            if crop_type and crop_type in self.growth_schedules:
                schedule = self.growth_schedules[crop_type]
                start_time_str = start_time_str or schedule.get('preferred_start_time', '06:00')
                end_time_str = end_time_str or schedule.get('preferred_end_time', '20:00')
            else:
                start_time_str = start_time_str or '06:00'
                end_time_str = end_time_str or '20:00'
        
        # Parse time strings
        start_hour, start_min = map(int, start_time_str.split(':'))
        end_hour, end_min = map(int, end_time_str.split(':'))
        
        # Create datetime objects for today
        today = current_time.date()
        start_time = datetime.combine(today, datetime.min.time().replace(hour=start_hour, minute=start_min))
        end_time = datetime.combine(today, datetime.min.time().replace(hour=end_hour, minute=end_min))
        
        # Calculate remaining time
        if current_time >= end_time:
            return 0.0  # Light period ended
        elif current_time <= start_time:
            return (end_time - start_time).total_seconds() / 3600  # Full period remaining
        else:
            return (end_time - current_time).total_seconds() / 3600  # Partial period remaining
    
    def _calculate_dli_intensity_requirement(self, remaining_dli: float, remaining_hours: float, light_id: str) -> float:
        """Calculate required light intensity to meet remaining DLI target."""
        if remaining_hours <= 0:
            return 0.0
        
        # Get light specifications
        light_config = self.lights_config.get(light_id, {})
        max_ppfd = light_config.get('max_ppfd', 200)  # Default max PPFD
        
        # Calculate required PPFD
        # DLI (mol/m²/day) = PPFD (μmol/m²/s) * photoperiod (hours) * 3600 (s/h) * 1e-6 (μmol to mol)
        required_ppfd = (remaining_dli * 1_000_000) / (remaining_hours * 3600)
        
        # Convert to intensity percentage
        intensity_percent = (required_ppfd / max_ppfd) * 100
        
        return min(100.0, max(0.0, intensity_percent))
    
    def _estimate_light_lux_contribution(self, light_id: str, intensity_percent: float) -> float:
        """Estimate lux contribution from a light at given intensity."""
        light_config = self.lights_config.get(light_id, {})
        
        # Get calibration data for this light
        if 'light_effects' in self.calibration_data and light_id in self.calibration_data['light_effects']:
            # Use average of all sensor readings as baseline lux contribution
            sensor_effects = self.calibration_data['light_effects'][light_id]
            average_lux_contribution = sum(sensor_effects.values()) / len(sensor_effects)
        else:
            # Estimate based on light type and power
            power_watts = light_config.get('power_watts', 50)
            light_type = light_config.get('type', 'LED_BASIC')
            
            # Rough estimates of lux per watt for different light types
            lux_per_watt = {
                'LED_STRIP': 80,
                'GROW_PANEL': 100,
                'LED_BASIC': 60,
                'RGB_ARRAY': 70
            }
            
            efficiency = lux_per_watt.get(light_type, 70)
            average_lux_contribution = power_watts * efficiency
        
        # Scale by intensity percentage
        return average_lux_contribution * (intensity_percent / 100)
    
    def get_dli_status(self, zone_key: str = None) -> Dict:
        """Get current DLI status for all zones or a specific zone."""
        today = date.today()
        status = {}
        
        zones_to_check = [zone_key] if zone_key else self.zones_config.get('zones', {}).keys()
        
        for zone in zones_to_check:
            if zone in self.zones_config.get('zones', {}):
                zone_config = self.zones_config['zones'][zone]
                crop_type = zone_config.get('crop_type', 'unknown')
                
                if crop_type in self.growth_schedules:
                    target_dli = self.growth_schedules[crop_type].get('target_dli', 15.0)
                    dli_progress = self.dli_tracker.get_dli_progress(zone, target_dli, today)
                    
                    status[zone] = {
                        'crop_type': crop_type,
                        'target_dli': target_dli,
                        'current_dli': dli_progress['current_dli'],
                        'progress_percent': dli_progress['progress_percent'],
                        'remaining_dli': dli_progress['remaining_dli'],
                        'is_target_met': dli_progress['is_target_met'],
                        'remaining_hours': self._calculate_remaining_light_hours(datetime.now(), crop_type)
                    }
        
        return status