"""Example orchestrator for the greenhouse sensors and controllers.

This is a simple loop that reads sensors and toggles outputs based on thresholds.
It's intentionally simple so you can extend it for scheduling, PID control, or remote APIs.
"""
import time
from sensors.dht22 import DHT22
from sensors.bh1750 import BH1750
from sensors.soil_moisture import SoilMoisture
from control.relay import Relay
from control.fan_controller import FanController
from logging import logger as log_module


def main():
    logger = log_module.Logger()
    dht = DHT22(pin=4)
    light = BH1750()
    soil = SoilMoisture()
    grow_light = Relay(pin=17, active_high=True)
    heater = Relay(pin=27, active_high=True)
    fan = FanController(pin=22)

    try:
        while True:
            d = dht.read()
            lux = light.read_lux()
            soil_pct = soil.moisture_percent()

            temp = d.get("temperature_c") if isinstance(d, dict) else None
            hum = d.get("humidity") if isinstance(d, dict) else None

            logger.log(temperature_c=temp, humidity=hum, lux=lux, soil_percent=soil_pct)

            # simple control logic examples
            if temp is not None and temp < 18.0:
                heater.on()
            else:
                heater.off()

            if lux is not None and lux < 200.0:
                grow_light.on()
            else:
                grow_light.off()

            if hum is not None and hum > 80:
                fan.set_speed(100)
            elif hum is not None and hum > 60:
                fan.set_speed(50)
            else:
                fan.set_speed(0)

            time.sleep(10)
    except KeyboardInterrupt:
        print("Shutting down, cleaning up GPIO")
    finally:
        grow_light.cleanup()
        heater.cleanup()
        fan.cleanup()


if __name__ == "__main__":
    main()