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
    
    def start(self):
        """Start the background scheduler."""
        if os.getenv("VERBOSE_SCHEDULER_LOGS"):
            print("[SensorScheduler][DEBUG] start() called")
        try:
            with self._lock:
                if self._running:
                    print("[SensorScheduler][DEBUG] Already running, skipping start.")
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
        finally:
            if acquired:
                self._lock.release()
    
    def get_cached_readings(self) -> Dict:
        """Get current cached sensor readings."""
        with self._lock:
            return {
                "config": {"sensors": self._sensor_cache["config"].copy()},
                "readings": self._sensor_cache["readings"].copy()
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
                    with self._lock:
                        # Store all fields from reading, plus timestamp and error
                        entry = dict(reading) if reading else {}
                        entry["timestamp"] = time.time()
                        entry["error"] = None if reading else err
                        self._sensor_cache["readings"][sensor_id] = entry
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