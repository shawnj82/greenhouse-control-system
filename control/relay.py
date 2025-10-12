"""Simple relay control using RPi.GPIO with fallback mock."""

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False


class Relay:
    def __init__(self, pin, active_high=True):
        self.pin = pin
        self.active_high = active_high
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self.off()

    def on(self):
        if not _HAS_GPIO:
            print(f"[MOCK] Relay {self.pin} ON")
            return
        GPIO.output(self.pin, GPIO.HIGH if self.active_high else GPIO.LOW)

    def off(self):
        if not _HAS_GPIO:
            print(f"[MOCK] Relay {self.pin} OFF")
            return
        GPIO.output(self.pin, GPIO.LOW if self.active_high else GPIO.HIGH)

    def cleanup(self):
        if _HAS_GPIO:
            GPIO.cleanup(self.pin)