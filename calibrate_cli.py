#!/usr/bin/env python3
"""Command line interface for light calibration system.

This script provides a simple command-line interface to run calibration
and optimization operations without using the web interface.
"""
import argparse
import json
import sys
from pathlib import Path

from control.light_calibration import LightCalibrator
from control.light_optimizer import LightOptimizer


def main():
    parser = argparse.ArgumentParser(description='Light Calibration CLI')
    parser.add_argument('--data-dir', default='data', help='Data directory path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Baseline measurement
    baseline_parser = subparsers.add_parser('baseline', help='Measure baseline light levels')
    baseline_parser.add_argument('--readings', type=int, default=5, help='Number of readings to average')
    
    # Individual light calibration
    calibrate_parser = subparsers.add_parser('calibrate', help='Calibrate specific light')
    calibrate_parser.add_argument('light_id', help='Light ID to calibrate')
    calibrate_parser.add_argument('--readings', type=int, default=5, help='Number of readings to average')
    calibrate_parser.add_argument('--comprehensive', action='store_true', help='Use spectral (TCS34725/AS7341) comprehensive calibration')
    
    # Full calibration
    full_parser = subparsers.add_parser('full', help='Run full calibration of all lights')
    full_parser.add_argument('--comprehensive', action='store_true', help='Include spectrum analysis')
    
    # Spectrum analysis
    spectrum_parser = subparsers.add_parser('spectrum', help='Spectrum analysis operations')
    spectrum_subparsers = spectrum_parser.add_subparsers(dest='spectrum_action', help='Spectrum commands')
    
    spectrum_subparsers.add_parser('report', help='Generate spectrum analysis report')
    spectrum_subparsers.add_parser('update', help='Update lights.json with measured spectrum')
    
    # Optimization
    optimize_parser = subparsers.add_parser('optimize', help='Optimize lights for zones')
    optimize_parser.add_argument('--method', choices=['greedy', 'linear', 'weighted_ls', 'multi_objective'], 
                                default='multi_objective', help='Optimization method')
    optimize_parser.add_argument('--apply', action='store_true', help='Apply optimization results')
    
    # Quality analysis
    quality_parser = subparsers.add_parser('quality', help='Analyze calibration quality')
    
    # Control commands
    control_parser = subparsers.add_parser('control', help='Control lights')
    control_parser.add_argument('action', choices=['all-off', 'light-on', 'light-off'])
    control_parser.add_argument('--light-id', help='Light ID for light-on/light-off actions')
    
    # Status
    status_parser = subparsers.add_parser('status', help='Show system status')

    # Manual single-light calibration (prompts user to toggle light)
    manual_parser = subparsers.add_parser('manual', help='Manual single-light calibration with prompts')
    manual_parser.add_argument('light_id', help='Light ID to calibrate')
    manual_parser.add_argument('--readings', type=int, default=5, help='Number of readings to average')
    manual_parser.add_argument('--delay', type=float, default=2.0, help='Delay between readings (seconds)')
    manual_parser.add_argument('--no-relay', action='store_true', help='Do not attempt to toggle relay (use when running off-Pi)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        calibrator = LightCalibrator(data_dir=args.data_dir)
        
        if args.command == 'baseline':
            print("Measuring baseline light levels...")
            baseline = calibrator.measure_baseline(num_readings=args.readings)
            print(f"Baseline measurements: {json.dumps(baseline, indent=2)}")
            
        elif args.command == 'calibrate':
            if args.comprehensive:
                print(f"Comprehensive calibration for light: {args.light_id}")
                baseline = calibrator.measure_baseline_comprehensive(num_readings=args.readings)
                result = calibrator.calibrate_light_comprehensive(args.light_id, baseline, num_readings=args.readings)
                
                # Save single-light comprehensive results to calibration data
                calibrator.calibration_data = {
                    'timestamp': result.get('timestamp', __import__('datetime').datetime.now().isoformat()),
                    'calibration_type': 'comprehensive_single_light',
                    'baseline': baseline.get('basic_sensors', {}),
                    'comprehensive_baseline': baseline,
                    'light_effects': {args.light_id: result.get('basic_effect', {})},
                    'spectrum_profiles': {args.light_id: {
                        'spectrum_analysis': result.get('spectrum_analysis', {}),
                        'light_data': result.get('light_data', {})
                    }},
                    'sensor_zones': calibrator.sensor_reader.get_sensor_zones()
                }
                calibrator._save_calibration_data()
                print(f"Comprehensive calibration data saved to {calibrator.data_dir / 'light_calibration.json'}")
                
                # Pretty print key parts
                basic_effect = result.get('basic_effect', {})
                print("Basic effect (if any):")
                print(json.dumps(basic_effect, indent=2))
                spectrum = result.get('spectrum_analysis', {})
                print("Spectrum analysis summary:")
                sig = spectrum.get('spectral_signature', {})
                brief = {
                    sid: {
                        'intensity_change': round(v.get('intensity_change', 0), 3),
                        'color_shift': v.get('color_shift')
                    } for sid, v in sig.items()
                }
                print(json.dumps(brief, indent=2))
            else:
                print(f"Calibrating light: {args.light_id}")
                baseline = calibrator.measure_baseline()
                effect = calibrator.calibrate_light(args.light_id, baseline, num_readings=args.readings)
                print(f"Light effect: {json.dumps(effect, indent=2)}")
            
        elif args.command == 'full':
            if args.comprehensive:
                print("Running comprehensive calibration with spectrum analysis...")
                calibration_data = calibrator.run_comprehensive_calibration()
                print("Comprehensive calibration completed successfully!")
                print(f"Calibrated {len(calibration_data.get('light_effects', {}))} lights with spectrum analysis")
            else:
                print("Running full calibration...")
                calibration_data = calibrator.run_full_calibration()
                print("Calibration completed successfully!")
                print(f"Calibrated {len(calibration_data.get('light_effects', {}))} lights")
            print(f"Using {len(calibration_data.get('baseline', {}))} sensors")
            
        elif args.command == 'optimize':
            print(f"Optimizing lights using {args.method} method...")
            zones_file = Path(args.data_dir) / 'zones.json'
            if not zones_file.exists():
                print("Error: zones.json not found")
                return 1
                
            with open(zones_file) as f:
                zones_data = json.load(f)
            
            optimal_lights = calibrator.optimize_for_zones(
                zones_data.get('zones', {}), 
                method=args.method
            )
            
            print("Optimization results:")
            for light_id, should_be_on in optimal_lights.items():
                status = "ON" if should_be_on else "OFF"
                print(f"  {light_id}: {status}")
            
            if args.apply:
                print("Applying optimization...")
                for light_id, should_be_on in optimal_lights.items():
                    if should_be_on:
                        calibrator.light_controller.turn_on_light(light_id)
                    else:
                        calibrator.light_controller.turn_off_light(light_id)
                print("Optimization applied!")
                
        elif args.command == 'quality':
            if not calibrator.calibration_data:
                print("No calibration data available. Run calibration first.")
                return 1
                
            optimizer = LightOptimizer(calibrator.calibration_data)
            quality = optimizer.analyze_calibration_quality()
            
            print("Calibration Quality Analysis:")
            print(f"  Sensors: {quality.get('num_sensors', 0)}")
            print(f"  Lights: {quality.get('num_lights', 0)}")
            print(f"  Responsive sensors: {quality.get('responsive_sensors', 0)}")
            print(f"  Effective lights: {quality.get('effective_lights', 0)}")
            print(f"  Overall quality: {quality.get('overall_quality', 0):.1%}")
            
        elif args.command == 'control':
            if args.action == 'all-off':
                print("Turning off all lights...")
                calibrator.light_controller.turn_off_all_lights()
                print("All lights turned off")
                
            elif args.action == 'light-on':
                if not args.light_id:
                    print("Error: --light-id required for light-on action")
                    return 1
                print(f"Turning on light: {args.light_id}")
                success = calibrator.light_controller.turn_on_light(args.light_id)
                if success:
                    print(f"Light {args.light_id} turned on")
                else:
                    print(f"Failed to turn on light {args.light_id}")
                    
            elif args.action == 'light-off':
                if not args.light_id:
                    print("Error: --light-id required for light-off action")
                    return 1
                print(f"Turning off light: {args.light_id}")
                success = calibrator.light_controller.turn_off_light(args.light_id)
                if success:
                    print(f"Light {args.light_id} turned off")
                else:
                    print(f"Failed to turn off light {args.light_id}")
                    
        elif args.command == 'spectrum':
            if args.spectrum_action == 'report':
                print("Generating spectrum analysis report...")
                report = calibrator.generate_spectrum_report()
                
                if 'error' in report:
                    print(f"Error: {report['error']}")
                    return 1
                
                print(f"\nSpectrum Analysis Report")
                print(f"Calibration: {report.get('calibration_timestamp', 'Unknown')}")
                print(f"\nLights Analyzed:")
                
                for light_id, analysis in report.get('lights_analyzed', {}).items():
                    if 'error' in analysis:
                        print(f"  {light_id}: Error - {analysis['error']}")
                        continue
                    
                    light_name = analysis.get('light_name', light_id)
                    print(f"  {light_name}:")
                    
                    color_analysis = analysis.get('color_analysis', {})
                    if color_analysis:
                        dominant = color_analysis.get('dominant_color', 'Unknown')
                        strength = color_analysis.get('dominant_strength', 0)
                        print(f"    Dominant color: {dominant} (strength: {strength:.1f})")
                    
                    par_eff = analysis.get('par_effectiveness', {})
                    if par_eff:
                        rating = par_eff.get('effectiveness_rating', 'unknown')
                        avg_par = par_eff.get('average_par_increase', 0)
                        print(f"    PAR effectiveness: {rating} (avg increase: {avg_par:.1f})")
                
                recommendations = report.get('recommendations', [])
                if recommendations:
                    print(f"\nRecommendations:")
                    for rec in recommendations:
                        print(f"  [{rec['type']}] {rec['message']}")
            
            elif args.spectrum_action == 'update':
                print("Updating lights.json with measured spectrum data...")
                updated = calibrator.update_lights_with_measured_spectrum()
                
                updated_count = sum(1 for success in updated.values() if success)
                total_count = len(updated)
                
                print(f"Updated {updated_count}/{total_count} lights with measured spectrum data")
                
                for light_id, success in updated.items():
                    status = "✓" if success else "✗"
                    print(f"  {status} {light_id}")
                    
        elif args.command == 'status':
            print("System Status:")
            print(f"  Data directory: {args.data_dir}")
            print(f"  Configured lights: {len(calibrator.lights_config)}")
            print(f"  Configured sensors: {len(calibrator.sensors_config)}")
            
            if calibrator.calibration_data:
                timestamp = calibrator.calibration_data.get('timestamp', 'Unknown')
                print(f"  Last calibration: {timestamp}")
            else:
                print("  Last calibration: Never")
        
        elif args.command == 'manual':
            print("Manual single-light calibration (comprehensive)")
            print("This will: 1) read baseline with light OFF, 2) read with light ON, 3) compute deltas.")
            input("Ensure the light is OFF, then press Enter to start baseline...")

            baseline = calibrator.measure_baseline_comprehensive(num_readings=args.readings, delay=args.delay)

            if not args.no_relay:
                print(f"Attempting to turn ON light via relay: {args.light_id}")
                calibrator.light_controller.turn_on_light(args.light_id)
            else:
                input("Now turn ON the light manually, then press Enter to continue...")

            import time as _t
            _t.sleep(3)

            # Collect comprehensive ON readings
            on_readings = []
            for i in range(args.readings):
                basic = calibrator.sensor_reader.read_all_sensors()
                spectral = calibrator.spectral_reader.read_comprehensive_data()
                on_readings.append({'basic': basic, 'spectral': spectral, 'timestamp': _t.time()})
                if i < args.readings - 1:
                    _t.sleep(args.delay)

            # Process
            light_on_data = calibrator._process_comprehensive_readings(on_readings)

            # Analyze spectrum
            spectrum_analysis = calibrator.spectral_reader.analyze_light_spectrum(
                args.light_id,
                baseline.get('spectral_sensors', {}),
                light_on_data.get('spectral_sensors', {})
            )

            # Compute basic effect (if any basic sensors present)
            basic_effect = {}
            base_basic = baseline.get('basic_sensors', {})
            on_basic = light_on_data.get('basic_sensors', {})
            for sid in base_basic.keys():
                if sid in on_basic:
                    basic_effect[sid] = on_basic[sid] - base_basic.get(sid, 0)

            # Build result and write a small file
            result = {
                'timestamp': __import__('datetime').datetime.now().isoformat(),
                'mode': 'manual_comprehensive_single',
                'light_id': args.light_id,
                'baseline': baseline,
                'light_on': light_on_data,
                'basic_effect': basic_effect,
                'spectrum_analysis': spectrum_analysis
            }

            out_path = Path(args.data_dir) / 'single_manual_calibration.json'
            with open(out_path, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"Manual calibration written to: {out_path}")
            # Brief summary
            sig = spectrum_analysis.get('spectral_signature', {})
            for sid, v in sig.items():
                print(f"  Sensor {sid}: Δlux≈{v.get('intensity_change'):.3f}, ΔRGB%={v.get('color_shift')}")
                
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        try:
            calibrator.cleanup()
        except:
            pass


if __name__ == '__main__':
    exit(main())