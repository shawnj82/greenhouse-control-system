def estimate_ppfd(r, g, b, c, gain, integration_time_ms, scale_factor=1.0):
    if c == 0:
        return 0.0
    r_ratio = r / c
    g_ratio = g / c
    b_ratio = b / c
    weighted_sum = (0.45 * r_ratio + 0.35 * g_ratio + 0.20 * b_ratio)
    gain_factor = gain  # e.g., 1, 4, 16, 60
    int_time_factor = integration_time_ms / 100.0  # Normalize to 100 ms baseline
    ppfd_est = weighted_sum * (c / (gain_factor * int_time_factor)) * scale_factor
    return round(ppfd_est, 1)
def calculate_6bands_and_quality(sensor_type, raw_data):
    """
    Calculate 6 bands (UV-A, Blue, Green, Red, Far-Red, NIR) and assign quality flags.
    Returns: dict of {band: {"value": float, "quality": str}}
    """
    bands = ["uv_a", "blue", "green", "red", "far_red", "nir"]
    result = {band: {"value": None, "quality": "baseline"} for band in bands}
    # AS7341: direct mapping for most bands
    if sensor_type == "AS7341" and raw_data:
        # Map: uv_a~violet, blue~blue, green~green, red~red, far_red~nir_1, nir~nir_2
        mapping = {
            "uv_a": ("violet", "direct"),
            "blue": ("blue", "direct"),
            "green": ("green", "direct"),
            "red": ("red", "direct"),
            "far_red": ("nir_1", "direct"),
            "nir": ("nir_2", "direct"),
        }
        for band, (src, q) in mapping.items():
            if src in raw_data:
                result[band] = {"value": raw_data[src], "quality": q}
    # TCS34725: only RGB, interpolate/extrapolate
    elif sensor_type == "TCS34725" and raw_data:
        # Use blue for blue, green for green, red for red
        for band, src in zip(["blue", "green", "red"], ["blue_raw", "green_raw", "red_raw"]):
            if src in raw_data:
                result[band] = {"value": raw_data[src], "quality": "direct"}
        # UV-A, Far-Red, NIR: not measured, set to baseline
    # TSL2591: has full/ir channels, can estimate some bands
    elif sensor_type == "TSL2591" and raw_data:
        # If raw_data has 'full' and 'ir', use as proxies
        if "full" in raw_data and "ir" in raw_data:
            result["nir"] = {"value": raw_data["ir"], "quality": "direct"}
            result["red"] = {"value": raw_data["full"] - raw_data["ir"], "quality": "calculated"}
        # Others: baseline
    # VEML7700, TSL2561, BH1750: only lux, all bands are baseline
    return result
"""
Shared sensor constants and functions for both the Flask app and the scheduler service.
"""
import os
import json
import time
from sensors.dht22 import DHT22
from sensors.bh1750 import BH1750
from sensors.tsl2561 import TSL2561
from sensors.veml7700 import VEML7700
from sensors.tsl2591 import TSL2591
from sensors.soil_moisture import SoilMoisture
from sensors.spectral_sensors import TCS34725Color
from control.light_calibration import LightCalibrator

# Data directory for configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

LIGHT_SENSORS_FILE = os.path.join(DATA_DIR, "light_sensors.json")

# Configuration settings (defaults)
def load_app_config():
    config_path = os.path.join(DATA_DIR, "light_control_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback defaults
    return {
        "sensor_cache_ttl": 5,
        "frontend_update_interval": 10
    }

_app_config = load_app_config()

def read_light_sensor(cfg, sensor_id=None):
    """Read a light sensor based on its config dict."""
    import sys, os
    if os.getenv("VERBOSE_SCHEDULER_LOGS"):
        print(f"[read_light_sensor][DEBUG] Called with cfg={cfg}, sensor_id={sensor_id}")
    sensor_type = (cfg.get("type") or "").upper()
    connection = cfg.get("connection", {})
    bus = connection.get("bus", 1)
    addr = connection.get("address")
    # Persistent cache for sensor instances
    if not hasattr(read_light_sensor, "_sensor_cache"):
        read_light_sensor._sensor_cache = {}
    cache = read_light_sensor._sensor_cache
    key = (sensor_type, bus, addr)
    try:
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print(f"[read_light_sensor][DEBUG] sensor_type={sensor_type}, bus={bus}, addr={addr}")
        sensor = None
        if sensor_type == "BH1750":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating BH1750")
                cache[key] = BH1750(bus=bus)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_lux() on BH1750")
            lux = sensor.read_lux()
            if lux is not None and lux < 0:
                try:
                    print(f"[Scheduler][WARN] Negative lux from BH1750 ({lux}); clamping to 0.0")
                except Exception:
                    pass
                lux = 0.0
            bands = calculate_6bands_and_quality(sensor_type, None)
            result = {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": lux, "quality": "direct" if lux is not None else "baseline"},
                    "par": {"value": None, "quality": "baseline"},
                    "color_temp": {"value": None, "quality": "baseline"},
                    "PPFD": {"value": None, "quality": "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Result: {result}")
            return result
        elif sensor_type == "TSL2561":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating TSL2561")
                cache[key] = TSL2561(bus=bus, addr=addr)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_lux() on TSL2561")
            lux = sensor.read_lux()
            if lux is not None and lux < 0:
                try:
                    print(f"[Scheduler][WARN] Negative lux from TSL2561 ({lux}); clamping to 0.0")
                except Exception:
                    pass
                lux = 0.0
            bands = calculate_6bands_and_quality(sensor_type, None)
            result = {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": lux, "quality": "direct" if lux is not None else "baseline"},
                    "par": {"value": None, "quality": "baseline"},
                    "color_temp": {"value": None, "quality": "baseline"},
                    "PPFD": {"value": None, "quality": "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Result: {result}")
            return result
        elif sensor_type == "TSL2591":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating TSL2591")
                cache[key] = TSL2591(bus=bus, addr=addr)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_lux() on TSL2591")
            # If TSL2591 exposes raw channels, use them; else just lux
            lux = sensor.read_lux()
            if lux is not None and lux < 0:
                try:
                    print(f"[Scheduler][WARN] Negative lux from TSL2591 ({lux}); clamping to 0.0")
                except Exception:
                    pass
                lux = 0.0
            raw_data = getattr(sensor, "last_raw", None) if hasattr(sensor, "last_raw") else None
            bands = calculate_6bands_and_quality(sensor_type, raw_data)
            result = {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": lux, "quality": "direct" if lux is not None else "baseline"},
                    "par": {"value": None, "quality": "baseline"},
                    "color_temp": {"value": None, "quality": "baseline"},
                    "PPFD": {"value": None, "quality": "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Result: {result}")
            return result
        elif sensor_type == "VEML7700":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating VEML7700")
                cache[key] = VEML7700(bus=bus)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_lux() on VEML7700")
            lux = sensor.read_lux()
            if lux is not None and lux < 0:
                try:
                    print(f"[Scheduler][WARN] Negative lux from VEML7700 ({lux}); clamping to 0.0")
                except Exception:
                    pass
                lux = 0.0
            bands = calculate_6bands_and_quality(sensor_type, None)
            result = {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": lux, "quality": "direct" if lux is not None else "baseline"},
                    "par": {"value": None, "quality": "baseline"},
                    "color_temp": {"value": None, "quality": "baseline"},
                    "PPFD": {"value": None, "quality": "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Result: {result}")
            return result
        elif sensor_type == "TCS34725":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating TCS34725Color")
                cache[key] = TCS34725Color(bus=bus, addr=addr)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_color() on TCS34725Color")
            color = sensor.read_color()
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] color result: {color}")
            bands = calculate_6bands_and_quality(sensor_type, color)
            # Calculate PPFD from RGB channels, scaled by lux (PAR is not reported)
            ppfd = None
            if color:
                r = color.get("red_raw", 0)
                g = color.get("green_raw", 0)
                b = color.get("blue_raw", 0)
                c = color.get("clear_raw", 0)
                gain = color.get("gain", 1)
                integration_time = color.get("integration_time_ms", 100)
                # You may want to tune scale_factor for calibration
                scale_factor = 0.05
                ppfd = estimate_ppfd(r, g, b, c, gain, integration_time, scale_factor)
                # Clamp negative lux if present
                if "lux" in color and color["lux"] is not None and color["lux"] < 0:
                    try:
                        print(f"[Scheduler][WARN] Negative lux from TCS34725 ({color['lux']}); clamping to 0.0")
                    except Exception:
                        pass
                    color["lux"] = 0.0
            result = {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": color.get("lux"), "quality": "direct" if color and color.get("lux") is not None else "baseline"},
                    "color_temp": {"value": color.get("color_temperature_k"), "quality": "direct" if color and color.get("color_temperature_k") is not None else "baseline"},
                    "PPFD": {"value": ppfd, "quality": "calculated" if ppfd is not None else "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Result: {result}")
            return result
        else:
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Unknown sensor type: {sensor_type}")
            bands = calculate_6bands_and_quality(sensor_type, None)
            return {
                "bands": bands,
                "light_metrics": {
                    "lux": {"value": None, "quality": "baseline"},
                    "par": {"value": None, "quality": "baseline"},
                    "color_temp": {"value": None, "quality": "baseline"},
                    "PPFD": {"value": None, "quality": "baseline"}
                },
                "timestamp": time.time(),
                "error": None
            }
    except Exception as e:
        print(f"[read_light_sensor][ERROR] Error reading {sensor_type}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        bands = calculate_6bands_and_quality(sensor_type, None)
        return {
            "bands": bands,
            "light_metrics": {
                "lux": {"value": None, "quality": "baseline"},
                "par": {"value": None, "quality": "baseline"},
                "color_temp": {"value": None, "quality": "baseline"},
                "PPFD": {"value": None, "quality": "baseline"}
            },
            "timestamp": time.time(),
            "error": str(e)
        }
