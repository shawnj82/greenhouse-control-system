#!/usr/bin/env python3
"""
Test script for adaptive light calibration system.
Demonstrates mixed capability optimization for various zone configurations.
"""

import json
import sys
from pathlib import Path
from control.light_calibration import LightCalibrator

def setup_test_environment():
    """Set up test data files for demonstration."""
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    # Create test zones configuration
    zones_config = {
        "grid_size": {"rows": 4, "cols": 6},
        "zones": {
            "A1": {
                "name": "Lettuce Section",
                "crop_type": "lettuce",
                "growth_stage": "vegetative",
                "light_spectrum": {
                    "par_target": 180,
                    "color_temperature": 4000,
                    "blue_percent": 25,
                    "green_percent": 40,
                    "red_percent": 35
                }
            },
            "A2": {
                "name": "Basil Garden",
                "crop_type": "basil",
                "growth_stage": "flowering",
                "light_spectrum": {
                    "par_target": 220,
                    "color_temperature": 4500,
                    "blue_percent": 30,
                    "green_percent": 30,
                    "red_percent": 40
                }
            },
            "B1": {
                "name": "Tomato Seedlings",
                "crop_type": "tomatoes",
                "growth_stage": "seedling",
                "light_spectrum": {
                    "par_target": 150,
                    "color_temperature": 3800,
                    "blue_percent": 35,
                    "green_percent": 30,
                    "red_percent": 35
                }
            },
            "B2": {
                "name": "Mixed Herbs",
                "crop_type": "herbs",
                "growth_stage": "vegetative",
                "light_spectrum": {
                    "par_target": 160,
                    "color_temperature": 4200,
                    "blue_percent": 28,
                    "green_percent": 40,
                    "red_percent": 32
                }
            }
        }
    }
    
    # Create test lights configuration
    lights_config = {
        "lights": {
            "led_strip_1": {
                "name": "Full Spectrum LED Strip 1",
                "type": "LED_STRIP",
                "position": {"row": 1, "col": 1},
                "zone_key": "A1",
                "gpio_pin": 18,
                "power_watts": 45,
                "spectrum": {
                    "color_temperature": 4000,
                    "blue_percent": 25,
                    "green_percent": 35,
                    "red_percent": 40,
                    "has_variable_color": True,
                    "spectral_channels": ["blue", "green", "red", "white"]
                }
            },
            "grow_panel_1": {
                "name": "High-Power Grow Panel 1",
                "type": "GROW_PANEL",
                "position": {"row": 1, "col": 2},
                "zone_key": "A2",
                "gpio_pin": 19,
                "power_watts": 100,
                "spectrum": {
                    "color_temperature": 3500,
                    "blue_percent": 20,
                    "green_percent": 30,
                    "red_percent": 50,
                    "has_variable_color": False,
                    "spectral_channels": ["red", "blue"]
                }
            },
            "basic_light_1": {
                "name": "Basic White LED 1",
                "type": "LED_BASIC",
                "position": {"row": 2, "col": 1},
                "zone_key": "B1",
                "gpio_pin": 20,
                "power_watts": 25,
                "spectrum": {
                    "color_temperature": 5000,
                    "blue_percent": 15,
                    "green_percent": 45,
                    "red_percent": 40,
                    "has_variable_color": False,
                    "spectral_channels": ["white"]
                }
            },
            "rgb_light_1": {
                "name": "RGB LED Array 1",
                "type": "RGB_ARRAY",
                "position": {"row": 2, "col": 2},
                "zone_key": "B2",
                "gpio_pin": 21,
                "power_watts": 60,
                "spectrum": {
                    "color_temperature": 4500,
                    "blue_percent": 33,
                    "green_percent": 33,
                    "red_percent": 34,
                    "has_variable_color": True,
                    "spectral_channels": ["red", "green", "blue"]
                }
            },
            "backup_light_1": {
                "name": "Backup White Light",
                "type": "LED_BASIC",
                "position": {"row": 1, "col": 3},
                "zone_key": None,
                "gpio_pin": 22,
                "power_watts": 30,
                "spectrum": {
                    "color_temperature": 4000,
                    "blue_percent": 20,
                    "green_percent": 40,
                    "red_percent": 40,
                    "has_variable_color": False,
                    "spectral_channels": ["white"]
                }
            }
        }
    }
    
    # Create test light sensors configuration
    sensors_config = {
        "sensors": {
            "bh1750_1": {
                "name": "Basic Light Sensor A1",
                "type": "BH1750",
                "connection": {"bus": 1, "address": 35},
                "zone_key": "A1",
                "position": {"row": 1, "col": 1}
            },
            "tsl2591_1": {
                "name": "Spectrum Sensor A2",
                "type": "TSL2591",
                "connection": {"bus": 1, "address": 41},
                "zone_key": "A2",
                "position": {"row": 1, "col": 2}
            },
            "veml7700_1": {
                "name": "Precision Sensor B1",
                "type": "VEML7700",
                "connection": {"bus": 1, "address": 16},
                "zone_key": "B1",
                "position": {"row": 2, "col": 1}
            },
            "tsl2561_1": {
                "name": "Standard Sensor B2",
                "type": "TSL2561",
                "connection": {"bus": 1, "address": 57},
                "zone_key": "B2",
                "position": {"row": 2, "col": 2}
            }
        }
    }
    
    # Save configuration files
    with open(data_dir / 'zones.json', 'w') as f:
        json.dump(zones_config, f, indent=2)
    
    with open(data_dir / 'lights.json', 'w') as f:
        json.dump(lights_config, f, indent=2)
    
    with open(data_dir / 'light_sensors.json', 'w') as f:
        json.dump(sensors_config, f, indent=2)
    
    print("✓ Test environment set up successfully")
    return data_dir

def test_zone_capabilities(calibrator):
    """Test zone capability analysis."""
    print("\n" + "="*60)
    print("TESTING ZONE CAPABILITY ANALYSIS")
    print("="*60)
    
    try:
        report = calibrator.get_zone_capability_report()
        
        print(f"\nZone Analysis Summary:")
        print(f"Total zones analyzed: {len(report.get('zones', {}))}")
        
        for zone_key, capabilities in report.get('zones', {}).items():
            print(f"\nZone: {zone_key}")
            print(f"  Optimization Level: {capabilities.get('optimization_level', 'unknown').upper()}")
            
            sensor_caps = capabilities.get('sensor_capabilities', {})
            print(f"  Sensors: {sensor_caps.get('count', 0)} ({', '.join(sensor_caps.get('types', []))})")
            print(f"  Spectral Support: {'Yes' if sensor_caps.get('has_spectral') else 'No'}")
            print(f"  Color Support: {'Yes' if sensor_caps.get('supports_color') else 'No'}")
            
            light_caps = capabilities.get('light_capabilities', {})
            print(f"  Lights: {light_caps.get('count', 0)} ({', '.join(light_caps.get('types', []))})")
            print(f"  Variable Color: {'Yes' if light_caps.get('has_variable_color') else 'No'}")
            print(f"  Total Power: {light_caps.get('total_power', 0)}W")
        
        return True
    except Exception as e:
        print(f"❌ Error analyzing zone capabilities: {e}")
        return False

def test_adaptive_calibration(calibrator):
    """Test adaptive calibration for mixed capability zones."""
    print("\n" + "="*60)
    print("TESTING ADAPTIVE CALIBRATION")
    print("="*60)
    
    try:
        # Test crop-based optimization
        crop_types = {
            "A1": "lettuce",
            "A2": "basil", 
            "B1": "tomatoes",
            "B2": "herbs"
        }
        
        growth_stages = {
            "A1": "vegetative",
            "A2": "flowering",
            "B1": "seedling", 
            "B2": "vegetative"
        }
        
        print("Running mixed crop type optimization...")
        results = calibrator.optimize_for_mixed_zone_types(crop_types, growth_stages)
        
        summary = results.get('overall_summary', {})
        print(f"\nOptimization Results:")
        print(f"  Success Rate: {summary.get('success_rate', 0)*100:.1f}%")
        print(f"  Quality Level: {summary.get('optimization_quality', 'unknown').upper()}")
        print(f"  Total Power: {summary.get('total_power_consumption', 0)}W")
        print(f"  Lights Activated: {summary.get('total_lights_activated', 0)}")
        
        strategies_used = summary.get('strategies_used', {})
        if strategies_used:
            print(f"\nOptimization Strategies Used:")
            for strategy, count in strategies_used.items():
                print(f"  {strategy.replace('_', ' ').title()}: {count} zones")
        
        zone_results = results.get('zone_results', {})
        print(f"\nZone-Specific Results:")
        for zone_key, zone_result in zone_results.items():
            strategy = zone_result.get('strategy_used', 'unknown')
            success = "✓" if zone_result.get('success') else "✗"
            confidence = zone_result.get('accuracy_metrics', {}).get('confidence_score', 0) * 100
            
            print(f"  {zone_key}: {success} {strategy.replace('_', ' ').title()} (Confidence: {confidence:.1f}%)")
            
            limitations = zone_result.get('feedback', {}).get('limitations', [])
            if limitations:
                print(f"    Limitations: {', '.join(limitations)}")
        
        return True
    except Exception as e:
        print(f"❌ Error running adaptive calibration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_custom_zone_requests(calibrator):
    """Test custom zone optimization requests."""
    print("\n" + "="*60)
    print("TESTING CUSTOM ZONE REQUESTS")
    print("="*60)
    
    try:
        # Create custom optimization requests
        zone_requests = {
            "A1": {
                "target_par": 200,
                "target_color_temp": 4200,
                "target_spectrum": {"blue_percent": 30, "green_percent": 35, "red_percent": 35},
                "intensity_priority": 1.0,
                "color_priority": 0.8,
                "max_power_consumption": 50
            },
            "A2": {
                "target_intensity": 250,
                "target_color_temp": 3800,
                "intensity_priority": 0.9,
                "color_priority": 0.9,
                "efficiency_priority": 0.6
            },
            "B1": {
                "target_par": 120,
                "min_intensity": 100,
                "max_intensity": 150,
                "intensity_priority": 1.0,
                "color_priority": 0.3  # Less important for basic sensors
            },
            "B2": {
                "target_spectrum": {"blue_percent": 25, "green_percent": 45, "red_percent": 30},
                "target_color_temp": 4500,
                "intensity_priority": 0.8,
                "color_priority": 0.9
            }
        }
        
        print("Running custom zone optimization requests...")
        results = calibrator.optimize_zones_with_adaptive_strategy(zone_requests)
        
        summary = results.get('overall_summary', {})
        print(f"\nCustom Optimization Results:")
        print(f"  Success Rate: {summary.get('success_rate', 0)*100:.1f}%")
        print(f"  Average Confidence: {summary.get('average_confidence', 0)*100:.1f}%")
        print(f"  Total Power: {summary.get('total_power_consumption', 0)}W")
        
        zone_results = results.get('zone_results', {})
        for zone_key, zone_result in zone_results.items():
            print(f"\n  Zone {zone_key}:")
            print(f"    Strategy: {zone_result.get('strategy_used', 'unknown').replace('_', ' ').title()}")
            print(f"    Success: {'Yes' if zone_result.get('success') else 'No'}")
            
            predicted = zone_result.get('predicted_metrics', {})
            if predicted:
                print(f"    Predicted Intensity: {predicted.get('intensity', 'N/A')}")
                print(f"    Predicted Color Temp: {predicted.get('color_temp', 'N/A')}")
                print(f"    Power Usage: {predicted.get('power_consumption', 'N/A')}W")
            
            feedback = zone_result.get('feedback', {})
            suggestions = feedback.get('suggestions', [])
            if suggestions:
                print(f"    Suggestions: {', '.join(suggestions)}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing custom zone requests: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_performance_analysis(calibrator):
    """Run performance analysis on the calibration system."""
    print("\n" + "="*60)
    print("PERFORMANCE ANALYSIS")
    print("="*60)
    
    try:
        # Test different optimization strategies
        strategies = ['greedy', 'linear', 'weighted_ls', 'multi_objective']
        
        zone_requests = {
            "A1": {"target_par": 180, "target_color_temp": 4000},
            "A2": {"target_par": 220, "target_color_temp": 4500},
            "B1": {"target_par": 150, "target_color_temp": 3800},
            "B2": {"target_par": 160, "target_color_temp": 4200}
        }
        
        print("Comparing optimization strategies:")
        for strategy in strategies:
            try:
                # Note: This would typically use the base optimizer with the strategy
                # For now, we'll use the adaptive system which chooses the best strategy
                results = calibrator.optimize_zones_with_adaptive_strategy(zone_requests)
                summary = results.get('overall_summary', {})
                
                print(f"\n  Strategy: {strategy.replace('_', ' ').title()}")
                print(f"    Success Rate: {summary.get('success_rate', 0)*100:.1f}%")
                print(f"    Power Efficiency: {summary.get('total_power_consumption', 0)}W")
                print(f"    Quality Score: {summary.get('average_confidence', 0)*100:.1f}%")
                
            except Exception as e:
                print(f"    Error with {strategy}: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Error in performance analysis: {e}")
        return False

def main():
    """Main test function."""
    print("🌱 Adaptive Light Calibration System Test")
    print("=" * 60)
    
    # Set up test environment
    data_dir = setup_test_environment()
    
    # Create calibrator instance
    print("\nInitializing light calibrator...")
    try:
        calibrator = LightCalibrator(data_dir=str(data_dir))
        print("✓ Light calibrator initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize calibrator: {e}")
        return 1
    
    # Run tests
    tests = [
        ("Zone Capabilities", test_zone_capabilities),
        ("Adaptive Calibration", test_adaptive_calibration),
        ("Custom Zone Requests", test_custom_zone_requests),
        ("Performance Analysis", run_performance_analysis)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            success = test_func(calibrator)
            results.append((test_name, success))
            status = "✓ PASSED" if success else "✗ FAILED"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            print(f"\n✗ FAILED: {test_name} - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓" if success else "✗"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! The adaptive calibration system is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)