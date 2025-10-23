"""Background scheduler for periodic sensor readings to avoid blocking web requests.

This module provides a lightweight background thread that periodically reads
sensor data and updates an in-memory cache, allowing web endpoints to serve
readings instantly without waiting for slow hardware I/O operations.
"""
import os
import threading
import time
import json
from datetime import datetime
from typing import Dict, Optional, Callable
from pathlib import Path


class SensorScheduler:
    """Background scheduler for periodic sensor readings."""
    
    def __init__(self, 
                 data_dir: str = "data",
                 update_interval: float = 5.0,
                 sensor_reader_func: Optional[Callable] = None):
        """Initialize the sensor scheduler.
        
        Args:
            data_dir: Directory containing sensor configuration
            update_interval: Seconds between sensor readings
            sensor_reader_func: Function to read a single sensor config
        """
        self.data_dir = Path(data_dir)
        self.update_interval = update_interval
        self.sensor_reader_func = sensor_reader_func
        
        # Thread management
        self._timer = None
        self._running = False
        # Use a re-entrant lock because some methods (e.g., start) call helpers
        # that also acquire the lock (like _load_sensor_config). A normal Lock
        # would deadlock when re-acquired by the same thread.
        self._lock = threading.RLock()
        # Config file tracking
        self._config_path = Path(data_dir) / "light_sensors.json"
        self._config_mtime = 0.0
        
        # Cached sensor data
        self._sensor_cache = {
            "readings": {},  # sensor_id -> {"lux": float, "color_temp_k": float, "timestamp": float, "error": str}
            "config": {},    # sensor_id -> config dict
            "last_update": 0.0,
            "update_count": 0,
            "error_count": 0
        }
        
        # Statistics
        self._stats = {
            "total_reads": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "avg_read_time": 0.0,
            "last_read_time": 0.0,
            "started_at": None
        }

        # Process-level lock file to prevent multiple schedulers
        self._lockfile_path = self.data_dir / "scheduler.lock"

    def _acquire_process_lock(self) -> bool:
        """Create a simple PID lock file to ensure a single scheduler instance.

        Returns True if lock acquired, False if another live instance holds the lock.
        """
        try:
            if self._lockfile_path.exists():
                try:
                    with open(self._lockfile_path, 'r') as f:
                        content = f.read().strip()
                    pid = int(content.split("\n", 1)[0]) if content else None
                except Exception:
                    pid = None
                # Check if PID is alive
                if pid and pid > 0:
                    alive = False
                    try:
                        # On POSIX, sending signal 0 checks existence
                        os.kill(pid, 0)
                        alive = True
                    except ProcessLookupError:
                        alive = False
                    except PermissionError:
                        # Process exists but not ours; assume alive
                        alive = True
                    if alive:
                        print(f"[Scheduler][LOCK] Another scheduler appears to be running with PID {pid}; not starting a second instance.")
                        return False
                    else:
                        print(f"[Scheduler][LOCK] Stale lock detected for PID {pid}; reclaiming lock.")
                # Remove stale or invalid lock
                try:
                    self._lockfile_path.unlink(missing_ok=True)
                except Exception:
                    pass
            # Write our PID to lock file
            with open(self._lockfile_path, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            print(f"[Scheduler][LOCK][WARN] Failed to manage lock file: {e}. Proceeding without lock.")
            return True

    def _release_process_lock(self):
        """Remove the PID lock file if owned by this process."""
        try:
            if self._lockfile_path.exists():
                pid = None
                try:
                    with open(self._lockfile_path, 'r') as f:
                        content = f.read().strip()
                    pid = int(content.split("\n", 1)[0]) if content else None
                except Exception:
                    pid = None
                if pid == os.getpid():
                    self._lockfile_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _lux_confidence_for_sensor_type(self, sensor_type: str) -> float:
        """Return a confidence weight for lux blending based on sensor type.

        Defaults can be overridden via environment variables like CONFIDENCE_TSL2591, CONFIDENCE_AS7262, etc.
        """
        st = (sensor_type or '').upper()
        defaults = {
            'TSL2591': 1.0,   # high-confidence lux meter
            'BH1750': 0.9,    # decent lux sensor
            'VEML7700': 0.9,  # decent lux sensor
            'TCS34725': 0.2,  # color sensor, lux is coarse
            'AS7262': 0.7,    # spectral estimated lux (mid confidence)
            'AS7265X': 0.6,   # spectral estimated lux (if used)
            'AS7341': 0.6     # spectral estimated lux (if used)
        }
        env_key = f"CONFIDENCE_{st}"
        try:
            val = os.getenv(env_key)
            if val is not None:
                f = float(val)
                # Clamp to sensible range
                if f < 0:
                    f = 0.0
                if f > 5:
                    f = 5.0
                return f
        except Exception:
            pass
        return defaults.get(st, 0.5)
    
    def start(self):
        """Start the background scheduler."""
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print("[SensorScheduler][DEBUG] start() called")
        try:
            with self._lock:
                if self._running:
                    print("[SensorScheduler][DEBUG] Already running, skipping start.")
                    return
                # Acquire process lock to ensure single instance
                if not self._acquire_process_lock():
                    return
                self._running = True
                self._stats["started_at"] = datetime.now().isoformat()
                print(f"🤖 Starting sensor scheduler (interval: {self.update_interval}s)")
                # Load initial config
                self._load_sensor_config()
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[SensorScheduler][DEBUG] Finished config load (inside lock), about to call _schedule_next_update()")
                self._schedule_next_update()
                if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                    print("[SensorScheduler][DEBUG] Returned from _schedule_next_update()")
            if os.getenv("VERBOSE_SCHEDULER_LOGS"):
                print("[SensorScheduler][DEBUG] start() method completed")
        except Exception as e:
            import traceback
            print(f"[SensorScheduler][ERROR] Exception in start(): {e}")
            traceback.print_exc()
    
    def stop(self):
        """Stop the background scheduler (non-blocking, robust)."""
        # Try to acquire the lock, but don't block forever
        acquired = self._lock.acquire(timeout=2.0)
        try:
            if not acquired:
                print("[WARN] Could not acquire scheduler lock promptly during stop; forcing shutdown.")
                self._running = False
                return
            if not self._running:
                return
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
            print("🛑 Sensor scheduler stopped")
            # Release PID lock
            self._release_process_lock()
        finally:
            if acquired:
                self._lock.release()
    
    def get_cached_readings(self) -> Dict:
        """Get current cached sensor readings."""
        with self._lock:
            return {
                "config": {"sensors": self._sensor_cache["config"].copy()},
                "readings": self._sensor_cache["readings"].copy(),
                "zone_fusion": self._sensor_cache.get("zone_fusion", {}).copy(),
                "timestamp": self._sensor_cache.get("last_update")
            }
    
    def get_stats(self) -> Dict:
        """Get scheduler performance statistics."""
        with self._lock:
            return {
                "running": self._running,
                "update_interval": self.update_interval,
                "cache_stats": {
                    "sensor_count": len(self._sensor_cache["config"]),
                    "last_update": self._sensor_cache["last_update"],
                    "update_count": self._sensor_cache["update_count"],
                    "error_count": self._sensor_cache["error_count"]
                },
                "performance": self._stats.copy()
            }
    
    def force_update(self):
        """Force an immediate sensor reading update."""
        if not self._running:
            return
        
        # Cancel current timer and run update now
        if self._timer:
            self._timer.cancel()
        
        self._update_sensors()
        self._schedule_next_update()
    
    def set_update_interval(self, interval: float):
        """Change the update interval."""
        with self._lock:
            self.update_interval = max(1.0, interval)  # Minimum 1 second
            print(f"📅 Sensor update interval changed to {self.update_interval}s")
    
    def _load_sensor_config(self):
        """Load sensor configuration from file."""
        config_file = self._config_path
        print(f"[Scheduler][DEBUG] Attempting to load config from {config_file}")
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    sensors = data.get("sensors", {})
                    print(f"[Scheduler][DEBUG] Raw sensors config: {sensors}")
                    with self._lock:
                        self._sensor_cache["config"] = sensors
                        # Update last known mtime
                        try:
                            self._config_mtime = config_file.stat().st_mtime
                        except Exception:
                            pass
                        # Initialize readings cache for new sensors
                        for sensor_id in sensors:
                            if sensor_id not in self._sensor_cache["readings"]:
                                self._sensor_cache["readings"][sensor_id] = {
                                    "lux": None,
                                    "color_temp_k": None,
                                    "timestamp": 0.0,
                                    "error": None
                                }
                    print(f"📊 Loaded {len(sensors)} sensor configurations: {list(sensors.keys())}")
            else:
                print(f"⚠️  No light_sensors.json found at {config_file}, scheduler will run with empty config")
        except Exception as e:
            print(f"❌ Error loading sensor config: {e}")
    
    def _schedule_next_update(self):
        """Schedule the next sensor update."""
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print(f"[SensorScheduler][DEBUG] _schedule_next_update called. running={self._running}")
        if not self._running:
            print("[SensorScheduler][DEBUG] Not running, will not schedule next update.")
            return
        self._timer = threading.Timer(self.update_interval, self._update_sensors)
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print(f"[SensorScheduler][DEBUG] Timer set for {self.update_interval} seconds.")
        self._timer.start()
    

    def _update_sensors(self):
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print("[SensorScheduler][DEBUG] _update_sensors() called")
        """Perform sensor readings and update cache, with logging."""
        if not self._running:
            print("[Scheduler][DEBUG] _update_sensors called but scheduler not running.")
            return
        start_time = time.time()
        try:
            # Reload config if file mtime changed (fast detection)
            try:
                if self._config_path.exists():
                    mtime = self._config_path.stat().st_mtime
                    if mtime != self._config_mtime:
                        print("[Scheduler][DEBUG] Detected config change on disk. Reloading...")
                        self._load_sensor_config()
                elif self._sensor_cache["config"]:
                    # Config file disappeared; clear config
                    print("[Scheduler][DEBUG] Config file missing; clearing sensors config.")
                    with self._lock:
                        self._sensor_cache["config"] = {}
                        self._config_mtime = 0.0
            except Exception as e:
                print(f"[Scheduler][WARN] Failed to check config mtime: {e}")
            sensors_config = self._sensor_cache["config"]
            print(f"[Scheduler][DEBUG] sensors_config: {sensors_config}")
            if not sensors_config:
                print("[Scheduler][DEBUG] No sensors configured. Skipping update.")
                self._schedule_next_update()
                return
            sensor_ids = list(sensors_config.keys())
            print(f"[Scheduler] Collecting data for sensors: {sensor_ids}")
            readings_updated = 0
            import traceback
            import threading
            def sensor_read_with_timeout(func, args=(), kwargs=None, timeout=5):
                """Run sensor read with timeout to catch hangs."""
                result = {}
                exc = {}
                def target():
                    try:
                        result['value'] = func(*args, **(kwargs or {}))
                    except Exception as e:
                        exc['error'] = e
                        exc['trace'] = traceback.format_exc()
                t = threading.Thread(target=target)
                t.start()
                t.join(timeout)
                if t.is_alive():
                    print(f"[Scheduler][ERROR] Sensor read for {args} timed out after {timeout}s!")
                    return None, f"Timeout after {timeout}s"
                if 'error' in exc:
                    print(f"[Scheduler][ERROR] Exception during sensor read: {exc['error']}\n{exc['trace']}")
                    return None, str(exc['error'])
                return result.get('value'), None

            for sensor_id, sensor_config in sensors_config.items():
                print(f"[Scheduler][DEBUG] Reading sensor {sensor_id} with config: {sensor_config}")
                try:
                    if self.sensor_reader_func:
                        reading, err = sensor_read_with_timeout(self.sensor_reader_func, args=(sensor_config, sensor_id), timeout=5)
                        if err:
                            raise Exception(err)
                    else:
                        reading = self._default_sensor_read(sensor_config)
                    print(f"[Scheduler][DEBUG] Sensor {sensor_id} reading result: {reading}")
                    # --- Write Guard: avoid overwriting with empty/invalid frames ---
                    sensor_type = str(sensor_config.get("type", "")).upper()
                    def _is_valid_tcs34725(r):
                        try:
                            raw = (r or {}).get("raw_color_data") or {}
                            if not raw:
                                return False
                            lux = raw.get("lux")
                            # Consider valid if lux is a finite number and any channel present
                            if lux is None:
                                return False
                            import math
                            if isinstance(lux, (int, float)) and math.isfinite(float(lux)):
                                # If all raw channels missing/zero, likely invalid
                                ch = [raw.get(k) for k in ("red_raw","green_raw","blue_raw","clear_raw")]
                                if any((isinstance(v,(int,float)) and v > 0) for v in ch if v is not None):
                                    return True
                                # If channels absent but lux valid, still accept
                                return True
                            return False
                        except Exception:
                            return False

                    def _is_valid_tsl2591(r):
                        try:
                            raw = (r or {}).get("raw_spectrum_data") or (r or {}).get("raw_lux_data") or {}
                            if not raw:
                                return False
                            lux = raw.get("lux")
                            import math
                            if lux is None:
                                return False
                            if not isinstance(lux, (int, float)):
                                return False
                            if not math.isfinite(float(lux)):
                                return False
                            # Accept saturated frames; upstream logic adapts exposure next cycle
                            return True
                        except Exception:
                            return False

                    should_write = True
                    if sensor_type == "TCS34725":
                        should_write = _is_valid_tcs34725(reading)
                        if not should_write:
                            print(f"[Scheduler][WARN] Write-guard: Skipping TCS34725 update for {sensor_id} due to empty/invalid raw_color_data; preserving last good value.")
                    elif sensor_type == "TSL2591":
                        should_write = _is_valid_tsl2591(reading)
                        if not should_write:
                            print(f"[Scheduler][WARN] Write-guard: Skipping TSL2591 update for {sensor_id} due to invalid lux; preserving last good value.")

                    with self._lock:
                        if should_write:
                            # Store all fields from reading, plus timestamp and error
                            entry = dict(reading) if reading else {}
                            entry["timestamp"] = time.time()
                            entry["error"] = None if reading else err
                            self._sensor_cache["readings"][sensor_id] = entry
                        else:
                            # Preserve previous entry; update only error count/statistics outside
                            pass
                    readings_updated += 1
                    self._stats["successful_reads"] += 1
                except Exception as e:
                    error_msg = str(e)
                    print(f"⚠️  Error reading sensor {sensor_id}: {error_msg}")
                    with self._lock:
                        self._sensor_cache["readings"][sensor_id] = {
                            "lux": None,
                            "color_temp_k": None,
                            "timestamp": time.time(),
                            "error": error_msg
                        }
                        self._sensor_cache["error_count"] += 1
                    self._stats["failed_reads"] += 1
            # Update cache metadata
            with self._lock:
                self._sensor_cache["last_update"] = time.time()
                self._sensor_cache["update_count"] += 1
            elapsed = time.time() - start_time
            print(f"[Scheduler] Sensor data collection complete: {readings_updated} sensors in {elapsed:.3f}s")
            # Update performance stats
            read_time = time.time() - start_time
            self._stats["total_reads"] += 1
            self._stats["last_read_time"] = read_time
            # Running average of read time
            prev_avg = self._stats["avg_read_time"]
            total_reads = self._stats["total_reads"]
            self._stats["avg_read_time"] = ((prev_avg * (total_reads - 1)) + read_time) / total_reads
            if readings_updated > 0:
                print(f"📊 Updated {readings_updated} sensor readings in {read_time:.3f}s")

            # --- FUSION FOR ZONES ---
            try:
                import json
                from control.fusion_utils.fusion_calculator import calculate_fusion_for_positions
                zones_path = self.data_dir / "zones.json"
                if zones_path.exists():
                    with open(zones_path, 'r') as f:
                        zones_data = json.load(f)
                    zones = zones_data.get("zones", {})
                    grid_size = zones_data.get("grid_size", {"rows": 24, "cols": 12})
                    
                    # Generate ALL zone keys for the full grid layout
                    all_zone_keys = []
                    for row in range(grid_size["rows"]):
                        for col in range(grid_size["cols"]):
                            all_zone_keys.append(f"{row}-{col}")
                    
                    print(f"[Scheduler][INFO] Calculating light metrics for {len(all_zone_keys)} grid cells ({grid_size['rows']}x{grid_size['cols']})")
                    
                    # For each zone, estimate fusion at its center (use key as position if possible)
                    fusion_results = {}
                    # Prepare sensor data and positions from cache/config
                    sensor_configs = self._sensor_cache["config"]
                    sensor_readings = self._sensor_cache["readings"]
                    sensor_data_list = []
                    positions = []
                    scaling_factors = []  # Track scaling factor per sensor
                    for sensor_id, config in sensor_configs.items():
                        reading = sensor_readings.get(sensor_id, {})
                        sensor_type = config.get("type")
                        if not sensor_type:
                            continue
                        # Get scaling factor from config (default to 1.0)
                        scaling_factor = float(config.get("scaling_factor", 1.0))
                        # PATCH: Use correct raw data for TCS34725
                        if sensor_type == "TCS34725":
                            # Try both 'raw_color_data' and fallback to top-level keys if needed
                            raw_color_data = reading.get("raw_color_data")
                            if not raw_color_data:
                                # Some code may store raw values at the top level
                                raw_color_data = {k: reading.get(k) for k in ["red_raw", "green_raw", "blue_raw", "clear_raw", "lux", "color_temperature_k"] if k in reading}
                            # Include optional per-sensor lux calibration from config
                            lux_cal = config.get("lux_calibration") or config.get("calibration_factor")
                            if lux_cal is not None:
                                try:
                                    lux_cal = float(lux_cal)
                                except Exception:
                                    lux_cal = None
                            data = {"sensor_type": sensor_type, "raw_color_data": raw_color_data}
                            if lux_cal is not None:
                                data["lux_calibration"] = lux_cal
                        elif sensor_type == "TSL2591":
                            lux_cal = config.get("lux_calibration") or config.get("calibration_factor")
                            if lux_cal is not None:
                                try:
                                    lux_cal = float(lux_cal)
                                except Exception:
                                    lux_cal = None
                            data = {"sensor_type": sensor_type, "raw_spectrum_data": reading.get("raw_spectrum_data", {})}
                            if lux_cal is not None:
                                data["lux_calibration"] = lux_cal
                        elif sensor_type == "AS7262":
                            # AS7262 6-channel spectral sensor (450-650nm visible)
                            raw_spectrum_data = reading.get("raw_spectrum_data", {})
                            data = {"sensor_type": sensor_type, "raw_spectrum_data": raw_spectrum_data}
                            # Prefer the calibrated estimated_lux if available for blending
                            if "estimated_lux" in reading:
                                try:
                                    data["estimated_lux"] = float(reading["estimated_lux"])
                                except Exception:
                                    pass
                        elif sensor_type == "BH1750":
                            data = {"sensor_type": sensor_type, "raw_lux_data": reading.get("raw_lux_data", {})}
                        elif sensor_type == "UV_SIM":
                            data = {"sensor_type": sensor_type, "raw_uv_data": reading.get("raw_uv_data", {})}
                        else:
                            continue
                        sensor_data_list.append(data)
                        scaling_factors.append(scaling_factor)
                        # Use explicit position if present, else parse from zone_key if available
                        if "position" in config:
                            pos = tuple(config["position"])
                        elif "zone_key" in config:
                            try:
                                row, col = map(int, str(config["zone_key"]).split("-"))
                                pos = (row, col)
                            except Exception:
                                pos = (0, 0)
                        else:
                            pos = (0, 0)
                        positions.append(pos)
                    # Handle single-sensor case: directly use sensor data with no interpolation
                    if len(sensor_data_list) == 1 and len(positions) == 1:
                        print("[Scheduler][INFO] Single sensor detected; using direct spectrum for all zones with distance attenuation.")
                        sensor_data = sensor_data_list[0]
                        sensor_pos = positions[0]
                        scaling_factor = scaling_factors[0]
                        print(f"[Scheduler][DEBUG] Sensor data for fusion: {sensor_data}")
                        print(f"[Scheduler][DEBUG] Scaling factor: {scaling_factor}")
                        
                        # Extract sensor's actual lux value (prefer calibrated/estimated when available)
                        sensor_lux = None
                        if 'raw_color_data' in sensor_data:
                            sensor_lux = sensor_data['raw_color_data'].get('lux')
                        elif 'raw_spectrum_data' in sensor_data:
                            sensor_lux = sensor_data['raw_spectrum_data'].get('lux')
                        elif 'raw_lux_data' in sensor_data:
                            sensor_lux = sensor_data['raw_lux_data'].get('lux')
                        # Prefer estimated_lux for AS7262 when present
                        if sensor_lux is None and sensor_data.get('sensor_type') == 'AS7262':
                            est = sensor_data.get('estimated_lux')
                            if isinstance(est, (int, float)):
                                sensor_lux = float(est)
                        
                        # Map sensor data to spectrum bins once
                        from control.spectral_fusion import SpectralDataFusion
                        spectrum_bins = SpectralDataFusion.create_spectrum_bins(min_wavelength=280, max_wavelength=850, bin_width=20)
                        sensor_type = sensor_data.get("sensor_type")
                        bin_contributions = SpectralDataFusion.map_sensor_to_bins(sensor_type, sensor_data, spectrum_bins)
                        print(f"[Scheduler][DEBUG] Bin contributions (non-zero): {dict((k, v) for k, v in bin_contributions.items() if v > 0)}")
                        base_intensities = [bin_contributions.get(i, 0.0) for i in range(len(spectrum_bins))]
                        
                        # Check if sensor has valid data (any non-zero intensity)
                        has_valid_data = any(val > 0 for val in base_intensities)
                        
                        # Calculate for ALL grid cells, not just planted zones
                        for zone_key in all_zone_keys:
                            try:
                                x, y = map(float, zone_key.split("-"))
                            except Exception:
                                continue
                            target_pos = (x, y)
                            # Calculate distance attenuation (inverse square law)
                            import math
                            dx = target_pos[0] - sensor_pos[0]
                            dy = target_pos[1] - sensor_pos[1]
                            true_distance = math.sqrt(dx*dx + dy*dy)
                            # Special-case the sensor's own cell: no attenuation and report 0.0 distance
                            if true_distance == 0.0:
                                effective_distance = 0.0
                                attenuation = 1.0
                            else:
                                # Clamp only the effective distance used for attenuation to avoid singularity
                                effective_distance = true_distance if true_distance >= 0.1 else 0.1
                                attenuation = 1.0 / (effective_distance ** 2 + 1.0)  # +1 prevents over-amplification at near-zero
                            
                            # Apply attenuation and scaling factor to intensities
                            attenuated_intensities = [val * attenuation * scaling_factor for val in base_intensities]
                            
                            
                            # For lux: use sensor's actual lux value with attenuation (don't recalculate from bins)
                            if sensor_lux is not None:
                                lux = sensor_lux * attenuation
                            else:
                                # Fallback to bin-based estimation if sensor doesn't provide lux
                                lux = self._estimate_lux_from_spectrum(spectrum_bins, attenuated_intensities)
                            
                            ppfd = self._estimate_ppfd_from_spectrum(spectrum_bins, attenuated_intensities)
                            # Consider valid if any bin intensity > 0 or if the sensor reported a lux value
                            is_valid = has_valid_data or (sensor_lux is not None and sensor_lux > 0)
                            fusion_results[zone_key] = {
                                "spectrum_bins": [list(b) for b in spectrum_bins],
                                "intensities": attenuated_intensities,
                                "lux": lux,
                                "ppfd": ppfd,
                                "color": None,
                                "single_sensor_mode": True,
                                # Report the true geometric distance (unclamped), rounded for readability
                                "distance_from_sensor": round(true_distance, 2),
                                "valid": is_valid
                            }
                    else:
                        # Multi-sensor fusion with blended lux (photopic + sensor-average)
                        # Read blend alpha from env at runtime (default 0.5)
                        try:
                            blend_alpha = float(os.getenv('FUSED_LUX_BLEND_ALPHA', '0.5'))
                        except Exception:
                            blend_alpha = 0.5
                        # Pre-extract sensor lux values and positions
                        sensor_lux_list = []  # list of (lux, (x,y), sensor_type) for sensors providing lux
                        for sdata, spos in zip(sensor_data_list, positions):
                            lux_val = None
                            sensor_type = sdata.get('sensor_type', 'unknown')
                            if 'raw_color_data' in sdata:
                                lux_val = sdata['raw_color_data'].get('lux')
                            elif 'raw_spectrum_data' in sdata:
                                lux_val = sdata['raw_spectrum_data'].get('lux')
                            elif 'raw_lux_data' in sdata:
                                lux_val = sdata['raw_lux_data'].get('lux')
                            # If AS7262 provides estimated_lux, use it as lux source
                            if lux_val is None and sensor_type == 'AS7262':
                                est = sdata.get('estimated_lux')
                                if isinstance(est, (int, float)):
                                    lux_val = float(est)
                            if lux_val is not None:
                                sensor_lux_list.append((float(lux_val), (float(spos[0]), float(spos[1])), sensor_type))
                        
                        # Calculate for ALL grid cells
                        for zone_key in all_zone_keys:
                            try:
                                x, y = map(float, zone_key.split("-"))
                            except Exception:
                                continue
                            target_pos = (x, y)
                            fusion = calculate_fusion_for_positions(sensor_data_list, positions, [target_pos])[0]
                            histogram = fusion['histogram']
                            spectrum_bins = histogram.get('wavelengths', [])
                            intensities = histogram.get('intensities', [])
                            # If histogram provided wavelength centers (numbers), convert to pseudo 20nm bins.
                            # Be robust to numpy scalars by checking for non-sequence (not list/tuple) elements.
                            if spectrum_bins and not isinstance(spectrum_bins[0], (list, tuple)):
                                try:
                                    spectrum_bins = [
                                        (float(c) - 10.0, float(c) + 10.0)
                                        for c in spectrum_bins
                                    ]
                                except Exception:
                                    # If conversion fails, fall back to empty bins to avoid unpack errors downstream
                                    spectrum_bins = []
                            # Check if any sensor data is valid
                            has_valid_data = any(val > 0 for val in intensities)
                            # Photopic lux from fused spectrum
                            photopic_lux = self._estimate_lux_from_spectrum(spectrum_bins, intensities)
                            # Sensor-average lux (inverse-distance weighting with confidence)
                            # TCS34725 has lower confidence for lux (it's a color sensor, not a lux meter)
                            avg_lux = None
                            total_w = 0.0
                            accum = 0.0
                            if sensor_lux_list:
                                import math
                                for slux, spos, stype in sensor_lux_list:
                                    # Apply confidence weight by sensor type (configurable via env)
                                    confidence = self._lux_confidence_for_sensor_type(stype)
                                    dx = target_pos[0] - spos[0]
                                    dy = target_pos[1] - spos[1]
                                    dist = math.hypot(dx, dy)
                                    if dist <= 0.01:
                                        # If at sensor location, use that sensor's lux directly
                                        avg_lux = slux
                                        total_w = 1.0
                                        accum = slux
                                        break
                                    w = confidence / (dist * dist)
                                    total_w += w
                                    accum += slux * w
                                if avg_lux is None:
                                    avg_lux = accum / total_w if total_w > 0 else None
                            # Blend final lux; if avg_lux unavailable, use photopic; if photopic zero, use avg
                            if avg_lux is not None and photopic_lux is not None:
                                lux = blend_alpha * photopic_lux + (1.0 - blend_alpha) * avg_lux
                            elif photopic_lux is not None and photopic_lux > 0:
                                lux = photopic_lux
                            else:
                                lux = avg_lux if avg_lux is not None else 0.0
                            # Store 20nm bin values, lux, ppfd
                            
                            # Note: PPFD continues to come from the spectrum path (not blended)
                            ppfd = self._estimate_ppfd_from_spectrum(spectrum_bins, intensities)
                            fusion_results[zone_key] = {
                                "spectrum_bins": list(spectrum_bins),
                                "intensities": list(intensities),
                                "lux": float(round(lux, 3)),
                                "ppfd": ppfd,
                                "color": histogram.get('color', None),
                                "single_sensor_mode": False,
                                "valid": has_valid_data
                            }
                    with self._lock:
                        self._sensor_cache["zone_fusion"] = fusion_results
                    # Write zone_fusion + readings to sensor_readings.json for the dashboard
                    self._write_cache_to_file()
            except Exception as e:
                print(f"[Scheduler][ERROR] Fusion calculation for zones failed: {e}")
        except Exception as e:
            print(f"❌ Critical error in sensor update: {e}")
            with self._lock:
                self._sensor_cache["error_count"] += 1
        finally:
            # Schedule next update
            self._schedule_next_update()
    
    def _default_sensor_read(self, config: Dict) -> Dict:
        """Default sensor reading implementation."""
        # This is a fallback - normally the Flask app will provide the reader function
        print(f"⚠️  Using default sensor reader for {config.get('name', 'unknown')}")
        return {"lux": None, "color_temp_k": None}

    # --- Simple estimators for derived metrics from fused spectrum ---
    def _estimate_lux_from_spectrum(self, spectrum_bins, intensities) -> float:
        """Approximate lux by weighting visible range with a crude photopic curve.

        This uses a simple triangular weighting centered at 555 nm to approximate
        the human eye's photopic sensitivity. It's not exact but provides a stable
        relative metric for dashboard display.
       
           Intensities are spectral densities (lux/nm), so we integrate by multiplying
           by bin width to get total lux contribution from each bin.
        """
        if not spectrum_bins or not intensities:
            return 0.0
        weighted_sum = 0.0
        weight_sum = 0.0
        total_width = 0.0
        for (lo, hi), val in zip(spectrum_bins, intensities):
            center = (lo + hi) / 2.0
            bin_width = hi - lo
            # Only consider visible band roughly 400-700 nm
            if center < 400 or center > 700:
                continue
            # Triangular weight around 555 nm with width ~310 nm
            weight = max(0.0, 1.0 - abs(center - 555.0) / 155.0)
            spectral_density = max(0.0, float(val))
            weighted_sum += spectral_density * bin_width * weight
            weight_sum += weight * bin_width
            total_width += bin_width
        if weight_sum <= 0 or total_width <= 0:
            return 0.0
        # Normalize so a flat spectrum preserves total lux
        normalized = weighted_sum * (total_width / weight_sum)
        return float(round(normalized, 3))

    def _estimate_ppfd_from_spectrum(self, spectrum_bins, intensities) -> float:
        """Estimate PPFD (µmol/m²/s) from binned spectrum using configurable method.

        Methods:
        - flat: sum calibrated intensities in PAR (400–700 nm) — current default behavior.
        - photon_weighted: per-bin photon count using E = h c / λ and converting photons/s to µmol/s/m².
        """
        if not spectrum_bins or not intensities:
            return 0.0

        # Try reading calculation method from optional config; default to 'flat'
        method = "flat"
        try:
            cfg_path = self.data_dir / "light_control_config.json"
            if cfg_path.exists():
                with open(cfg_path, 'r') as f:
                    cfg = json.load(f)
                method = (
                    cfg.get("ppfd_calculation", {}).get("method")
                    or cfg.get("ppfd_method")
                    or "flat"
                )
        except Exception:
            method = "flat"

        method = str(method).lower()

        if method == "photon_weighted":
            # Dimensionless photon weighting that preserves overall scale:
            # weight each bin by (lambda_ref / lambda_nm) within PAR, which emphasizes shorter wavelengths
            # while keeping magnitude comparable to the flat sum when spectrum is centered near lambda_ref.
            lambda_ref = 550.0  # nm
            weighted_sum = 0.0
            par_present = False
            for (lo, hi), val in zip(spectrum_bins, intensities):
                center_nm = (lo + hi) / 2.0
                if 400 <= center_nm <= 700:
                    par_present = par_present or (val is not None and float(val) > 0.0)
                    weight = lambda_ref / center_nm
                    weighted_sum += max(0.0, float(val)) * weight
            result = float(round(weighted_sum, 3))
            # Fallback: if result is 0 despite PAR intensities present, use flat sum
            if result <= 0.0 and par_present:
                par_sum = 0.0
                for (lo, hi), val in zip(spectrum_bins, intensities):
                    center = (lo + hi) / 2.0
                    if 400 <= center <= 700:
                        par_sum += max(0.0, float(val))
                return float(round(par_sum, 3))
            return result
        else:
            # flat method: sum PAR-band intensities
            par_sum = 0.0
            for (lo, hi), val in zip(spectrum_bins, intensities):
                center = (lo + hi) / 2.0
                if 400 <= center <= 700:
                    par_sum += max(0.0, float(val))
            return float(round(par_sum, 3))
    
    def _write_cache_to_file(self):
        """Write sensor readings and zone metrics to separate files."""
        try:
            output_file = self.data_dir / "sensor_readings.json"
            zone_metrics_file = self.data_dir / "zone_light_metrics.json"
            
            with self._lock:
                zone_fusion = self._sensor_cache.get("zone_fusion", {})
                
                # Write sensor readings only (no zone data)
                data_to_write = {
                    "timestamp": self._sensor_cache.get("last_update"),
                    "readings": self._sensor_cache.get("readings", {})
                }
                
                # Prepare zone light metrics without spectrum_bins (moved to spectrum_bins.json)
                zone_metrics = {
                    "timestamp": self._sensor_cache.get("last_update"),
                    "zones": {}
                }
                
                for zone_key, zone_data in zone_fusion.items():
                    # Extract only the dynamic data (exclude spectrum_bins)
                    zone_metrics["zones"][zone_key] = {
                        "intensities": zone_data.get("intensities", []),
                        "lux": zone_data.get("lux", 0.0),
                        "ppfd": zone_data.get("ppfd", 0.0),
                        "color": zone_data.get("color"),
                        "single_sensor_mode": zone_data.get("single_sensor_mode", False),
                        "distance_from_sensor": zone_data.get("distance_from_sensor", 0.0),
                        "valid": zone_data.get("valid", True)
                    }
            
            # Write sensor readings file (no zone data)
            with open(output_file, 'w') as f:
                json.dump(data_to_write, f, indent=2)
            
            # Write separate zone metrics file
            with open(zone_metrics_file, 'w') as f:
                json.dump(zone_metrics, f, indent=2)
            
            print(f"[Scheduler] Wrote cache to {output_file} and {zone_metrics_file}")
        except Exception as e:
            print(f"[Scheduler][ERROR] Failed to write sensor files: {e}")


# Global scheduler instance for the Flask app
_global_scheduler = None


def get_scheduler() -> Optional[SensorScheduler]:
    """Get the global scheduler instance."""
    return _global_scheduler


def start_scheduler(data_dir: str = "data", 
                   update_interval: float = 5.0,
                   sensor_reader_func: Optional[Callable] = None) -> SensorScheduler:
    """Start the global sensor scheduler."""
    global _global_scheduler
    
    if _global_scheduler and _global_scheduler._running:
        print("⚠️  Scheduler already running")
        return _global_scheduler
    
    _global_scheduler = SensorScheduler(
        data_dir=data_dir,
        update_interval=update_interval,
        sensor_reader_func=sensor_reader_func
    )
    
    _global_scheduler.start()
    return _global_scheduler


def stop_scheduler():
    """Stop the global sensor scheduler."""
    global _global_scheduler
    
    if _global_scheduler:
        _global_scheduler.stop()
        _global_scheduler = None


# Example usage for testing
if __name__ == "__main__":
    def mock_sensor_reader(config, sensor_id):
        """Mock sensor reader for testing."""
        import random
        time.sleep(0.1)  # Simulate slow I/O
        return {
            "lux": random.uniform(100, 1000),
            "color_temp_k": random.uniform(3000, 6000)
        }
    
    # Start scheduler
    scheduler = start_scheduler(
        update_interval=3.0,
        sensor_reader_func=mock_sensor_reader
    )
    
    try:
        # Let it run for a bit
        time.sleep(15)
        
        # Check results
        readings = scheduler.get_cached_readings()
        stats = scheduler.get_stats()
        
        print("\nCached readings:", json.dumps(readings, indent=2))
        print("\nScheduler stats:", json.dumps(stats, indent=2))
        
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop_scheduler()