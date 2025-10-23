#!/usr/bin/env python3
"""
Analyze and print spectral histograms for each configured light sensor and the combined fused
result at a target zone (defaults to the AS7262 zone if present).

Outputs lux_per_nm densities per 20nm bin, with small summaries.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple

from control.spectral_fusion import SpectralDataFusion
from control.fusion_utils.fusion_calculator import calculate_fusion_for_positions
from background_scheduler import SensorScheduler

DATA_DIR = Path('data')


def load_configs() -> Tuple[Dict, Dict]:
    sensors_cfg = {}
    readings = {}
    cfg_path = DATA_DIR / 'light_sensors.json'
    if cfg_path.exists():
        with open(cfg_path, 'r') as f:
            sensors_cfg = json.load(f).get('sensors', {})
    readings_path = DATA_DIR / 'sensor_readings.json'
    if readings_path.exists():
        with open(readings_path, 'r') as f:
            readings = json.load(f).get('readings', {})
    return sensors_cfg, readings


def build_sensor_data(sensors_cfg: Dict, readings: Dict) -> Tuple[List[Dict], List[Tuple[float, float]], List[str]]:
    sensor_data_list = []
    positions = []
    labels = []
    for sensor_id, config in sensors_cfg.items():
        reading = readings.get(sensor_id, {})
        sensor_type = config.get("type")
        if not sensor_type:
            continue
        data = {"sensor_type": sensor_type}
        if sensor_type == "TCS34725":
            raw_color_data = reading.get("raw_color_data")
            if not raw_color_data:
                raw_color_data = {k: reading.get(k) for k in ["red_raw","green_raw","blue_raw","clear_raw","lux","color_temperature_k"] if k in reading}
            data["raw_color_data"] = raw_color_data
            lux_cal = config.get("lux_calibration") or config.get("calibration_factor")
            if lux_cal is not None:
                try:
                    data["lux_calibration"] = float(lux_cal)
                except Exception:
                    pass
        elif sensor_type == "TSL2591":
            raw_spectrum = reading.get("raw_spectrum_data", {})
            data["raw_spectrum_data"] = raw_spectrum
            lux_cal = config.get("lux_calibration") or config.get("calibration_factor")
            if lux_cal is not None:
                try:
                    data["lux_calibration"] = float(lux_cal)
                except Exception:
                    pass
        elif sensor_type == "AS7262":
            raw_spectrum = reading.get("raw_spectrum_data", {})
            data["raw_spectrum_data"] = raw_spectrum
            est = reading.get("estimated_lux")
            if isinstance(est, (int, float)):
                data["estimated_lux"] = float(est)
        elif sensor_type == "BH1750":
            data["raw_lux_data"] = reading.get("raw_lux_data", {})
        else:
            # Skip unsupported
            continue
        # Position
        if "position" in config:
            pos = tuple(config["position"])  # type: ignore
        elif "zone_key" in config:
            try:
                row, col = map(int, str(config["zone_key"]).split("-"))
                pos = (row, col)
            except Exception:
                pos = (0.0, 0.0)
        else:
            pos = (0.0, 0.0)
        labels.append(f"{sensor_type}:{sensor_id}")
        sensor_data_list.append(data)
        positions.append((float(pos[0]), float(pos[1])))
    return sensor_data_list, positions, labels


def make_histogram_for_sensor(sensor_data: Dict, target_pos: Tuple[float, float], sensor_pos: Tuple[float, float], apply_spatial_weight: float = 1.0) -> Dict:
    """Create a histogram (wavelength centers + intensities) for a single sensor.
    Optionally applies a spatial weight (e.g., normalized weight for the target location).
    """
    spectrum_bins = SpectralDataFusion.create_spectrum_bins()
    contrib = SpectralDataFusion.map_sensor_to_bins(sensor_data.get('sensor_type','UNKNOWN'), sensor_data, spectrum_bins)
    intensities = [contrib.get(i, 0.0) * apply_spatial_weight for i in range(len(spectrum_bins))]
    # Convert to histogram-like output similar to fusion_calculator
    centers = [ (lo+hi)/2.0 for (lo,hi) in spectrum_bins ]
    return {
        'wavelengths': centers,
        'intensities': intensities,
        'bin_width': 20,
        'units': 'lux_per_nm'
    }


def photopic_lux_from_hist(hist: Dict) -> float:
    sched = SensorScheduler()
    # Recreate bins from centers
    centers = hist['wavelengths']
    bins = [(c-10.0, c+10.0) for c in centers]
    return float(sched._estimate_lux_from_spectrum(bins, hist['intensities']))


def main():
    sensors_cfg, readings = load_configs()
    sensor_data_list, positions, labels = build_sensor_data(sensors_cfg, readings)
    if not sensor_data_list:
        print("No sensors found.")
        return
    # Pick target zone: prefer AS7262's zone if present
    target_pos = (0.0, 0.0)
    for sid, cfg in sensors_cfg.items():
        if cfg.get('type') == 'AS7262' and 'zone_key' in cfg:
            try:
                r,c = map(int, str(cfg['zone_key']).split('-'))
                target_pos = (float(r), float(c))
                break
            except Exception:
                pass
    print(f"Target position for histograms: {target_pos}")

    # Compute spatial weights among all sensors at target_pos
    spatial_weights = SpectralDataFusion.calculate_light_intensity_weights(sensor_data_list, positions, target_pos)

    # Per-sensor histograms (weighted by spatial weights to show contribution share)
    per_sensor = []
    for data, pos, label, w in zip(sensor_data_list, positions, labels, spatial_weights):
        hist = make_histogram_for_sensor(data, target_pos, pos, apply_spatial_weight=w)
        lux = photopic_lux_from_hist(hist)
        # Summarize first few non-zero bins
        nz = [(i, int(hist['wavelengths'][i]), hist['intensities'][i]) for i in range(len(hist['intensities'])) if hist['intensities'][i] > 0]
        nz_head = [(i, wl, round(val,3)) for i, wl, val in nz[:10]]
        print(f"\n--- {label} (weight={w:.3f}) ---")
        print("nonzero bins:", len(nz))
        print("first 10 nz bins (idx, nm, lux/nm):", nz_head)
        print("photopic_lux (estimated):", lux)
        per_sensor.append({'label': label, 'hist': hist, 'lux': lux, 'weight': w})

    # Combined fused histogram using fusion_calculator
    fused = calculate_fusion_for_positions(sensor_data_list, positions, [target_pos])[0]
    comb_hist = fused['histogram']
    comb_lux = photopic_lux_from_hist(comb_hist)
    nz = [(i, int(comb_hist['wavelengths'][i]), comb_hist['intensities'][i]) for i in range(len(comb_hist['intensities'])) if comb_hist['intensities'][i] > 0]
    nz_head = [(i, wl, round(val,3)) for i, wl, val in nz[:10]]
    print("\n=== Combined fused ===")
    print("nonzero bins:", len(nz))
    print("first 10 nz bins (idx, nm, lux/nm):", nz_head)
    print("photopic_lux (estimated):", comb_lux)

if __name__ == '__main__':
    main()
