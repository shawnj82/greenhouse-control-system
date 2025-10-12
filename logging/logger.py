"""Centralized logger that writes console and CSV logs."""
import csv
import os
import time

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CSV_PATH = os.path.join(LOG_DIR, "readings.csv")


class Logger:
    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "temperature_c", "humidity", "lux", "soil_percent"])

    def log(self, temperature_c=None, humidity=None, lux=None, soil_percent=None):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts} | T={temperature_c}C H={humidity}% Lux={lux} Soil={soil_percent}%")
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([ts, temperature_c, humidity, lux, soil_percent])