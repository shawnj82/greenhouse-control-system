#!/usr/bin/env python3
"""
System Upgrade Analysis Tool

Analyzes your current grow light automation setup and provides personalized
upgrade recommendations based on detected issues and optimization opportunities.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class UpgradeRecommendation:
    category: str
    priority: str  # HIGH, MEDIUM, LOW
    title: str
    problem_description: str
    impact: str
    cost_range: str
    roi_timeline: str
    implementation_steps: List[str]
    tools_needed: List[str]
    success_metrics: List[str]

class SystemUpgradeAnalyzer:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.recommendations = []
        
    def load_system_data(self) -> Dict:
        """Load all system configuration data."""
        configs = {}
        
        config_files = [
            'lights.json', 'zones.json', 'relay_groups.json', 
            'errors.json', 'todos.json'
        ]
        
        for filename in config_files:
            filepath = self.data_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        # Extract main data section or use raw data
                        key = filename.replace('.json', '')
                        if isinstance(data, dict) and key in data:
                            configs[key] = data[key]
                        else:
                            configs[key] = data
                except Exception as e:
                    print(f"Warning: Could not load {filename}: {e}")
                    configs[key] = {}
            else:
                configs[key] = {}
        
        return configs
    
    def analyze_relay_conflicts(self, system_data: Dict) -> List[UpgradeRecommendation]:
        """Analyze shared relay configurations for plant conflicts."""
        recommendations = []
        
        lights = system_data.get('lights', {})
        zones = system_data.get('zones', {})
        relay_groups = system_data.get('relay_groups', {})
        
        if not relay_groups:
            return recommendations
        
        conflict_groups = []
        for group_id, group_config in relay_groups.items():
            lights_in_group = group_config.get('lights', [])
            if len(lights_in_group) < 2:
                continue
                
            # Check for plant type conflicts
            plant_types = []
            growth_stages = []
            
            for light_id in lights_in_group:
                light_config = lights.get(light_id, {})
                zone_key = light_config.get('zone_key')
                if zone_key and zone_key in zones:
                    zone = zones[zone_key]
                    crop = zone.get('crop', {})
                    plant_types.append(crop.get('type', 'unknown'))
                    growth_stages.append(crop.get('growth_stage', 'unknown'))
            
            # Detect conflicts
            unique_types = set(plant_types)
            unique_stages = set(growth_stages)
            
            has_conflict = False
            conflict_details = []
            
            # Check for incompatible plant combinations
            incompatible_pairs = [
                ('lettuce', 'flowers'),
                ('herbs', 'tomatoes'),
                ('lettuce', 'tomatoes'),
                ('seedlings', 'fruiting')
            ]
            
            for type1, type2 in incompatible_pairs:
                if type1 in plant_types and type2 in plant_types:
                    has_conflict = True
                    conflict_details.append(f"{type1} vs {type2}")
            
            # Check for growth stage conflicts
            stage_conflicts = [
                ('vegetative', 'flowering'),
                ('vegetative', 'fruiting'),
                ('seedling', 'mature')
            ]
            
            for stage1, stage2 in stage_conflicts:
                if stage1 in growth_stages and stage2 in growth_stages:
                    has_conflict = True
                    conflict_details.append(f"{stage1} vs {stage2} stages")
            
            if has_conflict:
                conflict_groups.append({
                    'group_id': group_id,
                    'description': group_config.get('description', group_id),
                    'conflicts': conflict_details,
                    'lights_count': len(lights_in_group),
                    'estimated_loss': len(conflict_details) * 25  # $25 per conflict per month
                })
        
        if conflict_groups:
            total_monthly_loss = sum(g['estimated_loss'] for g in conflict_groups)
            
            recommendations.append(UpgradeRecommendation(
                category="Relay Control",
                priority="HIGH",
                title="Resolve Shared Relay Plant Conflicts",
                problem_description=f"Found {len(conflict_groups)} relay groups with plant conflicts: " + 
                                  ", ".join([g['description'] for g in conflict_groups]),
                impact=f"Estimated ${total_monthly_loss}/month in reduced yields and energy waste",
                cost_range="$3-15 (additional relays)",
                roi_timeline="3-7 days",
                implementation_steps=[
                    "Run 'python analyze_relay_conflicts.py' for detailed analysis",
                    "Separate conflicting plant types into different relay groups",
                    "Install additional relays for incompatible combinations",
                    "Update relay_groups.json configuration",
                    "Test new groupings and monitor plant health"
                ],
                tools_needed=["analyze_relay_conflicts.py", "configure_shared_relays.py"],
                success_metrics=[
                    "No conflicting plant types in same relay group",
                    "Reduced manual light overrides",
                    "Improved plant health and growth rates",
                    "Energy consumption optimization"
                ]
            ))
        
        return recommendations
    
    def analyze_light_coverage(self, system_data: Dict) -> List[UpgradeRecommendation]:
        """Analyze light coverage and intensity issues."""
        recommendations = []
        
        lights = system_data.get('lights', {})
        zones = system_data.get('zones', {})
        
        if not lights or not zones:
            return recommendations
        
        coverage_issues = []
        intensity_issues = []
        
        for zone_id, zone_config in zones.items():
            # Find lights serving this zone
            zone_lights = [light_id for light_id, light_config in lights.items() 
                          if light_config.get('zone_key') == zone_id]
            
            if not zone_lights:
                coverage_issues.append({
                    'zone_id': zone_id,
                    'description': zone_config.get('description', zone_id),
                    'issue': 'no_lights'
                })
                continue
            
            # Check light intensity vs plant needs
            crop = zone_config.get('crop', {})
            plant_type = crop.get('type', 'unknown')
            growth_stage = crop.get('growth_stage', 'vegetative')
            
            # Estimate required PAR based on plant type
            par_requirements = {
                'lettuce': {'vegetative': 180, 'mature': 200},
                'herbs': {'vegetative': 150, 'mature': 180},
                'flowers': {'vegetative': 250, 'flowering': 400},
                'tomatoes': {'vegetative': 300, 'flowering': 500, 'fruiting': 600}
            }
            
            required_par = par_requirements.get(plant_type, {}).get(growth_stage, 200)
            
            # Check actual light output
            total_par = 0
            for light_id in zone_lights:
                light_config = lights[light_id]
                par_output = light_config.get('par_at_canopy', 150)  # Default assumption
                total_par += par_output
            
            if total_par < required_par * 0.8:  # 20% tolerance
                intensity_issues.append({
                    'zone_id': zone_id,
                    'description': zone_config.get('description', zone_id),
                    'required_par': required_par,
                    'actual_par': total_par,
                    'deficit': required_par - total_par,
                    'plant_type': plant_type,
                    'growth_stage': growth_stage
                })
        
        # Generate recommendations for coverage issues
        if coverage_issues:
            recommendations.append(UpgradeRecommendation(
                category="Light Coverage",
                priority="HIGH",
                title="Add Lighting to Uncovered Zones",
                problem_description=f"Found {len(coverage_issues)} zones without lighting: " +
                                  ", ".join([issue['description'] for issue in coverage_issues]),
                impact="Plants in these zones will have poor growth, stretching, or complete failure",
                cost_range="$25-75 per zone (LED strips or panels)",
                roi_timeline="2-4 weeks",
                implementation_steps=[
                    "Identify appropriate LED fixtures for each uncovered zone",
                    "Install lights with proper mounting and wiring",
                    "Add lights to lights.json configuration",
                    "Set up appropriate schedules and intensities",
                    "Monitor plant response and adjust as needed"
                ],
                tools_needed=["LED fixtures", "mounting hardware", "wiring supplies"],
                success_metrics=[
                    "All zones have adequate lighting",
                    "Improved plant growth rates",
                    "Reduced plant stretching",
                    "Even canopy development"
                ]
            ))
        
        # Generate recommendations for intensity issues
        if intensity_issues:
            total_deficit = sum(issue['deficit'] for issue in intensity_issues)
            avg_deficit = total_deficit / len(intensity_issues)
            
            recommendations.append(UpgradeRecommendation(
                category="Light Intensity",
                priority="HIGH" if avg_deficit > 100 else "MEDIUM",
                title="Increase Light Intensity for Underlit Zones",
                problem_description=f"Found {len(intensity_issues)} zones with insufficient light intensity. " +
                                  f"Average deficit: {avg_deficit:.0f} PAR",
                impact=f"Estimated 15-30% yield reduction in affected zones",
                cost_range="$15-50 per zone (supplemental LEDs or upgrades)",
                roi_timeline="3-6 weeks",
                implementation_steps=[
                    "Measure actual PAR levels with 'python test_tcs34725.py'",
                    "Add supplemental LED strips to boost intensity",
                    "Or replace existing lights with higher wattage units",
                    "Reposition lights for better coverage",
                    "Update light configurations in system"
                ],
                tools_needed=["PAR meter or TCS34725 sensor", "supplemental LEDs"],
                success_metrics=[
                    "All zones meeting minimum PAR requirements",
                    "Improved plant vigor and color",
                    "Faster growth rates",
                    "Better flowering/fruiting"
                ]
            ))
        
        return recommendations
    
    def analyze_energy_efficiency(self, system_data: Dict) -> List[UpgradeRecommendation]:
        """Analyze energy usage and efficiency opportunities."""
        recommendations = []
        
        lights = system_data.get('lights', {})
        relay_groups = system_data.get('relay_groups', {})
        
        if not lights:
            return recommendations
        
        # Calculate total system power
        total_watts = sum(light.get('power_watts', 50) for light in lights.values())
        
        # Estimate daily energy consumption (assume 14 hour average)
        daily_kwh = (total_watts * 14) / 1000
        monthly_kwh = daily_kwh * 30
        estimated_monthly_cost = monthly_kwh * 0.12  # $0.12/kWh average
        
        # Check for energy waste indicators
        waste_indicators = []
        
        # Look for lights with very long schedules
        for light_id, light_config in lights.items():
            power = light_config.get('power_watts', 50)
            # This would need schedule data to be more accurate
            # For now, flag high-power lights as potential optimization targets
            if power > 100:
                waste_indicators.append({
                    'type': 'high_power',
                    'light_id': light_id,
                    'power': power,
                    'potential_savings': power * 0.2  # Assume 20% efficiency gain possible
                })
        
        # Check for potential shared relay optimizations
        individual_lights = []
        for light_id, light_config in lights.items():
            # Check if light is NOT in any relay group
            in_group = any(light_id in group.get('lights', []) 
                          for group in relay_groups.values())
            if not in_group:
                individual_lights.append(light_id)
        
        if len(individual_lights) >= 2:
            waste_indicators.append({
                'type': 'missed_sharing',
                'count': len(individual_lights),
                'potential_savings': len(individual_lights) * 3  # $3 per relay
            })
        
        if estimated_monthly_cost > 50 or waste_indicators:
            priority = "HIGH" if estimated_monthly_cost > 100 else "MEDIUM"
            
            recommendations.append(UpgradeRecommendation(
                category="Energy Efficiency",
                priority=priority,
                title="Optimize Energy Consumption",
                problem_description=f"System consuming ~{monthly_kwh:.0f} kWh/month (${estimated_monthly_cost:.0f}). " +
                                  f"Found {len(waste_indicators)} optimization opportunities.",
                impact=f"Potential 15-30% reduction in energy costs (${estimated_monthly_cost * 0.2:.0f}/month savings)",
                cost_range="$0-100 (scheduling optimization to LED upgrades)",
                roi_timeline="1-6 months",
                implementation_steps=[
                    "Run 'python energy_efficiency_audit.py' for detailed analysis",
                    "Optimize light schedules based on DLI requirements",
                    "Consider shared relays for compatible lights",
                    "Upgrade inefficient LED fixtures if >2 years old",
                    "Implement time-of-use scheduling if applicable"
                ],
                tools_needed=["energy_efficiency_audit.py", "power monitoring"],
                success_metrics=[
                    "Reduced monthly energy consumption",
                    "Lower electricity bills", 
                    "Maintained or improved plant health",
                    "Optimized light schedules"
                ]
            ))
        
        return recommendations
    
    def analyze_zone_organization(self, system_data: Dict) -> List[UpgradeRecommendation]:
        """Analyze zone layout and organization efficiency."""
        recommendations = []
        
        zones = system_data.get('zones', {})
        lights = system_data.get('lights', {})
        
        if not zones:
            return recommendations
        
        organization_issues = []
        
        # Check for zones with mixed plant types (potential splitting candidates)
        mixed_zones = []
        for zone_id, zone_config in zones.items():
            crop = zone_config.get('crop', {})
            plant_type = crop.get('type', 'unknown')
            
            # This is a simplified check - in real systems you'd need more data
            # about actual plant variety within zones
            description = zone_config.get('description', '').lower()
            if 'mixed' in description or 'various' in description:
                mixed_zones.append({
                    'zone_id': zone_id,
                    'description': zone_config.get('description', zone_id),
                    'plant_type': plant_type
                })
        
        # Check for very small zones that could be merged
        small_zones = []
        for zone_id, zone_config in zones.items():
            # Find lights serving this zone
            zone_lights = [light_id for light_id, light_config in lights.items() 
                          if light_config.get('zone_key') == zone_id]
            
            if len(zone_lights) == 1:
                light_power = lights.get(zone_lights[0], {}).get('power_watts', 50)
                if light_power < 75:  # Small light = small zone
                    small_zones.append({
                        'zone_id': zone_id,
                        'description': zone_config.get('description', zone_id),
                        'light_power': light_power
                    })
        
        if mixed_zones or len(small_zones) >= 3:
            recommendations.append(UpgradeRecommendation(
                category="Zone Organization",
                priority="MEDIUM",
                title="Optimize Zone Layout and Grouping",
                problem_description=f"Found {len(mixed_zones)} mixed-use zones and {len(small_zones)} " +
                                  "small zones that could be reorganized for better automation",
                impact="Improved automation effectiveness and easier plant management",
                cost_range="$0-50 (barriers, reorganization supplies)",
                roi_timeline="Immediate (operational efficiency)",
                implementation_steps=[
                    "Review current zone boundaries and plant groupings",
                    "Split mixed zones by plant type or growth stage",
                    "Merge compatible small zones for easier management", 
                    "Install physical barriers between different plant types",
                    "Update zone configurations in system"
                ],
                tools_needed=["Zone barriers", "labels", "measuring tools"],
                success_metrics=[
                    "Each zone contains similar plant types",
                    "Reduced need for manual interventions",
                    "More consistent automation behavior",
                    "Easier plant care management"
                ]
            ))
        
        return recommendations
    
    def analyze_system_reliability(self, system_data: Dict) -> List[UpgradeRecommendation]:
        """Analyze system reliability and error patterns."""
        recommendations = []
        
        errors = system_data.get('errors', {})
        todos = system_data.get('todos', {})
        
        # Check for recurring errors
        if isinstance(errors, list) and len(errors) > 5:
            recommendations.append(UpgradeRecommendation(
                category="System Reliability", 
                priority="MEDIUM",
                title="Address System Errors and Reliability Issues",
                problem_description=f"Found {len(errors)} recorded errors. High error frequency may indicate " +
                                  "hardware issues, connectivity problems, or configuration errors.",
                impact="Reduced system reliability and potential plant care disruptions",
                cost_range="$0-100 (depends on root cause)",
                roi_timeline="Immediate",
                implementation_steps=[
                    "Review error logs for patterns",
                    "Check all hardware connections",
                    "Verify sensor calibration",
                    "Update software if needed",
                    "Consider backup systems for critical functions"
                ],
                tools_needed=["get_errors() tool", "hardware diagnostics"],
                success_metrics=[
                    "Reduced error frequency",
                    "Improved system uptime",
                    "More consistent automation",
                    "Fewer manual interventions needed"
                ]
            ))
        
        # Check for incomplete todos (suggesting manual oversight needs)
        if isinstance(todos, list):
            incomplete_todos = [todo for todo in todos if todo.get('status') != 'completed']
            if len(incomplete_todos) > 10:
                recommendations.append(UpgradeRecommendation(
                    category="Automation Completeness",
                    priority="LOW",
                    title="Reduce Manual Task Load with Enhanced Automation",
                    problem_description=f"Found {len(incomplete_todos)} pending manual tasks. Consider " +
                                      "automating recurring maintenance and monitoring tasks.",
                    impact="Reduced manual workload and more consistent plant care",
                    cost_range="$25-100 (additional sensors, automation scripts)",
                    roi_timeline="2-8 weeks",
                    implementation_steps=[
                        "Review recurring manual tasks",
                        "Identify automation opportunities",
                        "Add sensors for automatic monitoring",
                        "Create scheduled maintenance scripts",
                        "Set up automated alerts and notifications"
                    ],
                    tools_needed=["Additional sensors", "automation scripts"],
                    success_metrics=[
                        "Reduced manual task frequency",
                        "More consistent plant care",
                        "Fewer missed maintenance items",
                        "Better tracking of plant health"
                    ]
                ))
        
        return recommendations
    
    def generate_comprehensive_report(self) -> Dict:
        """Generate complete system upgrade analysis."""
        print("🔍 Loading system configuration...")
        system_data = self.load_system_data()
        
        print("🔍 Analyzing relay configurations...")
        self.recommendations.extend(self.analyze_relay_conflicts(system_data))
        
        print("🔍 Analyzing light coverage...")
        self.recommendations.extend(self.analyze_light_coverage(system_data))
        
        print("🔍 Analyzing energy efficiency...")
        self.recommendations.extend(self.analyze_energy_efficiency(system_data))
        
        print("🔍 Analyzing zone organization...")
        self.recommendations.extend(self.analyze_zone_organization(system_data))
        
        print("🔍 Analyzing system reliability...")
        self.recommendations.extend(self.analyze_system_reliability(system_data))
        
        # Prioritize recommendations
        priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        self.recommendations.sort(key=lambda x: priority_order.get(x.priority, 4))
        
        # Calculate total potential savings
        total_monthly_savings = 0
        for rec in self.recommendations:
            if "$" in rec.impact and "/month" in rec.impact:
                try:
                    # Extract dollar amount from impact description
                    import re
                    amounts = re.findall(r'\$(\d+)', rec.impact)
                    if amounts:
                        total_monthly_savings += int(amounts[0])
                except:
                    pass
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_recommendations': len(self.recommendations),
            'high_priority': len([r for r in self.recommendations if r.priority == "HIGH"]),
            'medium_priority': len([r for r in self.recommendations if r.priority == "MEDIUM"]),
            'low_priority': len([r for r in self.recommendations if r.priority == "LOW"]),
            'estimated_monthly_savings': total_monthly_savings,
            'recommendations': [
                {
                    'category': rec.category,
                    'priority': rec.priority,
                    'title': rec.title,
                    'problem_description': rec.problem_description,
                    'impact': rec.impact,
                    'cost_range': rec.cost_range,
                    'roi_timeline': rec.roi_timeline,
                    'implementation_steps': rec.implementation_steps,
                    'tools_needed': rec.tools_needed,
                    'success_metrics': rec.success_metrics
                } for rec in self.recommendations
            ]
        }

def print_upgrade_report(report: Dict):
    """Print formatted upgrade analysis report."""
    print("\n🚀 SYSTEM UPGRADE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Analysis Date: {report['timestamp']}")
    print(f"Total Recommendations: {report['total_recommendations']}")
    print(f"Estimated Monthly Savings: ${report['estimated_monthly_savings']}")
    print()
    
    # Priority summary
    print("📊 PRIORITY BREAKDOWN:")
    print(f"   🔴 HIGH Priority: {report['high_priority']} issues")
    print(f"   🟡 MEDIUM Priority: {report['medium_priority']} improvements")
    print(f"   🟢 LOW Priority: {report['low_priority']} enhancements")
    print()
    
    if report['high_priority'] > 0:
        print("⚠️  IMMEDIATE ACTION REQUIRED for HIGH priority items!")
        print()
    
    # Detailed recommendations
    for i, rec in enumerate(report['recommendations'], 1):
        priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        print(f"{priority_emoji.get(rec['priority'], '⚪')} {i}. {rec['title']}")
        print(f"   Category: {rec['category']}")
        print(f"   Priority: {rec['priority']}")
        print(f"   Problem: {rec['problem_description']}")
        print(f"   Impact: {rec['impact']}")
        print(f"   Cost: {rec['cost_range']}")
        print(f"   ROI: {rec['roi_timeline']}")
        
        print("   🔧 Implementation Steps:")
        for step in rec['implementation_steps'][:3]:  # Show first 3 steps
            print(f"      • {step}")
        if len(rec['implementation_steps']) > 3:
            print(f"      • ... and {len(rec['implementation_steps']) - 3} more steps")
        
        print("   📈 Success Metrics:")
        for metric in rec['success_metrics'][:2]:  # Show first 2 metrics
            print(f"      • {metric}")
        
        print()

def main():
    """Main function to run system upgrade analysis."""
    try:
        analyzer = SystemUpgradeAnalyzer()
        report = analyzer.generate_comprehensive_report()
        
        print_upgrade_report(report)
        
        # Save detailed report
        report_file = Path("data") / "system_upgrade_analysis.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📄 Detailed report saved to: {report_file}")
        print()
        print("🔗 For more information, see: docs/SYSTEM_UPGRADE_SUGGESTIONS.md")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()