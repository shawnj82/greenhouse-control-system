# PPFD estimation removed - returning raw driver data without processing
# Raw sensor data functions - no band processing needed since returning driver data directly
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
from sensors.spectral_sensors import TCS34725Color, SpectralSensorReader
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
    mux_addr = connection.get("mux_address")
    mux_channel = connection.get("mux_channel")
    # Persistent cache for sensor instances
    if not hasattr(read_light_sensor, "_sensor_cache"):
        read_light_sensor._sensor_cache = {}
    cache = read_light_sensor._sensor_cache
    key = (sensor_type, bus, addr)
    try:
        # If mux is configured, select the channel before reading
        if mux_addr is not None and mux_channel is not None:
            from sensors.pca9548a import PCA9548A
            mux = PCA9548A(bus=bus, address=mux_addr)
            mux.select_channel(mux_channel)
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
            
            result = {
                "raw_lux_data": {"lux": lux},  # Raw lux data from BH1750
                "sensor_type": "BH1750",
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] BH1750 Raw Result: {result}")
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
            
            result = {
                "raw_lux_data": {"lux": lux},  # Raw lux data from TSL2561
                "sensor_type": "TSL2561",
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] TSL2561 Raw Result: {result}")
            return result
        elif sensor_type == "TSL2591":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating TSL2591")
                cache[key] = TSL2591(bus=bus, addr=addr, mux_address=mux_addr, mux_channel=mux_channel)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_full_spectrum() on TSL2591")
            
            # Get full spectrum data from TSL2591 if available
            if hasattr(sensor, 'read_full_spectrum'):
                full_data = sensor.read_full_spectrum()
                if full_data and full_data.get("lux") is not None and full_data["lux"] < 0:
                    try:
                        print(f"[Scheduler][WARN] Negative lux from TSL2591 ({full_data['lux']}); clamping to 0.0")
                    except Exception:
                        pass
                    full_data["lux"] = 0.0
                result = {
                    "raw_spectrum_data": full_data or {},  # Full spectrum data (lux, IR, visible, full)
                    "sensor_type": "TSL2591",
                    "timestamp": time.time(),
                    "error": None
                }
            else:
                # Fallback to just lux
                lux = sensor.read_lux()
                if lux is not None and lux < 0:
                    try:
                        print(f"[Scheduler][WARN] Negative lux from TSL2591 ({lux}); clamping to 0.0")
                    except Exception:
                        pass
                    lux = 0.0
                result = {
                    "raw_lux_data": {"lux": lux},  # Just lux data
                    "sensor_type": "TSL2591",
                    "timestamp": time.time(),
                    "error": None
                }
            
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] TSL2591 Raw Result: {result}")
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
            
            result = {
                "raw_lux_data": {"lux": lux},  # Raw lux data from VEML7700
                "sensor_type": "VEML7700",
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] VEML7700 Raw Result: {result}")
            return result
        elif sensor_type == "TCS34725":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating TCS34725Color")
                cache[key] = TCS34725Color(bus=bus, addr=addr, mux_address=mux_addr, mux_channel=mux_channel)
            sensor = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_color() on TCS34725Color")
            color = sensor.read_color()
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] color result: {color}")
            
            # Return raw driver data with negative lux clamping
            if color:
                # Clamp negative lux if present
                if "lux" in color and color["lux"] is not None and color["lux"] < 0:
                    try:
                        print(f"[Scheduler][WARN] Negative lux from TCS34725 ({color['lux']}); clamping to 0.0")
                    except Exception:
                        pass
                    color["lux"] = 0.0
            
            result = {
                "raw_color_data": color or {},  # Raw color data from TCS34725 driver
                "sensor_type": "TCS34725",
                "timestamp": time.time(),
                "error": None
            }
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] TCS34725 Raw Result: {result}")
            return result
        
        elif sensor_type == "AS7265X":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating AS7265X via SpectralSensorReader")
                # Create a minimal config for the SpectralSensorReader
                spectral_config = {
                    sensor_id or "as7265x_sensor": {
                        "name": "AS7265X Spectral Sensor",
                        "type": "AS7265X",
                        "connection": {"bus": bus, "address": addr}
                    }
                }
                reader = SpectralSensorReader(spectral_config)
                cache[key] = reader
            reader = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_sensors() on AS7265X SpectralSensorReader")
            results = reader.read_sensors()
            if results:
                # Get first result (should be our AS7265X sensor)
                as7265x_data = next(iter(results.values()), {})
                raw_spectrum = as7265x_data.get('raw_data', {})
                
                # Return raw driver data without processing into 6 bands
                result = {
                    "raw_spectrum_data": raw_spectrum,  # Raw 18-channel data from driver
                    "sensor_type": "AS7265X",
                    "timestamp": time.time(),
                    "error": None
                }
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print(f"[read_light_sensor][DEBUG] AS7265X Raw Result: {result}")
                return result
            else:
                # No data returned
                return {
                    "raw_spectrum_data": {},
                    "sensor_type": "AS7265X", 
                    "timestamp": time.time(),
                    "error": "No data from AS7265X sensor"
                }
        
        elif sensor_type == "AS7341":
            if key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating AS7341 via SpectralSensorReader")
                # Create a minimal config for the SpectralSensorReader
                spectral_config = {
                    sensor_id or "as7341_sensor": {
                        "name": "AS7341 Spectral Sensor", 
                        "type": "AS7341",
                        "connection": {"bus": bus, "address": addr}
                    }
                }
                reader = SpectralSensorReader(spectral_config)
                cache[key] = reader
            reader = cache[key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_sensors() on AS7341 SpectralSensorReader")
            results = reader.read_sensors()
            if results:
                # Get first result (should be our AS7341 sensor)
                as7341_data = next(iter(results.values()), {})
                raw_spectrum = as7341_data.get('raw_data', {})
                
                # Return raw driver data without processing
                result = {
                    "raw_spectrum_data": raw_spectrum,  # Raw 11-channel data from driver
                    "sensor_type": "AS7341",
                    "timestamp": time.time(),
                    "error": None
                }
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print(f"[read_light_sensor][DEBUG] AS7341 Raw Result: {result}")
                return result
            else:
                # No data returned
                return {
                    "raw_spectrum_data": {},
                    "sensor_type": "AS7341",
                    "timestamp": time.time(),
                    "error": "No data from AS7341 sensor"
                }
        
        elif sensor_type == "AS7262":
            # AS7262 6-channel visible spectral sensor
            from sensors.as7262 import AS7262Sensor
            cache_key = (sensor_type, bus, addr, mux_addr, mux_channel)
            if cache_key not in cache:
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[read_light_sensor][DEBUG] Instantiating AS7262Sensor")
                cache[cache_key] = AS7262Sensor(
                    address=addr,
                    mux_address=mux_addr,
                    mux_channel=mux_channel,
                    mock_mode=False
                )
            sensor = cache[cache_key]
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[read_light_sensor][DEBUG] Calling read_spectrum() on AS7262Sensor")
            spectrum = sensor.read_spectrum()
            
            # Sanitize spectrum to mitigate rare I2C/ADC spikes (e.g., violet channel blow-ups)
            # NOTE: Primary validation happens in the AS7262 driver, but this provides
            # a secondary defense in case corrupt data makes it through (e.g., from old
            # cached reads or race conditions during code reload).
            def _sanitize_as7262_spectrum(spec: dict) -> dict:
                if not spec:
                    return spec
                ints = list((spec.get("intensities") or []))
                # Collect valid finite non-negative values under an upper bound
                valid = []
                for v in ints:
                    try:
                        fv = float(v)
                        if fv < 0 or not (fv == fv) or fv in (float("inf"), float("-inf")):
                            continue
                        valid.append(fv)
                    except Exception:
                        continue
                # Determine a robust cap (median * factor) with absolute max
                import statistics
                cap = None
                try:
                    if valid:
                        med = statistics.median(valid)
                        cap = max(1.0, med * 5.0)  # allow some dynamics but cap extreme outliers
                except Exception:
                    cap = None
                # Hardware limit: AS7262 uses 16-bit ADC, max calibrated ~100k in bright sun
                ABS_MAX = 100000.0
                cleaned = []
                for v in ints:
                    try:
                        fv = float(v)
                        if fv < 0 or not (fv == fv) or fv in (float("inf"), float("-inf")):
                            cleaned.append(0.0)
                        else:
                            # Apply median-based cap first, then absolute ceiling
                            if cap is not None and fv > cap:
                                fv = cap
                            if fv > ABS_MAX:
                                fv = ABS_MAX
                            cleaned.append(fv)
                    except Exception:
                        cleaned.append(0.0)
                # Update spec intensities and raw_values consistently
                spec = dict(spec)
                spec["intensities"] = cleaned
                rv = dict(spec.get("raw_values") or {})
                keys = ["violet","blue","green","yellow","orange","red"]
                for i, k in enumerate(keys):
                    if i < len(cleaned):
                        rv[k] = cleaned[i]
                spec["raw_values"] = rv
                return spec
            
            if spectrum:
                spectrum = _sanitize_as7262_spectrum(spectrum)
            
            # Compute an estimated lux value from the AS7262 channels, factoring in
            # sensor gain, integration time, and a user-provided scaling factor.
            estimated_lux = None
            exposure = {}
            try:
                if spectrum:
                    # Sum calibrated intensities across the six visible bands
                    # Use a sanitized sum to avoid transient I2C glitches (NaN/inf/negatives)
                    ints = spectrum.get("intensities", []) or []
                    safe = []
                    for v in ints:
                        try:
                            # accept only finite, non-negative values; clamp absurd spikes
                            if v is None:
                                continue
                            if float("nan") == v:  # will never be True, placeholder to force except
                                continue
                            fv = float(v)
                            if fv < 0 or fv != fv or fv == float("inf") or fv == float("-inf"):
                                continue
                            # basic spike clamp to mitigate occasional bit-flips
                            if fv > 1e6:
                                fv = 1e6
                            safe.append(fv)
                        except Exception:
                            continue
                    sum_intensity = sum(safe)
                    # Gain is one of {1, 3.7, 16, 64}; integration_time is in 2.8ms steps
                    # Access the underlying driver to read current settings
                    drv = getattr(sensor, "sensor", None)
                    gain = getattr(drv, "gain", 1) or 1
                    integration_steps = getattr(drv, "integration_time", 200) or 200
                    integration_ms = float(integration_steps) * 2.8
                    # Normalize by exposure so readings are comparable across settings
                    normalized = sum_intensity / max(1e-6, (gain * (integration_ms / 100.0)))
                    # Optional per-sensor scaling from config (lets you tune toward ~20,000 lux)
                    # Reuse existing 'scaling_factor' key if present; default chosen to be reasonable
                    scale = cfg.get("scaling_factor")
                    if scale is None:
                        # Heuristic default that yields ~20k lux for typical greenhouse lighting
                        # with gain=64, integration~560ms and intensities in the ~6k range.
                        scale = 1150.0
                    estimated_lux = float(normalized) * float(scale)
                    exposure = {
                        "gain": gain,
                        "integration_ms": integration_ms,
                        "scale": float(scale)
                    }
            except Exception as _e:
                # Keep estimated_lux None on error; don't break primary reading path
                pass
            
            result = {
                "raw_spectrum_data": spectrum or {},  # Contains wavelengths, intensities, raw_values
                "sensor_type": "AS7262",
                "timestamp": time.time(),
                "error": None if spectrum else "No data from AS7262 sensor"
            }
            # Attach estimated lux and exposure if computed
            if estimated_lux is not None:
                result["estimated_lux"] = estimated_lux
                result["exposure"] = exposure
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] AS7262 Raw Result: {result}")
            return result
        
        else:
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print(f"[read_light_sensor][DEBUG] Unknown sensor type: {sensor_type}")
            return {
                "raw_data": {},
                "sensor_type": sensor_type or "UNKNOWN",
                "timestamp": time.time(),
                "error": f"Unsupported sensor type: {sensor_type}"
            }
    except Exception as e:
        print(f"[read_light_sensor][ERROR] Error reading {sensor_type}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return {
            "raw_data": {},
            "sensor_type": sensor_type or "UNKNOWN",
            "timestamp": time.time(),
            "error": str(e)
        }
