#!/usr/bin/env python3
"""
Monitor data/sensor_readings.json for updates and print a concise summary.

Usage:
  python scripts/monitor_readings.py --file data/sensor_readings.json --interval 5
"""
import argparse
import json
import os
import time
from datetime import datetime


def read_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def summarize(data):
    readings = data.get("readings", {})
    lines = []
    for sid, r in readings.items():
        ts = r.get("timestamp")
        ts_str = datetime.fromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) and ts > 0 else "n/a"
        lines.append(
            f"- {sid}: lux={r.get('lux')}, CCT={r.get('color_temp_k')}K, ts={ts_str}, error={r.get('error')}"
        )
    return "\n".join(lines) if lines else "(no readings)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default='data/sensor_readings.json', help='Path to sensor readings JSON file')
    ap.add_argument('--interval', type=float, default=5.0, help='Polling interval seconds')
    args = ap.parse_args()

    path = args.file
    last_mtime = None
    print(f"Monitoring {path} every {args.interval}s. Ctrl+C to exit.")

    try:
        while True:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                now = time.time()
                age = now - mtime
                if last_mtime is None or mtime != last_mtime:
                    data = read_json(path)
                    print(f"\n[{datetime.now().isoformat()}] File updated (age {age:.1f}s)")
                    if isinstance(data, dict):
                        print(summarize(data))
                    else:
                        print("(invalid JSON)")
                    last_mtime = mtime
                else:
                    if age > args.interval * 3:
                        print(f"[{datetime.now().isoformat()}] WARNING: readings stale (age {age:.1f}s)")
            else:
                print(f"[{datetime.now().isoformat()}] Waiting for file to appear...")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()
