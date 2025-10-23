"""Advanced spectral light sensor support for color spectrum measurement.

This module extends the basic light sensors to include color/spectral measurement
capabilities for comprehensive light characterization during calibration.
"""
import time
from typing import Dict, List, Optional, Tuple

# Spectral sensor implementations (per-sensor availability flags)
try:
    import board
    import busio
    _HAS_I2C = True
except ImportError:
    _HAS_I2C = False

try:
    import adafruit_as7341  # 11-channel spectral sensor
    _HAS_AS7341 = True
except ImportError:
    _HAS_AS7341 = False

try:
    import adafruit_tcs34725  # RGB color sensor
    _HAS_TCS34725 = True
except ImportError:
    _HAS_TCS34725 = False

try:
    import adafruit_as726x   # AS7265x/AS7262/AS7263 spectral sensors
    _HAS_AS726X = True
except ImportError:
    _HAS_AS726X = False

try:
    from smbus2 import SMBus
    _HAS_SMBUS = True
except ImportError:
    _HAS_SMBUS = False


class AS7341Spectral:
    """AS7341 11-channel spectral sensor for detailed spectrum analysis."""
    
    DEFAULT_ADDR = 0x39
    
    # Channel wavelength centers (nm)
    CHANNELS = {
        'violet': 415,
        'indigo': 445, 
        'blue': 480,
        'cyan': 515,
        'green': 555,
        'yellow': 590,
        'orange': 630,
        'red': 680,
        'nir_1': 730,
        'nir_2': 850,
        'clear': None  # broadband
    }
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr
        self.sensor = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the AS7341 sensor."""
        if not (_HAS_I2C and _HAS_AS7341):
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_as7341.AS7341(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize AS7341: {e}")
            self.sensor = None
    
    def read_spectrum(self) -> Optional[Dict[str, float]]:
        """Read full spectral data from all channels."""
        if not self.sensor:
            return None
        
        try:
            # Read all channels
            readings = {}
            
            # Channel 1-6 (F1-F6)
            channel_data = self.sensor.channel_415nm  # F1 - violet
            readings['violet'] = channel_data
            
            readings['indigo'] = self.sensor.channel_445nm   # F2
            readings['blue'] = self.sensor.channel_480nm     # F3
            readings['cyan'] = self.sensor.channel_515nm     # F4
            readings['green'] = self.sensor.channel_555nm    # F5
            readings['yellow'] = self.sensor.channel_590nm   # F6
            
            # Channel 7-8 (F7-F8) 
            readings['orange'] = self.sensor.channel_630nm   # F7
            readings['red'] = self.sensor.channel_680nm      # F8
            
            # NIR channels
            readings['nir_1'] = self.sensor.channel_730nm    # NIR
            readings['nir_2'] = self.sensor.channel_850nm    # NIR
            
            # Clear channel (broadband)
            readings['clear'] = self.sensor.channel_clear
            
            return readings
            
        except Exception as e:
            print(f"Error reading AS7341: {e}")
            return None
    
    def calculate_color_ratios(self, spectrum: Dict[str, float]) -> Dict[str, float]:
        """Calculate color percentage ratios from spectrum data."""
        if not spectrum:
            return {}
        
        # Group channels into color categories
        blue_channels = ['violet', 'indigo', 'blue']
        green_channels = ['cyan', 'green']
        red_channels = ['yellow', 'orange', 'red']
        
        blue_total = sum(spectrum.get(ch, 0) for ch in blue_channels)
        green_total = sum(spectrum.get(ch, 0) for ch in green_channels)
        red_total = sum(spectrum.get(ch, 0) for ch in red_channels)
        
        total_visible = blue_total + green_total + red_total
        
        if total_visible == 0:
            return {'blue_percent': 0, 'green_percent': 0, 'red_percent': 0}
        
        return {
            'blue_percent': (blue_total / total_visible) * 100,
            'green_percent': (green_total / total_visible) * 100,
            'red_percent': (red_total / total_visible) * 100
        }
    
    def calculate_par_weight(self, spectrum: Dict[str, float]) -> float:
        """Calculate PAR-weighted light intensity."""
        if not spectrum:
            return 0.0
        
        # PAR weighting factors for plant photosynthesis (simplified)
        par_weights = {
            'violet': 0.1,   # 400-450nm - some effect
            'indigo': 0.3,   # 450-500nm - blue light response
            'blue': 0.8,     # 480-520nm - peak blue response
            'cyan': 0.9,     # 500-550nm - good for photosynthesis
            'green': 0.7,    # 520-600nm - moderate effectiveness
            'yellow': 0.9,   # 580-620nm - good red light start
            'orange': 1.0,   # 620-680nm - peak red response
            'red': 1.0,      # 660-700nm - peak red response
            'nir_1': 0.2,    # 700-800nm - far red effects
            'nir_2': 0.0     # >800nm - minimal photosynthetic effect
        }
        
        par_total = 0
        for channel, intensity in spectrum.items():
            weight = par_weights.get(channel, 0)
            par_total += intensity * weight
        
        return par_total


class AS7265xSpectral:
    """AS7265x 18-channel spectral sensor for comprehensive spectrum analysis.
    
    Combines three sensors (AS72651, AS72652, AS72653) for full UV-VIS-NIR coverage:
    - AS72651: 410, 435, 460, 485, 510, 535nm (UV-Blue-Green)
    - AS72652: 560, 585, 645, 705, 730, 760nm (Green-Red-NIR)  
    - AS72653: 810, 860, 900, 940nm + Clear, NIR (Extended NIR)
    """
    
    DEFAULT_ADDR = 0x49
    
    # Channel wavelength centers (nm) - all 18 channels
    CHANNELS = {
        # AS72651 - UV/Violet/Blue/Green
        'uv_410': 410,
        'violet_435': 435,
        'blue_460': 460,
        'blue_485': 485,
        'cyan_510': 510,
        'green_535': 535,
        # AS72652 - Green/Yellow/Orange/Red/NIR
        'green_560': 560,
        'yellow_585': 585,
        'red_645': 645,
        'red_705': 705,
        'nir_730': 730,
        'nir_760': 760,
        # AS72653 - Extended NIR
        'nir_810': 810,
        'nir_860': 860,
        'nir_900': 900,
        'nir_940': 940,
        'clear': None,   # broadband visible
        'nir_broad': None  # broadband NIR
    }
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR):
        self.bus_num = bus
        self.addr = addr
        self.sensor = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the AS7265x sensor."""
        if not (_HAS_I2C and _HAS_TCS34725):
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = adafruit_as726x.AS726x_I2C(i2c, address=self.addr)
        except Exception as e:
            print(f"Failed to initialize AS7265x: {e}")
            self.sensor = None
    
    def read_spectrum(self) -> Optional[Dict[str, float]]:
        """Read full 18-channel spectral data."""
        if not self.sensor:
            return None
        
        try:
            # Read all channels from the three sensors
            readings = {}
            
            # AS72651 channels (410-535nm)
            readings['uv_410'] = self.sensor.channel_410nm
            readings['violet_435'] = self.sensor.channel_435nm
            readings['blue_460'] = self.sensor.channel_460nm
            readings['blue_485'] = self.sensor.channel_485nm
            readings['cyan_510'] = self.sensor.channel_510nm
            readings['green_535'] = self.sensor.channel_535nm
            
            # AS72652 channels (560-760nm)
            readings['green_560'] = self.sensor.channel_560nm
            readings['yellow_585'] = self.sensor.channel_585nm
            readings['red_645'] = self.sensor.channel_645nm
            readings['red_705'] = self.sensor.channel_705nm
            readings['nir_730'] = self.sensor.channel_730nm
            readings['nir_760'] = self.sensor.channel_760nm
            
            # AS72653 channels (810-940nm + broadband)
            readings['nir_810'] = self.sensor.channel_810nm
            readings['nir_860'] = self.sensor.channel_860nm
            readings['nir_900'] = self.sensor.channel_900nm
            readings['nir_940'] = self.sensor.channel_940nm
            readings['clear'] = self.sensor.channel_clear
            readings['nir_broad'] = self.sensor.channel_nir
            
            return readings
            
        except Exception as e:
            print(f"Error reading AS7265x: {e}")
            return None
    
    def calculate_color_ratios(self, spectrum: Dict[str, float]) -> Dict[str, float]:
        """Calculate detailed color percentage ratios from 18-channel data."""
        if not spectrum:
            return {}
        
        # Group channels into detailed color categories
        uv_channels = ['uv_410']
        violet_channels = ['violet_435']
        blue_channels = ['blue_460', 'blue_485']
        cyan_channels = ['cyan_510']
        green_channels = ['green_535', 'green_560']
        yellow_channels = ['yellow_585']
        red_channels = ['red_645', 'red_705']
        nir_channels = ['nir_730', 'nir_760', 'nir_810', 'nir_860', 'nir_900', 'nir_940']
        
        # Calculate totals for each color group
        totals = {}
        for name, channels in [
            ('uv', uv_channels), ('violet', violet_channels), ('blue', blue_channels),
            ('cyan', cyan_channels), ('green', green_channels), ('yellow', yellow_channels),
            ('red', red_channels), ('nir', nir_channels)
        ]:
            totals[f'{name}_total'] = sum(spectrum.get(ch, 0) for ch in channels)
        
        # Calculate visible light total (exclude NIR and UV for photosynthesis calc)
        visible_total = sum(totals[k] for k in totals.keys() if k not in ['uv_total', 'nir_total'])
        
        if visible_total == 0:
            return {f'{name}_percent': 0 for name in ['uv', 'violet', 'blue', 'cyan', 'green', 'yellow', 'red', 'nir']}
        
        # Calculate percentages
        percentages = {}
        for name in ['uv', 'violet', 'blue', 'cyan', 'green', 'yellow', 'red', 'nir']:
            total_key = f'{name}_total'
            if name in ['uv', 'nir']:
                # UV and NIR as percentage of total spectrum
                all_total = sum(totals.values())
                percentages[f'{name}_percent'] = (totals[total_key] / all_total * 100) if all_total > 0 else 0
            else:
                # Visible colors as percentage of visible spectrum
                percentages[f'{name}_percent'] = (totals[total_key] / visible_total * 100) if visible_total > 0 else 0
        
        return percentages
    
    def calculate_par_weight(self, spectrum: Dict[str, float]) -> float:
        """Calculate detailed PAR-weighted light intensity using 18-channel data."""
        if not spectrum:
            return 0.0
        
        # Detailed PAR weighting factors based on photosynthetic action spectrum
        par_weights = {
            'uv_410': 0.05,      # UV-A has minimal but measurable effect
            'violet_435': 0.15,   # Violet light, some photosynthetic response
            'blue_460': 0.85,    # Blue peak for chlorophyll b
            'blue_485': 0.80,    # Blue-cyan transition
            'cyan_510': 0.75,    # Cyan, good photosynthetic efficiency
            'green_535': 0.70,   # Green, moderate but useful
            'green_560': 0.65,   # Green peak, lower absorption
            'yellow_585': 0.80,  # Yellow-orange, increasing efficiency
            'red_645': 1.00,     # Red peak for chlorophyll a
            'red_705': 0.95,     # Deep red, excellent for photosynthesis
            'nir_730': 0.20,     # Far-red, morphological effects
            'nir_760': 0.15,     # Far-red, shade avoidance
            'nir_810': 0.10,     # Near-infrared, minimal photosynthetic effect
            'nir_860': 0.05,     # Extended NIR
            'nir_900': 0.02,     # Extended NIR
            'nir_940': 0.01,     # Extended NIR, mostly heat
            'clear': 0.0,        # Don't double-count broadband
            'nir_broad': 0.0     # Don't double-count broadband NIR
        }
        
        par_total = 0
        for channel, intensity in spectrum.items():
            if intensity is not None:
                weight = par_weights.get(channel, 0)
                par_total += intensity * weight
        
        return par_total
    
    def calculate_light_quality_metrics(self, spectrum: Dict[str, float]) -> Dict[str, float]:
        """Calculate advanced light quality metrics for plant growth."""
        if not spectrum:
            return {}
        
        # Calculate key ratios important for plant physiology
        blue_total = sum(spectrum.get(ch, 0) for ch in ['blue_460', 'blue_485'])
        red_total = sum(spectrum.get(ch, 0) for ch in ['red_645', 'red_705'])
        far_red_total = sum(spectrum.get(ch, 0) for ch in ['nir_730', 'nir_760'])
        green_total = sum(spectrum.get(ch, 0) for ch in ['green_535', 'green_560'])
        
        metrics = {}
        
        # Red:Blue ratio (important for plant morphology)
        if blue_total > 0:
            metrics['red_blue_ratio'] = red_total / blue_total
        else:
            metrics['red_blue_ratio'] = 0
        
        # Red:Far-Red ratio (critical for shade avoidance response)
        if far_red_total > 0:
            metrics['red_far_red_ratio'] = red_total / far_red_total
        else:
            metrics['red_far_red_ratio'] = float('inf') if red_total > 0 else 0
        
        # Blue:Green ratio (affects photomorphogenesis)
        if green_total > 0:
            metrics['blue_green_ratio'] = blue_total / green_total
        else:
            metrics['blue_green_ratio'] = float('inf') if blue_total > 0 else 0
        
        # Photosynthetic Photon Flux Density estimate
        metrics['ppfd_estimate'] = self.calculate_par_weight(spectrum)
        
        # Light quality classification
        if metrics['red_blue_ratio'] > 2.0:
            metrics['light_type'] = 'warm_flowering'
        elif metrics['red_blue_ratio'] < 0.5:
            metrics['light_type'] = 'cool_vegetative'
        else:
            metrics['light_type'] = 'balanced_fullspectrum'
        
        return metrics


class TCS34725Color:
    def approximate_ppfd(self, color_data: Dict[str, float]) -> float:
        """Advanced PPFD approximation using RGB spectral analysis and lux.
        
        This method uses the RGB ratios to estimate spectral distribution and applies
        photosynthetic action spectrum weighting for more accurate PAR estimation.
        
        Photosynthetic efficiency by wavelength region (relative):
        - Blue (400-500nm): 0.85 efficiency (chlorophyll b absorption peak)
        - Green (500-600nm): 0.70 efficiency (lower absorption, but still useful)
        - Red (600-700nm): 1.00 efficiency (chlorophyll a absorption peak)
        
        The TCS34725 RGB channels roughly correspond to:
        - Blue channel: ~465nm peak (includes violet-blue)
        - Green channel: ~525nm peak 
        - Red channel: ~615nm peak (includes red-orange)
        """
        lux = color_data.get('lux', 0)
        if lux == 0:
            return 0.0
            
        # Get raw RGB values
        r_raw = color_data.get('red_raw', 0)
        g_raw = color_data.get('green_raw', 0) 
        b_raw = color_data.get('blue_raw', 0)
        
        # Calculate total and avoid division by zero
        total_rgb = r_raw + g_raw + b_raw
        if total_rgb == 0:
            # Fallback to basic color temperature method
            color_temp = color_data.get('color_temperature_k', 5000)
            base_factor = 0.0185 if color_temp > 4000 else 0.0165
            return lux * base_factor
            
        # Calculate RGB percentages
        r_pct = r_raw / total_rgb
        g_pct = g_raw / total_rgb
        b_pct = b_raw / total_rgb
        
        # Photosynthetic efficiency weights for each color channel
        # Based on photosynthetic action spectrum and typical LED spectral distributions
        red_efficiency = 1.00    # Peak efficiency (660-680nm region)
        green_efficiency = 0.70  # Lower but non-zero (green light penetrates deeper)
        blue_efficiency = 0.85   # High efficiency (430-450nm chlorophyll peaks)
        
        # Calculate weighted photosynthetic efficiency
        spectral_efficiency = (r_pct * red_efficiency + 
                             g_pct * green_efficiency + 
                             b_pct * blue_efficiency)
        
        # Base conversion factor (typical for white LEDs)
        base_conversion = 0.0185
        
        # Adjust conversion factor based on spectral content
        # More red/blue content = higher PPFD per lux
        # More green content = lower PPFD per lux
        efficiency_factor = spectral_efficiency / 0.85  # Normalize to typical white LED
        
        # Apply color temperature fine-tuning
        color_temp = color_data.get('color_temperature_k', 5000)
        if color_temp < 3000:
            # Very warm - boost red efficiency slightly
            temp_adjustment = 1.02
        elif color_temp > 6000:
            # Very cool - blue content may be excessive
            temp_adjustment = 0.98
        else:
            temp_adjustment = 1.0
            
        final_conversion = base_conversion * efficiency_factor * temp_adjustment
        
        # Wider bounds to accommodate varied light sources (0.008 to 0.035 μmol/m²/s per lux)
        # Note: Typical ranges:
        # - HPS: ~0.008-0.012
        # - Metal Halide: ~0.012-0.015
        # - White LED: ~0.014-0.018
        # - Full Spectrum LED: ~0.016-0.020
        # - Sunlight: ~0.018-0.022
        # - Blurple LED: ~0.020-0.035
        final_conversion = max(0.008, min(0.035, final_conversion))
        
        return lux * final_conversion
    """TCS34725 RGB color sensor for ambient light analysis.
    
    IMPORTANT: For accurate ambient light readings, ensure the onboard LED
    is disabled by jumpering the LED pin to GND on the breakout board.
    """
    
    DEFAULT_ADDR = 0x29
    
    def __init__(self, bus=1, addr=DEFAULT_ADDR, mux_address=None, mux_channel=None):
        self.bus_num = bus
        self.addr = addr
        self.mux_address = mux_address
        self.mux_channel = mux_channel
        self.sensor = None
        # Track last used settings for adaptive adjustment
        self._last_integration_idx = 5  # default to 240ms (index 5)
        self._last_gain_idx = 2         # default to 16x (index 2)
        self._integration_times = [2.4, 24, 50, 101, 154, 240]  # ms
        self._gains = [1, 4, 16, 60]
        self._initialize()
    
    def _verify_i2c_device(self, bus_num, addr):
        """Verify if an I2C device responds at the given address."""
        try:
            from smbus2 import SMBus
            with SMBus(bus_num) as bus:
                bus.read_byte(addr)
                return True
        except Exception as e:
            print(f"[TCS34725] Device verification failed at address 0x{addr:02x}: {e}")
            return False

    def _initialize(self):
        """Initialize the TCS34725 sensor with optimal ambient light settings."""
        if not (_HAS_I2C and _HAS_TCS34725):
            print("[TCS34725] Missing dependencies: I2C=", _HAS_I2C, "TCS34725=", _HAS_TCS34725)
            return
        try:
            print("[TCS34725] Starting initialization...")
            print(f"[TCS34725] Bus: {self.bus_num}, Address: {self.addr}, Mux: {self.mux_address}, Channel: {self.mux_channel}")

            # First verify multiplexer is present if configured
            if self.mux_address is not None:
                print(f"[TCS34725] Verifying multiplexer at 0x{self.mux_address:02x}")
                if not self._verify_i2c_device(self.bus_num, self.mux_address):
                    raise Exception(f"Multiplexer not found at address 0x{self.mux_address:02x}")

            # Select mux channel if configured
            if self.mux_address is not None and self.mux_channel is not None:
                from sensors.pca9548a import PCA9548A
                import time
                print(f"[TCS34725] Setting up multiplexer at address 0x{self.mux_address:02x} channel {self.mux_channel}")
                mux = PCA9548A(bus=self.bus_num, address=self.mux_address)
                
                # First clear all channels
                mux.select_channel(0)
                time.sleep(0.05)
                
                # Now select our channel
                mux.select_channel(self.mux_channel)
                time.sleep(0.05)  # Give the mux time to switch
                print("[TCS34725] Multiplexer channel selected")
                
                # Verify sensor is accessible through mux
                print(f"[TCS34725] Verifying sensor presence at 0x{self.addr:02x} through mux")
                if not self._verify_i2c_device(self.bus_num, self.addr):
                    raise Exception(f"TCS34725 not found at address 0x{self.addr:02x} after mux channel select")
            
            print("[TCS34725] Setting up I2C bus...")
            i2c = busio.I2C(board.SCL, board.SDA)
            print(f"[TCS34725] Creating TCS34725 instance at address 0x{self.addr:02x}")
            self.sensor = adafruit_tcs34725.TCS34725(i2c, address=self.addr)
            
            # Configure for optimal ambient light measurement
            print("[TCS34725] Configuring sensor parameters...")
            # Start with lower settings to avoid saturation
            self.sensor.integration_time = 50   # Start with shorter integration time
            self.sensor.gain = 4               # Start with lower gain
            time.sleep(0.1)
            
            # Test read to verify communication
            print("[TCS34725] Testing sensor communication...")
            test_r, test_g, test_b, test_c = self.sensor.color_raw
            print(f"[TCS34725] Test read successful: r={test_r}, g={test_g}, b={test_b}, c={test_c}")
            
            # Now set final settings
            print("[TCS34725] Setting final parameters...")
            self.sensor.integration_time = 240  # 240ms for better accuracy
            self.sensor.gain = 16              # Higher gain for low light sensitivity
            self.sensor.interrupt = False      # Clear any interrupt flags
            
            print(f"[TCS34725] Successfully initialized: integration_time={self.sensor.integration_time}ms, gain={self.sensor.gain}x")
            
        except Exception as e:
            print(f"[TCS34725] Failed to initialize: {e}")
            import traceback
            print("[TCS34725] Stack trace:")
            traceback.print_exc()
            self.sensor = None
    
    def read_color(self) -> Optional[Dict[str, float]]:
        """Read RGB color data with adaptive gain/integration: only step up/down if needed."""
        if not self.sensor:
            print("[TCS34725] No sensor instance available - was initialization successful?")
            return None
        try:
            print("[TCS34725] Starting color read...")
            import time
            max_clear = 65535
            # Target to keep under ~80% of full scale to avoid clipping and allow headroom
            target_ratio = 0.80
            high_trigger = int(max_clear * 0.82)  # step-down trigger (hysteresis above target)
            high_release = int(max_clear * 0.78)  # release threshold to avoid chattering
            # Low end thresholds (keep existing conservative low signal floor)
            min_clear = 5000
            min_clear_up = 6000    # step-up trigger with small hysteresis
            # Use last settings
            it_idx = self._last_integration_idx
            gain_idx = self._last_gain_idx
            integration_times = self._integration_times
            gains = self._gains
            
            print(f"[TCS34725] Using settings: integration_time={integration_times[it_idx]}ms, gain={gains[gain_idx]}x")
            
            # Apply current (last used) settings for this measurement
            try:
                self.sensor.integration_time = integration_times[it_idx]
                self.sensor.gain = gains[gain_idx]
            except Exception as e:
                print(f"[TCS34725] Error setting sensor parameters: {e}")
                raise
                
            time.sleep(0.15)

            # Read values under current settings BEFORE making any adjustments
            print("[TCS34725] Reading raw color values...")
            try:
                r, g, b, c = self.sensor.color_raw
                print(f"[TCS34725] Raw color values read: r={r}, g={g}, b={b}, c={c}")
            except Exception as e:
                print(f"[TCS34725] Error reading raw color values: {e}")
                raise
                
            # Also compute lux and color temperature using current settings
            print("[TCS34725] Reading lux and color temperature...")
            try:
                color_temp = self.sensor.color_temperature
                lux = self.sensor.lux
                print(f"[TCS34725] Lux and color temp read: lux={lux}, color_temp={color_temp}")
            except Exception as e:
                print(f"[TCS34725] Error reading lux/color temp: {e}")
                raise
                
            # Defensive handling: DN40 returns None when saturated or invalid
            if lux is None:
                # Treat as saturation/invalid; report 0.0 lux to downstream
                print("[TCS34725][WARN] Lux is None (likely saturation); setting lux to 0.0")
                lux = 0.0
            elif lux < 0:
                print(f"[TCS34725][WARN] Negative lux computed ({lux}); clamping to 0.0")
                lux = 0.0
            print(f"[TCS34725] Final values: r={r}, g={g}, b={b}, c={c}, lux={lux}, color_temp={color_temp}")

            # Decide adjustments for NEXT measurement
            adjusted = False
            new_it_idx = it_idx
            new_gain_idx = gain_idx
            # Step logic with hysteresis: if near clip, reduce; if too low, increase
            if c >= high_trigger:
                # Too high, step down gain first, then integration
                changed = False
                if new_gain_idx > 0:
                    new_gain_idx -= 1
                    changed = True
                    print(f"[TCS34725] High signal ({c} >= {high_trigger}): scheduling decrease gain to {gains[new_gain_idx]}x")
                elif new_it_idx > 0:
                    new_it_idx -= 1
                    changed = True
                    print(f"[TCS34725] High signal: scheduling decrease integration_time to {integration_times[new_it_idx]}ms")
                else:
                    # Already at minimum settings, cannot adjust further
                    print("[TCS34725] High signal but already at minimum gain/time; holding settings")
                adjusted = changed
            elif c < min_clear_up:
                # Too low, step up integration time first, then gain
                changed = False
                if new_it_idx < len(integration_times) - 1:
                    new_it_idx += 1
                    changed = True
                    print(f"[TCS34725] Low signal ({c} < {min_clear_up}): scheduling increase integration_time to {integration_times[new_it_idx]}ms")
                elif new_gain_idx < len(gains) - 1:
                    new_gain_idx += 1
                    changed = True
                    print(f"[TCS34725] Low signal: scheduling increase gain to {gains[new_gain_idx]}x")
                else:
                    # Already at maximum settings, cannot adjust further
                    print("[TCS34725] Low signal but already at maximum gain/time; holding settings")
                adjusted = changed

            # Apply any scheduled changes AFTER completing the current read,
            # so that returned values reflect the original settings.
            if adjusted:
                self._last_integration_idx = new_it_idx
                self._last_gain_idx = new_gain_idx
                # Reinitialize sensor to force new settings to take effect immediately
                print(f"[TCS34725] Adjustment scheduled for next read: integration_time={integration_times[new_it_idx]}ms, gain={gains[new_gain_idx]}x. Reinitializing sensor for fast stabilization.")
                self._initialize()
                # After reinitialization, settings are already applied in _initialize()
            else:
                # Keep last indices unchanged
                self._last_integration_idx = it_idx
                self._last_gain_idx = gain_idx

            color_data = {
                'red_raw': r,
                'green_raw': g,
                'blue_raw': b,
                'clear_raw': c,
                'color_temperature_k': color_temp,
                'lux': lux,
                # Report the settings used for this reading (pre-adjustment)
                'integration_time_ms': integration_times[it_idx],
                'gain': gains[gain_idx]
            }
            # Add PPFD approximation
            color_data['ppfd_approx'] = self.approximate_ppfd(color_data)
            return color_data
        except Exception as e:
            print(f"Error reading TCS34725: {e}")
            return None
    
    def calculate_rgb_ratios(self, color_data: Dict[str, float]) -> Dict[str, float]:
        """Calculate RGB percentage ratios."""
        if not color_data:
            return {}
        
        r = color_data.get('red_raw', 0)
        g = color_data.get('green_raw', 0)
        b = color_data.get('blue_raw', 0)
        
        total_rgb = r + g + b
        
        if total_rgb == 0:
            return {'red_percent': 0, 'green_percent': 0, 'blue_percent': 0}
        
        return {
            'red_percent': (r / total_rgb) * 100,
            'green_percent': (g / total_rgb) * 100,
            'blue_percent': (b / total_rgb) * 100
        }


class SpectralSensorReader:
    """Enhanced sensor reader that includes spectral measurement capabilities."""
    
    def __init__(self, sensors_config: Dict):
        self.sensors_config = sensors_config
        self.spectral_sensors = {}
        self.basic_sensors = {}
        
        self._initialize_sensors()
    
    def _initialize_sensors(self):
        """Initialize both basic and spectral sensors."""
        for sensor_id, config in self.sensors_config.items():
            sensor_type = config.get('type', '').upper()
            connection = config.get('connection', {})
            
            try:
                if sensor_type == 'AS7341':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', AS7341Spectral.DEFAULT_ADDR)
                    self.spectral_sensors[sensor_id] = {
                        'instance': AS7341Spectral(bus=bus, addr=addr),
                        'config': config,
                        'type': 'spectral'
                    }
                elif sensor_type == 'AS7265X':
                    bus = connection.get('bus', 1)
                    addr = connection.get('address', AS7265xSpectral.DEFAULT_ADDR)
                    self.spectral_sensors[sensor_id] = {
                        'instance': AS7265xSpectral(bus=bus, addr=addr),
                        'config': config,
                        'type': 'spectral_18ch'
                    }
                elif sensor_type == 'TCS34725':
                    bus = connection.get('bus', 1) 
                    addr = connection.get('address', TCS34725Color.DEFAULT_ADDR)
                    mux_addr = connection.get('mux_address')
                    mux_ch = connection.get('mux_channel')
                    self.spectral_sensors[sensor_id] = {
                        'instance': TCS34725Color(bus=bus, addr=addr, mux_address=mux_addr, mux_channel=mux_ch),
                        'config': config,
                        'type': 'color'
                    }
                else:
                    # Fall back to basic sensors (BH1750, etc.)
                    from control.light_calibration import SensorReader
                    basic_reader = SensorReader({sensor_id: config})
                    if basic_reader.sensors:
                        self.basic_sensors[sensor_id] = basic_reader.sensors[sensor_id]
                        
            except Exception as e:
                print(f"Failed to initialize sensor {sensor_id}: {e}")
    
    def read_sensors(self) -> Dict[str, Dict]:
        """Read raw data directly from sensors without processing."""
        results = {}
        
        # Read spectral sensors - return raw driver data
        for sensor_id, sensor_data in self.spectral_sensors.items():
            sensor = sensor_data['instance']
            sensor_type = sensor_data['type']
            
            try:
                if sensor_type == 'spectral' and isinstance(sensor, AS7341Spectral):
                    # Return raw spectrum from AS7341 driver
                    spectrum = sensor.read_spectrum()
                    if spectrum:
                        results[sensor_id] = {
                            'type': 'spectral',
                            'raw_data': spectrum  # Just the raw spectrum data
                        }
                
                elif sensor_type == 'spectral_18ch' and isinstance(sensor, AS7265xSpectral):
                    # Return raw spectrum from AS7265X driver
                    spectrum = sensor.read_spectrum()
                    if spectrum:
                        results[sensor_id] = {
                            'type': 'spectral_18ch',
                            'raw_data': spectrum  # Just the raw 18-channel data
                        }
                
                elif sensor_type == 'color' and isinstance(sensor, TCS34725Color):
                    # Return raw color data from TCS34725 driver
                    color_data = sensor.read_color()
                    if color_data:
                        results[sensor_id] = {
                            'type': 'color',
                            'raw_data': color_data  # Just the raw color data
                        }
                        
            except Exception as e:
                print(f"Error reading spectral sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        # Read basic sensors
        for sensor_id, sensor_data in self.basic_sensors.items():
            try:
                sensor = sensor_data['instance']
                if hasattr(sensor, 'read_lux'):
                    lux = sensor.read_lux()
                    results[sensor_id] = {
                        'type': 'basic',
                        'raw_data': {'lux': lux}  # Basic sensor just returns lux
                    }
            except Exception as e:
                print(f"Error reading basic sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        return results

    def read_comprehensive_data(self) -> Dict[str, Dict]:
        """Read both intensity and spectral data from all sensors."""
        results = {}
        
        # Read spectral sensors
        for sensor_id, sensor_data in self.spectral_sensors.items():
            sensor = sensor_data['instance']
            sensor_type = sensor_data['type']
            
            try:
                if sensor_type == 'spectral' and isinstance(sensor, AS7341Spectral):
                    spectrum = sensor.read_spectrum()
                    if spectrum:
                        color_ratios = sensor.calculate_color_ratios(spectrum)
                        par_weight = sensor.calculate_par_weight(spectrum)
                        
                        results[sensor_id] = {
                            'type': 'spectral',
                            'spectrum': spectrum,
                            'color_ratios': color_ratios,
                            'par_weighted_intensity': par_weight,
                            'total_intensity': spectrum.get('clear', 0)
                        }
                
                elif sensor_type == 'spectral_18ch' and isinstance(sensor, AS7265xSpectral):
                    spectrum = sensor.read_spectrum()
                    if spectrum:
                        color_ratios = sensor.calculate_color_ratios(spectrum)
                        par_weight = sensor.calculate_par_weight(spectrum)
                        light_quality = sensor.calculate_light_quality_metrics(spectrum)
                        
                        results[sensor_id] = {
                            'type': 'spectral_18ch',
                            'spectrum': spectrum,
                            'color_ratios': color_ratios,
                            'par_weighted_intensity': par_weight,
                            'light_quality_metrics': light_quality,
                            'total_intensity': spectrum.get('clear', 0)
                        }
                
                elif sensor_type == 'color' and isinstance(sensor, TCS34725Color):
                    color_data = sensor.read_color()
                    if color_data:
                        rgb_ratios = sensor.calculate_rgb_ratios(color_data)
                        results[sensor_id] = {
                            'type': 'color',
                            'color_data': color_data,
                            'rgb_ratios': rgb_ratios,
                            'lux': color_data.get('lux', 0),
                            'color_temperature': color_data.get('color_temperature_k', 0),
                            'ppfd_approx': color_data.get('ppfd_approx', 0)
                        }
                        
            except Exception as e:
                print(f"Error reading spectral sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        # Read basic sensors
        for sensor_id, sensor_data in self.basic_sensors.items():
            try:
                sensor = sensor_data['instance']
                if hasattr(sensor, 'read_lux'):
                    lux = sensor.read_lux()
                    results[sensor_id] = {
                        'type': 'basic',
                        'lux': lux
                    }
            except Exception as e:
                print(f"Error reading basic sensor {sensor_id}: {e}")
                results[sensor_id] = {'type': 'error', 'error': str(e)}
        
        return results
    
    def analyze_light_spectrum(self, light_id: str, 
                             baseline_data: Dict, 
                             light_on_data: Dict) -> Dict:
        """Analyze the spectral characteristics of a specific light."""
        analysis = {
            'light_id': light_id,
            'spectral_signature': {},
            'color_analysis': {},
            'par_effectiveness': {}
        }
        
        for sensor_id in baseline_data.keys():
            if sensor_id in light_on_data:
                baseline = baseline_data[sensor_id]
                light_on = light_on_data[sensor_id]
                
                sensor_analysis = {
                    'sensor_id': sensor_id,
                    'intensity_change': 0,
                    'lux_change': 0,
                    'ppfd_change': 0,
                    'spectral_change': None,
                    'color_shift': None
                }
                
                # Analyze based on sensor type
                if baseline.get('type') == 'spectral' and light_on.get('type') == 'spectral':
                    # Calculate spectral differences
                    baseline_spectrum = baseline.get('spectrum', {})
                    light_spectrum = light_on.get('spectrum', {})
                    
                    spectral_diff = {}
                    for channel in baseline_spectrum.keys():
                        baseline_val = baseline_spectrum.get(channel, 0)
                        light_val = light_spectrum.get(channel, 0)
                        spectral_diff[channel] = light_val - baseline_val
                    
                    sensor_analysis['spectral_change'] = spectral_diff
                    
                    # Color ratio changes
                    baseline_colors = baseline.get('color_ratios', {})
                    light_colors = light_on.get('color_ratios', {})
                    
                    color_shift = {}
                    for color in baseline_colors.keys():
                        baseline_pct = baseline_colors.get(color, 0)
                        light_pct = light_colors.get(color, 0)
                        color_shift[color] = light_pct - baseline_pct
                    
                    sensor_analysis['color_shift'] = color_shift
                    
                    # PAR effectiveness
                    baseline_par = baseline.get('par_weighted_intensity', 0)
                    light_par = light_on.get('par_weighted_intensity', 0)
                    sensor_analysis['par_increase'] = light_par - baseline_par
                
                elif baseline.get('type') == 'color' and light_on.get('type') == 'color':
                    # RGB analysis
                    baseline_rgb = baseline.get('rgb_ratios', {})
                    light_rgb = light_on.get('rgb_ratios', {})
                    
                    rgb_shift = {}
                    for color in baseline_rgb.keys():
                        baseline_pct = baseline_rgb.get(color, 0)
                        light_pct = light_rgb.get(color, 0)
                        rgb_shift[color] = light_pct - baseline_pct
                    
                    sensor_analysis['color_shift'] = rgb_shift
                    
                    # Color temperature change
                    baseline_temp = baseline.get('color_data', {}).get('color_temperature_k', 0)
                    light_temp = light_on.get('color_data', {}).get('color_temperature_k', 0)
                    sensor_analysis['color_temp_change'] = light_temp - baseline_temp
                
                # Basic intensity change for all sensor types
                baseline_lux = baseline.get('lux', 0)
                light_lux = light_on.get('lux', 0)
                sensor_analysis['lux_change'] = light_lux - baseline_lux

                # For TCS34725, use ppfd_approx if available
                if 'ppfd_approx' in baseline and 'ppfd_approx' in light_on:
                    baseline_ppfd = baseline.get('ppfd_approx', 0)
                    light_ppfd = light_on.get('ppfd_approx', 0)
                    sensor_analysis['ppfd_change'] = light_ppfd - baseline_ppfd
                else:
                    baseline_par = baseline.get('par_weighted_intensity', 0)
                    light_par = light_on.get('par_weighted_intensity', 0)
                    sensor_analysis['ppfd_change'] = light_par - baseline_par

                baseline_intensity = (baseline_lux or baseline.get('total_intensity', 0) or baseline_par)
                light_intensity = (light_lux or light_on.get('total_intensity', 0) or light_par)
                sensor_analysis['intensity_change'] = light_intensity - baseline_intensity

                analysis['spectral_signature'][sensor_id] = sensor_analysis
        
        return analysis


# Mock implementations for testing without hardware
class MockAS7341:
    """Mock AS7341 for testing without hardware."""
    
    def __init__(self, bus=None, addr=None, **kwargs):
        """Initialize mock sensor (ignores hardware parameters)."""
        pass
    
    def read_spectrum(self):
        import random
        return {
            'violet': random.uniform(100, 500),
            'indigo': random.uniform(200, 800), 
            'blue': random.uniform(300, 1000),
            'cyan': random.uniform(400, 1200),
            'green': random.uniform(500, 1500),
            'yellow': random.uniform(300, 1000),
            'orange': random.uniform(200, 800),
            'red': random.uniform(400, 1200),
            'nir_1': random.uniform(100, 400),
            'nir_2': random.uniform(50, 200),
            'clear': random.uniform(2000, 8000)
        }
    
    def calculate_color_ratios(self, spectrum):
        if not spectrum:
            return {}
        blue = spectrum.get('blue', 0) + spectrum.get('indigo', 0)
        green = spectrum.get('green', 0) + spectrum.get('cyan', 0)
        red = spectrum.get('red', 0) + spectrum.get('orange', 0) + spectrum.get('yellow', 0)
        total = blue + green + red
        if total == 0:
            return {}
        return {
            'blue_percent': (blue/total) * 100,
            'green_percent': (green/total) * 100, 
            'red_percent': (red/total) * 100
        }
    
    def calculate_par_weight(self, spectrum):
        return sum(spectrum.values()) * 0.7  # Mock PAR calculation
    
    def read_color(self):
        """Mock read_color for TCS34725 compatibility."""
        import random
        return {
            'r': random.randint(50, 255),
            'g': random.randint(50, 255),
            'b': random.randint(50, 255),
            'c': random.randint(200, 1000),
            'lux': random.uniform(100, 1000),
            'color_temp': random.uniform(3000, 6500)
        }


# Use mocks if specific hardware modules are unavailable
if not _HAS_AS7341:
    AS7341Spectral = MockAS7341
if not _HAS_TCS34725:
    # Reuse MockAS7341 for TCS34725 compatibility (implements read_color)
    TCS34725Color = MockAS7341