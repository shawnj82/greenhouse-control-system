#!/usr/bin/env python3
"""
Light Coverage Analysis Tool

Analyzes light coverage across zones and identifies areas with insufficient
or excessive lighting for optimal plant growth.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import math

def load_system_config(data_dir: str = "data") -> Tuple[Dict, Dict]:
    """Load lights and zones configuration."""
    lights_file = Path(data_dir) / "lights.json"
    zones_file = Path(data_dir) / "zones.json"
    
    lights = {}
    zones = {}
    
    if lights_file.exists():
        with open(lights_file, 'r') as f:
            data = json.load(f)
            lights = data.get('lights', data)
    
    if zones_file.exists():
        with open(zones_file, 'r') as f:
            data = json.load(f)
            zones = data.get('zones', data)
    
    return lights, zones

def get_plant_light_requirements(plant_type: str, growth_stage: str) -> Dict:
    """Get optimal light requirements for plant type and stage."""
    requirements = {
        'lettuce': {
            'vegetative': {'min_par': 120, 'optimal_par': 180, 'max_par': 250},
            'mature': {'min_par': 150, 'optimal_par': 200, 'max_par': 280}
        },
        'herbs': {
            'vegetative': {'min_par': 100, 'optimal_par': 150, 'max_par': 220},
            'mature': {'min_par': 120, 'optimal_par': 180, 'max_par': 250}
        },
        'flowers': {
            'vegetative': {'min_par': 200, 'optimal_par': 250, 'max_par': 400},
            'flowering': {'min_par': 300, 'optimal_par': 400, 'max_par': 600}
        },
        'tomatoes': {
            'vegetative': {'min_par': 250, 'optimal_par': 300, 'max_par': 450},
            'flowering': {'min_par': 400, 'optimal_par': 500, 'max_par': 700},
            'fruiting': {'min_par': 450, 'optimal_par': 600, 'max_par': 800}
        },
        'peppers': {
            'vegetative': {'min_par': 200, 'optimal_par': 280, 'max_par': 400},
            'flowering': {'min_par': 350, 'optimal_par': 450, 'max_par': 650},
            'fruiting': {'min_par': 400, 'optimal_par': 550, 'max_par': 750}
        },
        'seedlings': {
            'germination': {'min_par': 50, 'optimal_par': 100, 'max_par': 150},
            'early': {'min_par': 80, 'optimal_par': 120, 'max_par': 180}
        }
    }
    
    return requirements.get(plant_type, {}).get(growth_stage, 
                                              {'min_par': 100, 'optimal_par': 200, 'max_par': 300})

def analyze_zone_coverage(lights: Dict, zones: Dict) -> List[Dict]:
    """Analyze light coverage for each zone."""
    coverage_analysis = []
    
    for zone_id, zone_config in zones.items():
        # Find lights serving this zone
        zone_lights = []
        total_par = 0
        total_power = 0
        
        for light_id, light_config in lights.items():
            if light_config.get('zone_key') == zone_id:
                zone_lights.append({
                    'light_id': light_id,
                    'description': light_config.get('description', light_id),
                    'power_watts': light_config.get('power_watts', 50),
                    'par_at_canopy': light_config.get('par_at_canopy', 150)
                })
                total_par += light_config.get('par_at_canopy', 150)
                total_power += light_config.get('power_watts', 50)
        
        # Get plant requirements
        crop = zone_config.get('crop', {})
        plant_type = crop.get('type', 'unknown')
        growth_stage = crop.get('growth_stage', 'vegetative')
        requirements = get_plant_light_requirements(plant_type, growth_stage)
        
        # Analyze coverage adequacy
        min_par = requirements['min_par']
        optimal_par = requirements['optimal_par']
        max_par = requirements['max_par']
        
        # Determine coverage status
        if total_par == 0:
            status = 'no_coverage'
            adequacy = 0
        elif total_par < min_par:
            status = 'insufficient'
            adequacy = total_par / min_par
        elif total_par <= max_par:
            status = 'adequate'
            adequacy = min(1.0, total_par / optimal_par)
        else:
            status = 'excessive'
            adequacy = max_par / total_par  # Inverse for excessive
        
        # Calculate efficiency (PAR per watt)
        efficiency = total_par / total_power if total_power > 0 else 0
        
        coverage_analysis.append({
            'zone_id': zone_id,
            'zone_description': zone_config.get('description', zone_id),
            'plant_type': plant_type,
            'growth_stage': growth_stage,
            'lights_count': len(zone_lights),
            'zone_lights': zone_lights,
            'total_par': total_par,
            'total_power_watts': total_power,
            'efficiency_par_per_watt': round(efficiency, 2),
            'requirements': requirements,
            'coverage_status': status,
            'adequacy_score': round(adequacy, 2),
            'recommendations': generate_coverage_recommendations(
                status, total_par, requirements, total_power, zone_lights
            )
        })
    
    return coverage_analysis

def generate_coverage_recommendations(status: str, current_par: int, requirements: Dict, 
                                    current_power: int, lights: List[Dict]) -> List[str]:
    """Generate specific recommendations for improving zone coverage."""
    recommendations = []
    
    min_par = requirements['min_par']
    optimal_par = requirements['optimal_par']
    max_par = requirements['max_par']
    
    if status == 'no_coverage':
        recommendations.extend([
            f"🚨 CRITICAL: Install lighting for this zone",
            f"💡 Add LED providing {optimal_par} PAR minimum",
            f"📐 Calculate area to determine appropriate fixture size",
            f"🔌 Plan power and control wiring"
        ])
    
    elif status == 'insufficient':
        deficit = optimal_par - current_par
        recommendations.extend([
            f"⚠️ INSUFFICIENT: Need additional {deficit} PAR",
            f"💡 Add supplemental LED strips or increase existing power",
            f"🔄 Consider repositioning lights for better coverage",
            f"🪞 Add reflectors to improve light distribution"
        ])
        
        if len(lights) == 1 and lights[0]['power_watts'] < 100:
            recommendations.append("🔋 Upgrade to higher wattage LED fixture")
        elif len(lights) > 0:
            recommendations.append("➕ Add additional light fixtures")
    
    elif status == 'adequate':
        if current_par < optimal_par * 0.9:
            recommendations.append("📈 Consider small intensity boost for optimal growth")
        else:
            recommendations.append("✅ Coverage is appropriate for current plants")
        
        # Check efficiency
        avg_efficiency = current_par / current_power if current_power > 0 else 0
        if avg_efficiency < 2.0:  # Less than 2 PAR per watt is inefficient
            recommendations.append("⚡ Consider upgrading to more efficient LED technology")
    
    elif status == 'excessive':
        excess = current_par - max_par
        recommendations.extend([
            f"⚠️ EXCESSIVE: {excess} PAR over maximum safe level",
            f"🔥 Risk of light burn and plant stress",
            f"📏 Increase distance between lights and plants",
            f"🎛️ Reduce light intensity or duration",
            f"💰 Wasted energy - consider using excess for other zones"
        ])
        
        if len(lights) > 1:
            recommendations.append("🔄 Redistribute some lights to underlit zones")
    
    return recommendations

def identify_coverage_problems(analysis: List[Dict]) -> Dict:
    """Identify overall coverage problems and optimization opportunities."""
    problems = {
        'critical_issues': [],
        'efficiency_opportunities': [],
        'redistribution_suggestions': [],
        'upgrade_priorities': []
    }
    
    no_coverage_zones = [a for a in analysis if a['coverage_status'] == 'no_coverage']
    insufficient_zones = [a for a in analysis if a['coverage_status'] == 'insufficient']
    excessive_zones = [a for a in analysis if a['coverage_status'] == 'excessive']
    
    # Critical issues
    if no_coverage_zones:
        problems['critical_issues'].append({
            'type': 'no_coverage',
            'count': len(no_coverage_zones),
            'zones': [z['zone_description'] for z in no_coverage_zones],
            'priority': 'IMMEDIATE'
        })
    
    if insufficient_zones:
        total_deficit = sum(z['requirements']['optimal_par'] - z['total_par'] 
                           for z in insufficient_zones)
        problems['critical_issues'].append({
            'type': 'insufficient_coverage',
            'count': len(insufficient_zones),
            'total_par_deficit': total_deficit,
            'zones': [z['zone_description'] for z in insufficient_zones],
            'priority': 'HIGH'
        })
    
    # Efficiency opportunities
    low_efficiency_zones = [a for a in analysis if a['efficiency_par_per_watt'] < 2.0 and a['total_power_watts'] > 0]
    if low_efficiency_zones:
        problems['efficiency_opportunities'].append({
            'type': 'low_efficiency',
            'count': len(low_efficiency_zones),
            'zones': [z['zone_description'] for z in low_efficiency_zones],
            'avg_efficiency': sum(z['efficiency_par_per_watt'] for z in low_efficiency_zones) / len(low_efficiency_zones)
        })
    
    # Redistribution suggestions
    if excessive_zones and insufficient_zones:
        problems['redistribution_suggestions'].append({
            'type': 'excess_to_deficit',
            'excessive_zones': [z['zone_description'] for z in excessive_zones],
            'insufficient_zones': [z['zone_description'] for z in insufficient_zones],
            'potential_savings': 'High - redistribute lights instead of buying new'
        })
    
    # Priority ranking
    for zone in analysis:
        if zone['coverage_status'] in ['no_coverage', 'insufficient']:
            priority_score = 0
            if zone['coverage_status'] == 'no_coverage':
                priority_score = 100
            else:
                priority_score = (zone['requirements']['optimal_par'] - zone['total_par']) / zone['requirements']['optimal_par'] * 100
            
            problems['upgrade_priorities'].append({
                'zone': zone['zone_description'],
                'priority_score': round(priority_score, 1),
                'issue': zone['coverage_status'],
                'estimated_cost': estimate_upgrade_cost(zone)
            })
    
    # Sort by priority
    problems['upgrade_priorities'].sort(key=lambda x: x['priority_score'], reverse=True)
    
    return problems

def estimate_upgrade_cost(zone_analysis: Dict) -> str:
    """Estimate cost to fix coverage issues for a zone."""
    status = zone_analysis['coverage_status']
    current_par = zone_analysis['total_par']
    optimal_par = zone_analysis['requirements']['optimal_par']
    
    if status == 'no_coverage':
        # Estimate based on required PAR
        if optimal_par <= 200:
            return "$25-50 (LED strip)"
        elif optimal_par <= 400:
            return "$50-100 (medium LED panel)"
        else:
            return "$100-200 (high-power LED)"
    
    elif status == 'insufficient':
        deficit = optimal_par - current_par
        if deficit <= 50:
            return "$15-30 (small supplemental LED)"
        elif deficit <= 150:
            return "$30-60 (additional LED strip)"
        else:
            return "$60-120 (major light addition)"
    
    return "Analysis needed"

def print_coverage_analysis(analysis: List[Dict], problems: Dict):
    """Print formatted coverage analysis results."""
    print("💡 LIGHT COVERAGE ANALYSIS REPORT")
    print("=" * 50)
    print(f"Analysis Date: {datetime.now().isoformat()}")
    print(f"Zones Analyzed: {len(analysis)}")
    print()
    
    # Summary by status
    status_counts = {}
    for zone in analysis:
        status = zone['coverage_status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("📊 COVERAGE SUMMARY:")
    status_emojis = {
        'no_coverage': '🚨',
        'insufficient': '⚠️',
        'adequate': '✅',
        'excessive': '🔥'
    }
    
    for status, count in status_counts.items():
        emoji = status_emojis.get(status, '❓')
        print(f"   {emoji} {status.replace('_', ' ').title()}: {count} zones")
    print()
    
    # Critical issues
    if problems['critical_issues']:
        print("🚨 CRITICAL ISSUES:")
        for issue in problems['critical_issues']:
            print(f"   • {issue['type'].replace('_', ' ').title()}: {issue['count']} zones")
            print(f"     Zones: {', '.join(issue['zones'][:3])}")
            if len(issue['zones']) > 3:
                print(f"     ... and {len(issue['zones']) - 3} more")
        print()
    
    # Top priority upgrades
    if problems['upgrade_priorities']:
        print("🎯 TOP UPGRADE PRIORITIES:")
        for i, priority in enumerate(problems['upgrade_priorities'][:5], 1):
            print(f"   {i}. {priority['zone']} (Score: {priority['priority_score']})")
            print(f"      Issue: {priority['issue'].replace('_', ' ').title()}")
            print(f"      Est. Cost: {priority['estimated_cost']}")
        print()
    
    # Detailed zone analysis
    print("🔍 DETAILED ZONE ANALYSIS:")
    for zone in analysis:
        status_emoji = status_emojis.get(zone['coverage_status'], '❓')
        print(f"{status_emoji} {zone['zone_description']}")
        print(f"   Plant: {zone['plant_type']} ({zone['growth_stage']})")
        print(f"   Current PAR: {zone['total_par']} (Optimal: {zone['requirements']['optimal_par']})")
        print(f"   Power: {zone['total_power_watts']}W (Efficiency: {zone['efficiency_par_per_watt']} PAR/W)")
        print(f"   Lights: {zone['lights_count']} fixtures")
        
        if zone['recommendations']:
            print("   🔧 Recommendations:")
            for rec in zone['recommendations'][:2]:  # Show top 2
                print(f"      {rec}")
        print()

def main():
    """Run light coverage analysis."""
    try:
        print("💡 Analyzing Light Coverage...")
        
        lights, zones = load_system_config()
        
        if not zones:
            print("❌ No zones configuration found. Please set up zones first.")
            return
        
        analysis = analyze_zone_coverage(lights, zones)
        problems = identify_coverage_problems(analysis)
        
        print_coverage_analysis(analysis, problems)
        
        # Save detailed report
        report = {
            'timestamp': datetime.now().isoformat(),
            'zone_analysis': analysis,
            'problems_identified': problems,
            'summary': {
                'total_zones': len(analysis),
                'adequate_zones': len([a for a in analysis if a['coverage_status'] == 'adequate']),
                'problem_zones': len([a for a in analysis if a['coverage_status'] in ['no_coverage', 'insufficient']]),
                'total_par_deficit': sum(max(0, a['requirements']['optimal_par'] - a['total_par']) for a in analysis)
            }
        }
        
        report_file = Path("data") / "light_coverage_analysis.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📄 Detailed report saved to: {report_file}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()