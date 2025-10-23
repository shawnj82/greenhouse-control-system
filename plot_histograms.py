#!/usr/bin/env python3
"""
Plot per-sensor and combined spectral histograms (lux per nm) at a target zone.
Saves the result as PNGs under the plots/ directory.
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')  # headless
import matplotlib.pyplot as plt

from control.spectral_fusion import SpectralDataFusion
from control.fusion_utils.fusion_calculator import calculate_fusion_for_positions
from background_scheduler import SensorScheduler

DATA_DIR = Path('data')
PLOTS_DIR = Path('plots')
PLOTS_DIR.mkdir(exist_ok=True)


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
            continue
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


def photopic_lux_from_hist(wavelengths: List[float], intensities: List[float]) -> float:
    sched = SensorScheduler()
    bins = [(c-10.0, c+10.0) for c in wavelengths]
    return float(sched._estimate_lux_from_spectrum(bins, intensities))


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
    # Spatial weights
    spatial_weights = SpectralDataFusion.calculate_light_intensity_weights(sensor_data_list, positions, target_pos)
    # Per-sensor hist data
    per_hists = []
    for data, w, label in zip(sensor_data_list, spatial_weights, labels):
        bins = SpectralDataFusion.create_spectrum_bins()
        contrib = SpectralDataFusion.map_sensor_to_bins(data.get('sensor_type','UNKNOWN'), data, bins)
        centers = [ (lo+hi)/2.0 for (lo,hi) in bins ]
        intensities = [contrib.get(i, 0.0) * w for i in range(len(bins))]
        lux = photopic_lux_from_hist(centers, intensities)
        per_hists.append({
            'label': label,
            'wavelengths': centers,
            'intensities': intensities,
            'lux': lux,
            'weight': w
        })
    # Combined fused
    fused = calculate_fusion_for_positions(sensor_data_list, positions, [target_pos])[0]
    comb = fused['histogram']
    comb_lux = photopic_lux_from_hist(comb['wavelengths'], comb['intensities'])

    # Plot
    n = len(per_hists)
    cols = 2
    rows = (n + 1 + cols - 1)//cols  # +1 for combined
    fig, axes = plt.subplots(rows, cols, figsize=(12, 4*rows), squeeze=False)

    def plot_hist(ax, label, wavelengths, intensities, lux):
        ax.bar(wavelengths, intensities, width=20, align='center', color='#4a90e2')
        ax.set_title(f"{label}\nPhotopic lux≈{lux:.1f}")
        ax.set_xlabel('Wavelength (nm)')
        ax.set_ylabel('Intensity (lux/nm)')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(280, 850)

    # Fill per-sensor
    idx = 0
    for ph in per_hists:
        r = idx // cols
        c = idx % cols
        plot_hist(axes[r][c], f"{ph['label']} (w={ph['weight']:.3f})", ph['wavelengths'], ph['intensities'], ph['lux'])
        idx += 1

    # Combined
    r = idx // cols
    c = idx % cols
    plot_hist(axes[r][c], "Combined fused", comb['wavelengths'], comb['intensities'], comb_lux)
    idx += 1

    # Hide any unused subplots
    total_subplots = rows*cols
    while idx < total_subplots:
        r = idx // cols
        c = idx % cols
        axes[r][c].axis('off')
        idx += 1

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = PLOTS_DIR / f"histograms_{int(target_pos[0])}-{int(target_pos[1])}_{ts}.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")

if __name__ == '__main__':
    main()
