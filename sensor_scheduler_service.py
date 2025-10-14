"""
Standalone sensor scheduler service for greenhouse-control-system.
Periodically reads all configured sensors and writes results to a shared JSON file.
"""
import os
import time
import json
from background_scheduler import start_scheduler, stop_scheduler
from sensor_shared import DATA_DIR, _app_config, read_light_sensor

# Path to shared readings file
READINGS_FILE = os.path.join(DATA_DIR, "sensor_readings.json")

# How often to write readings (seconds)
WRITE_INTERVAL = _app_config.get("sensor_cache_ttl", 5)


def write_atomic_json(filepath, data):
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, filepath)


def main():
    print("[SchedulerService] Starting sensor scheduler...")
    scheduler = start_scheduler(
        data_dir=DATA_DIR,
        update_interval=WRITE_INTERVAL,
        sensor_reader_func=read_light_sensor
    )
    try:
        while True:
            print("[SchedulerService][DEBUG] Main loop: about to get_cached_readings()")
            readings = scheduler.get_cached_readings()
            print(f"[SchedulerService][DEBUG] Main loop: got readings: {readings}")
            print(f"[SchedulerService][DEBUG] Main loop: about to write to {READINGS_FILE}")
            write_atomic_json(READINGS_FILE, readings)
            print(f"[SchedulerService] Wrote sensor readings to {READINGS_FILE}")
            time.sleep(WRITE_INTERVAL)
    except KeyboardInterrupt:
        print("[SchedulerService] Shutting down...")
    finally:
        stop_scheduler()
        print("[SchedulerService] Scheduler stopped.")


if __name__ == "__main__":
    main()
