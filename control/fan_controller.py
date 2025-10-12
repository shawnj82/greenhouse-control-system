"""Simple PWM-based fan controller using RPi.GPIO with fallback."""

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False


class FanController:
    def __init__(self, pin, freq=2500):
        self.pin = pin
        self.freq = freq
        self._pwm = None
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self._pwm = GPIO.PWM(self.pin, self.freq)
            self._pwm.start(0)

    def set_speed(self, percent):
        """Set speed 0-100."""
        pct = max(0, min(100, int(percent)))
        if not _HAS_GPIO:
            print(f"[MOCK] Fan {self.pin} speed set to {pct}%")
            return
        self._pwm.ChangeDutyCycle(pct)

    def stop(self):
        if not _HAS_GPIO:
            print(f"[MOCK] Fan {self.pin} stopped")
            return
        self._pwm.stop()

    def cleanup(self):
        if _HAS_GPIO:
            GPIO.cleanup(self.pin)