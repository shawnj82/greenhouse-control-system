#!/usr/bin/env python3
"""
Shared Relay Conflict Analysis Tool

This tool analyzes potential conflicts when lights serving different plant types
share a relay, and provides intelligent recommendations for grouping decisions.
"""

import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime, time
from pathlib import Path

def load_config_files(data_dir: str = "data") -> Tuple[Dict, Dict, Dict]:
    """Load all configuration files."""
    files = ['lights.json', 'zones.json', 'relay_groups.json']
    configs = []
    
    for filename in files:
        filepath = Path(data_dir) / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Extract the main data section
                if filename == 'lights.json':
                    configs.append(data.get('lights', {}))
                elif filename == 'zones.json':
                    configs.append(data.get('zones', {}))
                else:
                    configs.append(data.get('relay_groups', {}))
        else:
            configs.append({})
    
    return tuple(configs)

def get_plant_light_requirements(plant_type: str, growth_stage: str = "vegetative") -> Dict:
    """Get lighting requirements for different plant types and growth stages."""
    
    plant_profiles = {
        'lettuce': {
            'vegetative': {
                'ideal_par': 180,
                'min_par': 120,
                'max_par': 250,
                'ideal_color_temp': 4000,
                'spectrum_preference': {'red': 35, 'blue': 25, 'green': 40},
                'daily_light_hours': 14,
                'morning_start': time(6, 0),
                'evening_end': time(20, 0),
                'light_sensitivity': 'medium'
            },
            'harvest_ready': {
                'ideal_par': 200,
                'min_par': 150,
                'max_par': 280,
                'ideal_color_temp': 4200,
                'spectrum_preference': {'red': 40, 'blue': 20, 'green': 40},
                'daily_light_hours': 12,
                'morning_start': time(7, 0),
                'evening_end': time(19, 0),
                'light_sensitivity': 'medium'
            }
        },
        'flowers': {
            'vegetative': {
                'ideal_par': 250,
                'min_par': 200,
                'max_par': 400,
                'ideal_color_temp': 4500,
                'spectrum_preference': {'red': 30, 'blue': 35, 'green': 35},
                'daily_light_hours': 16,
                'morning_start': time(5, 30),
                'evening_end': time(21, 30),
                'light_sensitivity': 'low'
            },
            'flowering': {
                'ideal_par': 400,
                'min_par': 300,
                'max_par': 600,
                'ideal_color_temp': 3200,
                'spectrum_preference': {'red': 55, 'blue': 20, 'green': 25},
                'daily_light_hours': 12,
                'morning_start': time(6, 0),
                'evening_end': time(18, 0),
                'light_sensitivity': 'low'
            }
        },
        'herbs': {
            'vegetative': {
                'ideal_par': 150,
                'min_par': 100,
                'max_par': 220,
                'ideal_color_temp': 4200,
                'spectrum_preference': {'red': 32, 'blue': 28, 'green': 40},
                'daily_light_hours': 14,
                'morning_start': time(6, 30),
                'evening_end': time(20, 30),
                'light_sensitivity': 'high'
            },
            'mature': {
                'ideal_par': 180,
                'min_par': 120,
                'max_par': 250,
                'ideal_color_temp': 4000,
                'spectrum_preference': {'red': 35, 'blue': 25, 'green': 40},
                'daily_light_hours': 12,
                'morning_start': time(7, 0),
                'evening_end': time(19, 0),
                'light_sensitivity': 'high'
            }
        },
        'tomatoes': {
            'vegetative': {
                'ideal_par': 300,
                'min_par': 250,
                'max_par': 450,
                'ideal_color_temp': 4000,
                'spectrum_preference': {'red': 40, 'blue': 25, 'green': 35},
                'daily_light_hours': 16,
                'morning_start': time(5, 0),
                'evening_end': time(21, 0),
                'light_sensitivity': 'low'
            },
            'flowering': {
                'ideal_par': 500,
                'min_par': 400,
                'max_par': 700,
                'ideal_color_temp': 3500,
                'spectrum_preference': {'red': 50, 'blue': 20, 'green': 30},
                'daily_light_hours': 14,
                'morning_start': time(5, 30),
                'evening_end': time(19, 30),
                'light_sensitivity': 'low'
            },
            'fruiting': {
                'ideal_par': 600,
                'min_par': 450,
                'max_par': 800,
                'ideal_color_temp': 3200,
                'spectrum_preference': {'red': 60, 'blue': 15, 'green': 25},
                'daily_light_hours': 12,
                'morning_start': time(6, 0),
                'evening_end': time(18, 0),
                'light_sensitivity': 'very_low'
            }
        }
    }
    
    return plant_profiles.get(plant_type, {}).get(growth_stage, {})

def calculate_schedule_conflict(req1: Dict, req2: Dict) -> Dict:
    """Calculate scheduling conflicts between two plant requirements."""
    
    # Extract timing info
    start1 = req1.get('morning_start', time(6, 0))
    end1 = req1.get('evening_end', time(20, 0))
    hours1 = req1.get('daily_light_hours', 14)
    
    start2 = req2.get('morning_start', time(6, 0))
    end2 = req2.get('evening_end', time(20, 0))
    hours2 = req2.get('daily_light_hours', 14)
    
    # Calculate overlaps and conflicts
    earliest_start = min(start1, start2)
    latest_end = max(end1, end2)
    
    # Convert times to minutes for easier calculation
    def time_to_minutes(t):
        return t.hour * 60 + t.minute
    
    start1_min = time_to_minutes(start1)
    end1_min = time_to_minutes(end1)
    start2_min = time_to_minutes(start2)
    end2_min = time_to_minutes(end2)
    
    # Find overlap period
    overlap_start = max(start1_min, start2_min)
    overlap_end = min(end1_min, end2_min)
    overlap_minutes = max(0, overlap_end - overlap_start)
    
    # Calculate total needed period
    total_start = min(start1_min, start2_min)
    total_end = max(end1_min, end2_min)
    total_minutes = total_end - total_start
    
    conflict_score = 1.0 - (overlap_minutes / total_minutes) if total_minutes > 0 else 0
    
    return {
        'schedule_overlap_hours': overlap_minutes / 60,
        'total_schedule_hours': total_minutes / 60,
        'schedule_conflict_score': conflict_score,
        'earliest_start': earliest_start,
        'latest_end': latest_end,
        'wasted_light_hours': (total_minutes - max(hours1 * 60, hours2 * 60)) / 60
    }

def calculate_spectrum_conflict(req1: Dict, req2: Dict) -> Dict:
    """Calculate spectrum conflicts between two plant requirements."""
    
    spectrum1 = req1.get('spectrum_preference', {})
    spectrum2 = req2.get('spectrum_preference', {})
    
    if not spectrum1 or not spectrum2:
        return {'spectrum_conflict_score': 0, 'spectrum_compatibility': 'unknown'}
    
    # Calculate differences in spectrum preferences
    conflicts = {}
    total_difference = 0
    
    for color in ['red', 'blue', 'green']:
        pref1 = spectrum1.get(color, 33)  # Default to equal split
        pref2 = spectrum2.get(color, 33)
        difference = abs(pref1 - pref2)
        conflicts[f'{color}_difference'] = difference
        total_difference += difference
    
    # Color temperature conflict
    temp1 = req1.get('ideal_color_temp', 4000)
    temp2 = req2.get('ideal_color_temp', 4000)
    temp_difference = abs(temp1 - temp2)
    
    # Calculate overall spectrum conflict score (0 = no conflict, 1 = major conflict)
    spectrum_conflict = (total_difference / 300) + (temp_difference / 10000)  # Normalized
    spectrum_conflict = min(1.0, spectrum_conflict)
    
    # Determine compatibility level
    if spectrum_conflict < 0.1:
        compatibility = 'excellent'
    elif spectrum_conflict < 0.3:
        compatibility = 'good'
    elif spectrum_conflict < 0.6:
        compatibility = 'moderate'
    else:
        compatibility = 'poor'
    
    return {
        'spectrum_conflict_score': spectrum_conflict,
        'spectrum_compatibility': compatibility,
        'color_differences': conflicts,
        'color_temp_difference': temp_difference
    }

def calculate_intensity_conflict(req1: Dict, req2: Dict) -> Dict:
    """Calculate light intensity conflicts between two plant requirements."""
    
    par1 = req1.get('ideal_par', 200)
    min1 = req1.get('min_par', par1 * 0.7)
    max1 = req1.get('max_par', par1 * 1.4)
    
    par2 = req2.get('ideal_par', 200)
    min2 = req2.get('min_par', par2 * 0.7)
    max2 = req2.get('max_par', par2 * 1.4)
    
    # Find overlap in acceptable ranges
    overlap_min = max(min1, min2)
    overlap_max = min(max1, max2)
    
    if overlap_max <= overlap_min:
        # No overlap - severe conflict
        intensity_conflict = 1.0
        compatibility = 'incompatible'
        compromise_par = None
    else:
        # Calculate how much of each plant's range is lost
        range1 = max1 - min1
        range2 = max2 - min2
        overlap_range = overlap_max - overlap_min
        
        # Conflict based on how much compromise is needed
        compromise_par = (overlap_min + overlap_max) / 2
        conflict1 = abs(par1 - compromise_par) / range1 if range1 > 0 else 0
        conflict2 = abs(par2 - compromise_par) / range2 if range2 > 0 else 0
        
        intensity_conflict = max(conflict1, conflict2)
        
        if intensity_conflict < 0.1:
            compatibility = 'excellent'
        elif intensity_conflict < 0.3:
            compatibility = 'good'
        elif intensity_conflict < 0.6:
            compatibility = 'moderate'
        else:
            compatibility = 'poor'
    
    return {
        'intensity_conflict_score': intensity_conflict,
        'intensity_compatibility': compatibility,
        'compromise_par': compromise_par,
        'plant1_par_loss': abs(par1 - compromise_par) if compromise_par else None,
        'plant2_par_loss': abs(par2 - compromise_par) if compromise_par else None,
        'acceptable_range': (overlap_min, overlap_max) if overlap_max > overlap_min else None
    }

def analyze_relay_group_conflicts(data_dir: str = "data") -> Dict:
    """Analyze all configured relay groups for plant conflicts."""
    
    lights_config, zones_config, relay_groups_config = load_config_files(data_dir)
    
    if not relay_groups_config:
        return {'error': 'No relay groups configured'}
    
    analysis_results = {
        'timestamp': datetime.now().isoformat(),
        'groups_analyzed': len(relay_groups_config),
        'conflict_summary': {
            'no_conflict': 0,
            'minor_conflict': 0,
            'major_conflict': 0,
            'severe_conflict': 0
        },
        'group_analyses': {}
    }
    
    for group_id, group_config in relay_groups_config.items():
        lights_in_group = group_config.get('lights', [])
        
        # Find zones affected by each light
        light_zones = {}
        for light_id in lights_in_group:
            light_config = lights_config.get(light_id, {})
            zone_key = light_config.get('zone_key')
            if zone_key:
                light_zones[light_id] = zones_config.get(zone_key, {})
        
        # Analyze conflicts between zones
        conflicts = []
        zone_pairs = []
        
        zone_list = list(light_zones.items())
        for i in range(len(zone_list)):
            for j in range(i + 1, len(zone_list)):
                light1_id, zone1 = zone_list[i]
                light2_id, zone2 = zone_list[j]
                
                # Extract plant information
                crop1 = zone1.get('crop', {})
                crop2 = zone2.get('crop', {})
                
                plant_type1 = crop1.get('type', 'unknown')
                growth_stage1 = crop1.get('growth_stage', 'vegetative')
                plant_type2 = crop2.get('type', 'unknown')
                growth_stage2 = crop2.get('growth_stage', 'vegetative')
                
                # Get requirements
                req1 = get_plant_light_requirements(plant_type1, growth_stage1)
                req2 = get_plant_light_requirements(plant_type2, growth_stage2)
                
                if req1 and req2:
                    # Analyze conflicts
                    schedule_conflict = calculate_schedule_conflict(req1, req2)
                    spectrum_conflict = calculate_spectrum_conflict(req1, req2)
                    intensity_conflict = calculate_intensity_conflict(req1, req2)
                    
                    # Calculate overall conflict score
                    overall_conflict = (
                        schedule_conflict['schedule_conflict_score'] * 0.4 +
                        spectrum_conflict['spectrum_conflict_score'] * 0.35 +
                        intensity_conflict['intensity_conflict_score'] * 0.25
                    )
                    
                    conflict_analysis = {
                        'light1': {'id': light1_id, 'plant': plant_type1, 'stage': growth_stage1},
                        'light2': {'id': light2_id, 'plant': plant_type2, 'stage': growth_stage2},
                        'schedule_conflict': schedule_conflict,
                        'spectrum_conflict': spectrum_conflict,
                        'intensity_conflict': intensity_conflict,
                        'overall_conflict_score': overall_conflict,
                        'conflict_level': _get_conflict_level(overall_conflict),
                        'recommendations': _generate_conflict_recommendations(
                            overall_conflict, schedule_conflict, spectrum_conflict, intensity_conflict
                        )
                    }
                    
                    conflicts.append(conflict_analysis)
        
        # Summarize group analysis
        if conflicts:
            max_conflict = max(c['overall_conflict_score'] for c in conflicts)
            avg_conflict = sum(c['overall_conflict_score'] for c in conflicts) / len(conflicts)
            conflict_level = _get_conflict_level(max_conflict)
        else:
            max_conflict = 0
            avg_conflict = 0
            conflict_level = 'no_conflict'
        
        analysis_results['group_analyses'][group_id] = {
            'group_description': group_config.get('description', group_id),
            'lights_count': len(lights_in_group),
            'zones_affected': len(light_zones),
            'max_conflict_score': max_conflict,
            'average_conflict_score': avg_conflict,
            'overall_conflict_level': conflict_level,
            'detailed_conflicts': conflicts,
            'group_recommendations': _generate_group_recommendations(conflicts, group_config)
        }
        
        # Update summary
        analysis_results['conflict_summary'][conflict_level] += 1
    
    return analysis_results

def _get_conflict_level(conflict_score: float) -> str:
    """Determine conflict level from score."""
    if conflict_score < 0.2:
        return 'no_conflict'
    elif conflict_score < 0.4:
        return 'minor_conflict'
    elif conflict_score < 0.7:
        return 'major_conflict'
    else:
        return 'severe_conflict'

def _generate_conflict_recommendations(overall_score: float, schedule: Dict, spectrum: Dict, intensity: Dict) -> List[str]:
    """Generate specific recommendations for resolving conflicts."""
    recommendations = []
    
    if overall_score < 0.2:
        recommendations.append("✅ Plants are compatible for shared relay control")
        return recommendations
    
    # Schedule conflicts
    if schedule['schedule_conflict_score'] > 0.3:
        recommendations.append(f"⏰ Schedule conflict: {schedule['wasted_light_hours']:.1f} hours of unnecessary lighting daily")
        recommendations.append(f"💡 Consider using timer switches or separate relays for different schedules")
    
    # Spectrum conflicts  
    if spectrum['spectrum_conflict_score'] > 0.3:
        spectrum_compat = spectrum['spectrum_compatibility']
        recommendations.append(f"🌈 Spectrum compatibility: {spectrum_compat}")
        if spectrum_compat in ['poor', 'moderate']:
            recommendations.append("💡 Consider using full-spectrum lights or separate channels")
    
    # Intensity conflicts
    if intensity['intensity_conflict_score'] > 0.3:
        intensity_compat = intensity['intensity_compatibility']
        recommendations.append(f"💪 Intensity compatibility: {intensity_compat}")
        if intensity_compat == 'incompatible':
            recommendations.append("❌ Plants require incompatible light intensities - separate relays strongly recommended")
        elif intensity['compromise_par']:
            recommendations.append(f"⚖️ Compromise intensity: {intensity['compromise_par']:.0f} PAR")
    
    # Overall recommendations
    if overall_score > 0.7:
        recommendations.append("🚨 SEVERE CONFLICT: Strong recommendation to use separate relays")
        recommendations.append("💰 Cost savings not worth plant health compromise")
    elif overall_score > 0.4:
        recommendations.append("⚠️ MAJOR CONFLICT: Consider if cost savings justify plant compromise")
        recommendations.append("🔧 Evaluate using separate relay or relocating plants")
    
    return recommendations

def _generate_group_recommendations(conflicts: List[Dict], group_config: Dict) -> List[str]:
    """Generate recommendations for the entire relay group."""
    if not conflicts:
        return ["✅ No plant conflicts detected in this group"]
    
    recommendations = []
    max_conflict = max(c['overall_conflict_score'] for c in conflicts)
    
    if max_conflict > 0.7:
        recommendations.append("🚨 CRITICAL: This relay group has severe plant conflicts")
        recommendations.append("💡 Strongly recommend splitting into separate relays")
        recommendations.append("🔧 Alternative: Relocate plants with similar needs together")
    
    elif max_conflict > 0.4:
        recommendations.append("⚠️ WARNING: This relay group has significant conflicts")
        recommendations.append("💰 Evaluate if hardware savings justify plant health compromise")
        recommendations.append("🔄 Consider regrouping lights with more compatible plants")
    
    elif max_conflict > 0.2:
        recommendations.append("ℹ️ Minor conflicts detected - monitor plant health closely")
        recommendations.append("📊 Track plant performance to ensure adequate growth")
    
    else:
        recommendations.append("✅ Plants in this group are compatible for shared control")
        recommendations.append("💰 Good candidate for cost-effective relay sharing")
    
    # Add specific technical recommendations
    power_total = group_config.get('power_total_watts', 0)
    if power_total > 300:
        recommendations.append(f"⚡ High power group ({power_total}W) - ensure adequate relay rating")
    
    return recommendations

def print_conflict_analysis(analysis: Dict):
    """Print formatted conflict analysis results."""
    print("🔍 RELAY GROUP CONFLICT ANALYSIS")
    print("=" * 50)
    print(f"Analysis Date: {analysis['timestamp']}")
    print(f"Groups Analyzed: {analysis['groups_analyzed']}")
    print()
    
    # Summary
    summary = analysis['conflict_summary']
    print("📊 CONFLICT SUMMARY:")
    print(f"   ✅ No Conflicts: {summary['no_conflict']}")
    print(f"   ⚠️  Minor Conflicts: {summary['minor_conflict']}")
    print(f"   🟠 Major Conflicts: {summary['major_conflict']}")
    print(f"   🔴 Severe Conflicts: {summary['severe_conflict']}")
    print()
    
    # Detailed analysis
    for group_id, group_analysis in analysis['group_analyses'].items():
        print(f"👥 GROUP: {group_analysis['group_description']}")
        print(f"   Lights: {group_analysis['lights_count']}")
        print(f"   Zones Affected: {group_analysis['zones_affected']}")
        print(f"   Conflict Level: {group_analysis['overall_conflict_level'].replace('_', ' ').title()}")
        print(f"   Max Conflict Score: {group_analysis['max_conflict_score']:.2f}")
        
        # Recommendations
        print("   🔧 RECOMMENDATIONS:")
        for rec in group_analysis['group_recommendations']:
            print(f"      {rec}")
        
        # Detailed conflicts
        if group_analysis['detailed_conflicts']:
            print("   🔍 DETAILED CONFLICTS:")
            for conflict in group_analysis['detailed_conflicts']:
                plant1 = conflict['light1']
                plant2 = conflict['light2']
                score = conflict['overall_conflict_score']
                
                print(f"      {plant1['plant']} ({plant1['stage']}) vs {plant2['plant']} ({plant2['stage']})")
                print(f"      Conflict Score: {score:.2f}")
                
                for rec in conflict['recommendations'][:2]:  # Show top 2 recommendations
                    print(f"        {rec}")
        
        print()

def main():
    """Main function to run conflict analysis."""
    import sys
    
    # Check if we should use example data
    use_examples = len(sys.argv) > 1 and sys.argv[1] == "--examples"
    
    try:
        print("🔍 Analyzing Relay Group Conflicts...")
        
        if use_examples:
            print("📋 Using example conflict scenarios...")
            # Temporarily rename example files to be used by analysis
            import shutil
            backup_files = []
            
            example_mappings = [
                ("lights_examples.json", "lights.json"),
                ("zones_examples.json", "zones.json"), 
                ("relay_groups_examples.json", "relay_groups.json")
            ]
            
            data_dir = Path("data")
            
            # Backup existing files and use examples
            for example_file, target_file in example_mappings:
                example_path = data_dir / example_file
                target_path = data_dir / target_file
                backup_path = data_dir / f"{target_file}.backup"
                
                if target_path.exists():
                    shutil.copy2(target_path, backup_path)
                    backup_files.append((target_path, backup_path))
                
                if example_path.exists():
                    shutil.copy2(example_path, target_path)
            
            try:
                analysis = analyze_relay_group_conflicts()
            finally:
                # Restore original files
                for target_path, backup_path in backup_files:
                    shutil.copy2(backup_path, target_path)
                    backup_path.unlink()
        else:
            analysis = analyze_relay_group_conflicts()
        
        if 'error' in analysis:
            print(f"❌ {analysis['error']}")
            return
        
        print_conflict_analysis(analysis)
        
        # Save detailed report
        report_file = Path("data") / "relay_conflict_analysis.json"
        with open(report_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        print(f"📄 Detailed report saved to: {report_file}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()