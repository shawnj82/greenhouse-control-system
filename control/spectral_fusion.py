"""
Spectral data fusion utilities for combining measurements from different sensor types
to create unified spectrum estimates and spatial interpolations.
"""
import os
import math
from typing import Dict, List, Tuple, Optional
import numpy as np


class SpectralDataFusion:
    """Combines data from heterogeneous light sensors for spectrum estimation."""
    
    # Wavelength response maps for each sensor type
    SENSOR_WAVELENGTH_MAPS = {
        'TCS34725': {
            'red_raw': (620, 750),
            'green_raw': (500, 570),
            'blue_raw': (450, 520),
            'clear_raw': (400, 700)
        },
        'TSL2591': {
            'visible': (400, 700),
            'infrared': (700, 1100)
        },
        'AS7262': {
            # AS7262 6-channel visible spectral sensor (typical FWHM ≈ 40 nm)
            # Model each filter as a 40 nm rectangular band centered at nominal wavelength
            'violet': (430, 470),   # 450nm center, 40nm width
            'blue':   (480, 520),   # 500nm center, 40nm width
            'green':  (530, 570),   # 550nm center, 40nm width
            'yellow': (550, 590),   # 570nm center, 40nm width
            'orange': (580, 620),   # 600nm center, 40nm width
            'red':    (630, 670)    # 650nm center, 40nm width
        },
        'BH1750': {
            'broadband': (400, 700)
        }
    }
    
    @staticmethod
    def create_spectrum_bins(min_wavelength=280, max_wavelength=850, bin_width=20):
        """Create wavelength bins for spectrum reconstruction (default: 280-850nm, 20nm bins)."""
        bins = []
        wavelength = min_wavelength
        while wavelength < max_wavelength:
            bins.append((wavelength, wavelength + bin_width))
            wavelength += bin_width
        return bins
    
    @staticmethod
    def map_sensor_to_bins(sensor_type: str, sensor_data: Dict, spectrum_bins: List[Tuple[int, int]]) -> Dict[int, float]:
        """Map sensor channel data to spectrum bins.
        
        For sensors with gain/integration time settings (like TCS34725), this normalizes
        the raw counts to a standard baseline before mapping to bins. This ensures that
        values from different sensor settings are comparable.
        
        Normalization formula for TCS34725:
            normalized_count = raw_count / (gain × integration_time_ms)
        
        This gives counts per millisecond per unit gain, making values comparable.
        """
        if sensor_type not in SpectralDataFusion.SENSOR_WAVELENGTH_MAPS:
            return {}
        
        wavelength_map = SpectralDataFusion.SENSOR_WAVELENGTH_MAPS[sensor_type]
        bin_contributions = {i: 0.0 for i in range(len(spectrum_bins))}
        
        # Extract raw data based on sensor type
        if sensor_type == 'TCS34725':
            raw_data = sensor_data.get('raw_color_data', {})
            try:
                cfg_factor = sensor_data.get('lux_calibration') or sensor_data.get('calibration_factor')
            except Exception:
                cfg_factor = None
            if cfg_factor is None:
                try:
                    cfg_factor = float(os.getenv('TCS34725_LUX_CALIBRATION', '0.3545'))
                except Exception:
                    cfg_factor = 0.3545
            sensor_lux = float(raw_data.get('lux') or 0.0) * float(cfg_factor)
            rgb_channels = ['red_raw', 'green_raw', 'blue_raw', 'clear_raw']
            channel_ranges = {
                'red_raw':  (600, 700),
                'green_raw': (500, 580),
                'blue_raw':  (430, 490),
                'clear_raw': (400, 700)
            }
            channel_widths = {k: v[1] - v[0] for k, v in channel_ranges.items()}
            raw_sums = {k: max(0, float(raw_data.get(k, 0))) for k in rgb_channels}
            total_raw = sum(raw_sums.values())
            if sensor_lux > 0 and total_raw > 0:
                raw_data = {}
                # Distribute lux by channel ratio, then by channel width (lux/nm)
                for k in rgb_channels:
                    frac = raw_sums[k] / total_raw if total_raw > 0 else 0
                    width = channel_widths[k]
                    raw_data[k] = (sensor_lux * frac) / width if width > 0 else 0
                raw_data['lux'] = sensor_lux  # for reference, not mapped
            else:
                gain = raw_data.get('gain', 1)
                integration_time_ms = raw_data.get('integration_time_ms', 1)
                normalization = gain * integration_time_ms
                # fallback: keep raw_data as-is
            normalization = 1.0  # Already in lux/nm units if using lux path
        elif sensor_type == 'TSL2591':
            raw_data = sensor_data.get('raw_spectrum_data', {})
            # TSL2591 provides calibrated lux, but raw visible/IR counts aren't directly usable
            # Instead, use the lux value and distribute it according to visible vs IR ratio
            # Allow optional lux calibration factor if provided in config (defaults to 1.0)
            try:
                cfg_factor = float(sensor_data.get('lux_calibration') or 1.0)
            except Exception:
                cfg_factor = 1.0
            sensor_lux = float(raw_data.get('lux') or 0.0) * cfg_factor
            visible_count = raw_data.get('visible', 0)
            infrared_count = raw_data.get('infrared', 0)
            total_count = visible_count + infrared_count
            if total_count > 0 and sensor_lux > 0:
                # Create spectral density distribution (lux/nm) from TSL2591's broad-band values
                # Each channel spans a wide wavelength range, so we create a density value
                # that will be integrated (summed) across bins later
                visible_fraction = visible_count / total_count
                infrared_fraction = infrared_count / total_count
                # Calculate spectral density for each broad channel
                # visible spans 400-700nm (300nm), infrared spans 700-1100nm (400nm)
                visible_width = 300  # nm
                infrared_width = 400  # nm
                # Distribute lux as spectral density (lux/nm) so summing across bins gives correct total
                raw_data = {
                    'visible': (sensor_lux * visible_fraction) / visible_width,
                    'infrared': (sensor_lux * infrared_fraction) / infrared_width,
                    'lux': sensor_lux  # Keep for reference but won't be mapped
                }
            
            normalization = 1.0  # Already in lux units
        elif sensor_type == 'AS7262':
            # AS7262 6-channel VIS sensor — model each channel as a Gaussian with FWHM ~40 nm
            # over each bin. This yields lux/nm per bin and preserves total estimated_lux.
            spectrum = sensor_data.get('raw_spectrum_data', {})
            channel_values = spectrum.get('raw_values', {}) or {}
            # Extract sanitized channel values (non-negative floats)
            channels = {
                'violet': float(max(0.0, channel_values.get('violet', 0.0))),
                'blue':   float(max(0.0, channel_values.get('blue',   0.0))),
                'green':  float(max(0.0, channel_values.get('green',  0.0))),
                'yellow': float(max(0.0, channel_values.get('yellow', 0.0))),
                'orange': float(max(0.0, channel_values.get('orange', 0.0))),
                'red':    float(max(0.0, channel_values.get('red',    0.0)))
            }
            total = sum(channels.values())
            # Determine total lux to distribute (prefer estimated_lux; fallback to default)
            est_lux = sensor_data.get('estimated_lux')
            DEFAULT_LUX = 500.0
            total_lux = float(est_lux) if isinstance(est_lux, (int, float)) and est_lux > 0 else DEFAULT_LUX

            # Channel centers (nm) and Gaussian sigma from FWHM
            centers = {
                'violet': 450.0,
                'blue':   500.0,
                'green':  550.0,
                'yellow': 570.0,
                'orange': 600.0,
                'red':    650.0,
            }
            FWHM = 40.0
            sigma = FWHM / 2.355  # nm
            inv_sqrt2 = 1.0 / math.sqrt(2.0)

            # Compute per-channel lux budgets by relative strength
            if total <= 0:
                return {i: 0.0 for i in range(len(spectrum_bins))}
            channel_lux = {name: (val / total) * total_lux for name, val in channels.items()}

            # Helper: integrate normalized Gaussian over [a,b]
            # Normalized Gaussian pdf: (1/(sigma*sqrt(2*pi))) * exp(-0.5*((x-mu)/sigma)^2)
            # Integral uses error function: Phi = 0.5*(1+erf((x-mu)/(sigma*sqrt(2))))
            def gaussian_cdf(x, mu):
                return 0.5 * (1.0 + math.erf((x - mu) * inv_sqrt2 / sigma))

            bin_contribs = {i: 0.0 for i in range(len(spectrum_bins))}
            for idx, (lo, hi) in enumerate(spectrum_bins):
                bin_width = hi - lo
                if bin_width <= 0:
                    continue
                # Sum contributions from all channels into this bin
                s = 0.0
                for name, mu in centers.items():
                    # Fraction of this channel within the bin
                    frac = gaussian_cdf(hi, mu) - gaussian_cdf(lo, mu)
                    if frac <= 0:
                        continue
                    # Convert channel lux in this bin to a density by dividing by bin width
                    s += (channel_lux.get(name, 0.0) * frac) / bin_width
                bin_contribs[idx] = s
            return bin_contribs
        elif sensor_type in ['AS7341', 'AS7265X']:
            raw_data = sensor_data.get('raw_spectrum_data', {})
            normalization = 1.0
        else:
            raw_data = sensor_data.get('raw_lux_data', {})
            normalization = 1.0
        
        # For this sensor: for each bin, find the narrowest overlapping channel and use only that
        # Precompute normalized values for all channels
        norm_vals = {}
        for ch in raw_data:
            if ch not in wavelength_map or raw_data[ch] is None:
                continue
            # Apply normalization
            if normalization > 0:
                norm_vals[ch] = raw_data[ch] / normalization
            else:
                norm_vals[ch] = raw_data[ch]
        
        # For each bin, find the narrowest overlapping channel for THIS sensor
        for bin_idx, (bin_start, bin_end) in enumerate(spectrum_bins):
            best_ch = None
            best_width = None
            best_val = 0.0
            
            for ch, val in norm_vals.items():
                ch_range = wavelength_map[ch]
                ch_width = ch_range[1] - ch_range[0]
                overlap_start = max(ch_range[0], bin_start)
                overlap_end = min(ch_range[1], bin_end)
                
                if overlap_end > overlap_start:
                    # Convert channel spectral density (lux/nm) to a bin-equivalent density
                    # that integrates correctly when multiplied by bin width.
                    # bin_intensity = density * (overlap_nm / bin_width)
                    overlap_nm = (overlap_end - overlap_start)
                    bin_width = (bin_end - bin_start)
                    contrib = val * (overlap_nm / bin_width)
                    # Pick the narrowest channel (smallest width) for this sensor
                    if best_ch is None or ch_width < best_width:
                        best_ch = ch
                        best_width = ch_width
                        best_val = contrib
            
            # Add this sensor's contribution (will be blended with other sensors via spatial weighting)
            if best_ch is not None:
                bin_contributions[bin_idx] = best_val
        
        # Energy preservation for AS7262: rescale so integrated lux matches estimated_lux if provided
        if sensor_type == 'AS7262':
            try:
                est = sensor_data.get('estimated_lux')
                if isinstance(est, (int, float)) and est > 0:
                    # Integrate current bin_contributions across visible by multiplying by bin width
                    current = 0.0
                    for (lo, hi), idx in zip(spectrum_bins, range(len(spectrum_bins))):
                        center = (lo + hi) / 2.0
                        if 400 <= center <= 700:
                            current += bin_contributions.get(idx, 0.0) * (hi - lo)
                    if current > 0:
                        scale = float(est) / float(current)
                        for idx in list(bin_contributions.keys()):
                            bin_contributions[idx] *= scale
            except Exception:
                pass

        return bin_contributions
    
    @staticmethod
    def spatial_interpolate(sensor1_data: Dict, sensor1_pos: Tuple[float, float],
                           sensor2_data: Dict, sensor2_pos: Tuple[float, float],
                           target_pos: Tuple[float, float]) -> Dict:
        """
        Spatially interpolate between two sensor readings to estimate spectrum at target position.
        Uses 3D inverse distance weighting accounting for light height geometry.
        """
        # Calculate 3D distances accounting for light/sensor height differences
        dist1 = SpectralDataFusion.calculate_3d_light_distance(sensor1_pos, target_pos)
        dist2 = SpectralDataFusion.calculate_3d_light_distance(sensor2_pos, target_pos)
        
        # Avoid division by zero
        if dist1 < 0.01:
            return sensor1_data
        if dist2 < 0.01:
            return sensor2_data
        
        # Inverse square distance weighting (follows light intensity physics)
        weight1 = 1.0 / (dist1 ** 2)
        weight2 = 1.0 / (dist2 ** 2)
        total_weight = weight1 + weight2
        
        weight1_norm = weight1 / total_weight
        weight2_norm = weight2 / total_weight
        
        return {
            'weight1': weight1_norm,
            'weight2': weight2_norm,
            'distance1': dist1,
            'distance2': dist2,
            'interpolation_method': 'inverse_distance_weighting_3d'
        }
    
    @staticmethod
    def get_sensor_quality_for_measurement(sensor_type: str, sensor_data: Dict, spectrum_bins: List[Tuple[int, int]]) -> Dict[int, float]:
        """
        Get measurement-specific quality weights for each spectrum bin.
        
        Different sensors excel at different measurements:
        - BH1750: Excellent lux accuracy, no spectral info
        - TCS34725: Good RGB, poor lux accuracy  
        - TSL2591: Good broad spectrum, excellent IR
        - AS7341/AS7265X: Excellent spectral accuracy across their ranges
        
        Returns:
            Dict mapping bin_index to quality weight (0.0-1.0)
        """
        # Base quality scores for different measurement types
        base_qualities = {
            'AS7265X': {
                'spectral_accuracy': 1.0,    # Excellent 18-channel spectral
                'lux_accuracy': 0.7,         # Good derived lux
                'broadband_accuracy': 0.8    # Good broadband estimation
            },
            'AS7341': {
                'spectral_accuracy': 0.9,    # Excellent 11-channel spectral  
                'lux_accuracy': 0.6,         # Decent derived lux
                'broadband_accuracy': 0.7    # Good broadband estimation
            },
            'TSL2591': {
                'spectral_accuracy': 0.4,    # Limited spectral resolution
                'lux_accuracy': 0.6,         # Good lux measurement
                'broadband_accuracy': 0.8    # Excellent broadband
            },
            'TCS34725': {
                'spectral_accuracy': 0.3,    # Basic RGB only
                'lux_accuracy': 0.3,         # Poor lux accuracy (derived from RGB)
                'broadband_accuracy': 0.4    # Limited broadband capability
            },
            'BH1750': {
                'spectral_accuracy': 0.0,    # No spectral information
                'lux_accuracy': 1.0,         # Excellent dedicated lux measurement
                'broadband_accuracy': 0.5    # Decent broadband indication
            },
            'TSL2561': {
                'spectral_accuracy': 0.1,    # Very limited spectral
                'lux_accuracy': 0.8,         # Good lux accuracy
                'broadband_accuracy': 0.6    # Decent broadband
            },
            'VEML7700': {
                'spectral_accuracy': 0.1,    # Very limited spectral
                'lux_accuracy': 0.9,         # Excellent lux accuracy
                'broadband_accuracy': 0.6    # Decent broadband
            }
        }
        
        if sensor_type not in base_qualities:
            # Unknown sensor - assign minimal quality
            return {i: 0.1 for i in range(len(spectrum_bins))}
        
        qualities = base_qualities[sensor_type]
        bin_qualities = {}
        
        # For each spectrum bin, determine the appropriate quality based on what the sensor measures
        for bin_idx, (bin_start, bin_end) in enumerate(spectrum_bins):
            bin_center = (bin_start + bin_end) / 2
            
            # Determine quality based on measurement type and wavelength
            if sensor_type == 'BH1750':
                # BH1750 provides excellent lux but no spectral detail
                # For broadband bins, use lux accuracy; for specific wavelengths, minimal
                if bin_center >= 400 and bin_center <= 700:  # Visible range where lux is relevant
                    bin_qualities[bin_idx] = qualities['lux_accuracy'] * 0.6  # Scale down since it's not true spectral
                else:
                    bin_qualities[bin_idx] = 0.1  # Minimal for non-visible
                    
            elif sensor_type in ['TSL2561', 'VEML7700']:
                # Good lux sensors but limited spectral
                if bin_center >= 400 and bin_center <= 700:  # Visible range
                    bin_qualities[bin_idx] = qualities['lux_accuracy'] * 0.4
                else:
                    bin_qualities[bin_idx] = 0.1
                    
            elif sensor_type == 'TCS34725':
                # RGB sensor - good for specific color bands, poor elsewhere
                if 620 <= bin_center <= 700:      # Red range
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 1.2  # Boost for red strength
                elif 500 <= bin_center <= 580:    # Green range  
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 1.3  # Boost for green strength
                elif 430 <= bin_center <= 490:    # Blue range
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 1.1  # Boost for blue strength
                elif 400 <= bin_center <= 700:    # Other visible
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 0.8
                else:
                    bin_qualities[bin_idx] = 0.1   # Poor outside visible
                    
            elif sensor_type == 'TSL2591':
                # Good for visible and excellent for IR
                if 400 <= bin_center <= 700:      # Visible range
                    bin_qualities[bin_idx] = qualities['spectral_accuracy']
                elif 700 <= bin_center <= 1100:   # IR range - TSL2591's strength
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 1.5  # Boost for IR excellence
                else:
                    bin_qualities[bin_idx] = 0.2
                    
            elif sensor_type in ['AS7341', 'AS7265X']:
                # Multi-channel sensors - check if bin overlaps with sensor channels
                wavelength_map = SpectralDataFusion.SENSOR_WAVELENGTH_MAPS.get(sensor_type, {})
                max_overlap = 0.0
                
                for channel_range in wavelength_map.values():
                    overlap = min(bin_end, channel_range[1]) - max(bin_start, channel_range[0])
                    if overlap > 0:
                        overlap_fraction = overlap / (bin_end - bin_start)
                        max_overlap = max(max_overlap, overlap_fraction)
                
                if max_overlap > 0.5:  # Good overlap with sensor channel
                    bin_qualities[bin_idx] = qualities['spectral_accuracy']
                elif max_overlap > 0.1:  # Some overlap
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 0.7
                else:  # No overlap - interpolated
                    bin_qualities[bin_idx] = qualities['spectral_accuracy'] * 0.3
                    
            else:
                # Default case
                bin_qualities[bin_idx] = 0.1
            
            # Ensure quality is in valid range
            bin_qualities[bin_idx] = max(0.0, min(1.0, bin_qualities[bin_idx]))
        
        return bin_qualities
    
    @staticmethod
    def calculate_3d_light_distance(sensor_pos: Tuple[float, float], target_pos: Tuple[float, float], 
                                   light_height_ft: float = 6.0, sensor_height_ft: float = 3.0) -> float:
        """
        Calculate 3D distance from sensor to light source accounting for height differences.
        
        Args:
            sensor_pos: (x, y) position of sensor in horizontal plane (units)
            target_pos: (x, y) position where light measurement is needed (units) 
            light_height_ft: Height of light sources above ground (feet)
            sensor_height_ft: Height of sensors above ground (feet)
        
        Returns:
            3D distance in units (assuming 1 unit = 1 foot for simplicity)
            
        Real greenhouse geometry:
        - Lights mounted at 6 feet
        - Sensors at 3 feet  
        - Baseline vertical distance: 3 feet
        - In-zone sensor: sqrt(3^2 + 0^2) = 3 feet from light
        - 1 unit away: sqrt(3^2 + 1^2) = 3.16 feet from light
        """
        # Horizontal distance between sensor position and target position
        horizontal_distance = math.sqrt((target_pos[0] - sensor_pos[0])**2 + (target_pos[1] - sensor_pos[1])**2)
        
        # Vertical distance (height difference between lights and sensors)
        vertical_distance = light_height_ft - sensor_height_ft
        
        # 3D distance using Pythagorean theorem
        distance_3d = math.sqrt(horizontal_distance**2 + vertical_distance**2)
        
        return distance_3d
    
    @staticmethod
    def calculate_light_intensity_weights(sensors_data: List[Dict], positions: List[Tuple[float, float]], 
                                        target_pos: Tuple[float, float], 
                                        light_height_ft: float = 6.0, sensor_height_ft: float = 3.0) -> List[float]:
        """
        Calculate spatial weights based on realistic 3D light-to-sensor geometry.
        
        Uses inverse square law for light intensity: I ∝ 1/d²
        Where d is the 3D distance from light source to sensor.
        
        Args:
            sensors_data: List of sensor readings
            positions: List of (x, y) positions for each sensor  
            target_pos: (x, y) position where we want to estimate spectrum
            light_height_ft: Height of light sources (feet)
            sensor_height_ft: Height of sensors (feet)
            
        Returns:
            List of normalized spatial weights for each sensor
        """
        spatial_weights = []
        
        for i, pos in enumerate(positions):
            # Calculate 3D distance from sensor to light source
            distance_3d = SpectralDataFusion.calculate_3d_light_distance(
                pos, target_pos, light_height_ft, sensor_height_ft
            )
            
            # Apply inverse square law: weight ∝ 1/d²
            # Add small constant to avoid division by zero
            weight = 1.0 / (distance_3d ** 2 + 0.01)
            spatial_weights.append(weight)
        
        # Normalize weights so they sum to 1
        total_weight = sum(spatial_weights)
        if total_weight > 0:
            spatial_weights = [w / total_weight for w in spatial_weights]
        else:
            # Fallback: equal weights
            spatial_weights = [1.0 / len(positions)] * len(positions)
        
        return spatial_weights
    
    @staticmethod
    def fuse_sensor_spectra(sensors_data: List[Dict], positions: List[Tuple[float, float]], 
                           target_pos: Tuple[float, float]) -> Dict:
        """
        Create unified spectrum estimate from multiple heterogeneous sensors.
        
        Args:
            sensors_data: List of sensor readings with format {'sensor_type': str, 'raw_*_data': dict}
            positions: List of (x, y) positions for each sensor
            target_pos: (x, y) position where we want to estimate spectrum
        
        Returns:
            Dict with unified spectrum bins and confidence estimates
        """
        if len(sensors_data) != len(positions):
            raise ValueError("Number of sensors must match number of positions")
        
    # Create standard spectrum bins (20nm width from 280-850nm)
        spectrum_bins = SpectralDataFusion.create_spectrum_bins()
        fused_spectrum = {i: {'value': 0.0, 'confidence': 0.0, 'sources': []} 
                         for i in range(len(spectrum_bins))}
        
        # Calculate spatial weights using realistic 3D light geometry
        spatial_weights = SpectralDataFusion.calculate_light_intensity_weights(
            sensors_data, positions, target_pos
        )
        
        # Map each sensor to spectrum bins and combine
        for i, (sensor_data, spatial_weight) in enumerate(zip(sensors_data, spatial_weights)):
            sensor_type = sensor_data.get('sensor_type', 'UNKNOWN')
            bin_contributions = SpectralDataFusion.map_sensor_to_bins(sensor_type, sensor_data, spectrum_bins)
            
            # Get quality weights based on measurement type and sensor capabilities
            quality_weights = SpectralDataFusion.get_sensor_quality_for_measurement(
                sensor_type, sensor_data, spectrum_bins
            )
            
            # Store raw contributions for later normalization by capable sensors
            for bin_idx, contribution in bin_contributions.items():
                if contribution > 0:  # Sensor has actual measurement for this wavelength
                    bin_quality_weight = quality_weights.get(bin_idx, 0.1)
                    if 'raw_contributions' not in fused_spectrum[bin_idx]:
                        fused_spectrum[bin_idx]['raw_contributions'] = []
                    
                    fused_spectrum[bin_idx]['raw_contributions'].append({
                        'sensor_type': sensor_type,
                        'contribution': contribution,
                        'spatial_weight': spatial_weight,
                        'quality_weight': bin_quality_weight,
                        'sensor_index': i
                    })
        
        # Normalize spatial weights per bin based on sensors that can actually contribute
        for bin_idx, bin_data in fused_spectrum.items():
            if 'raw_contributions' in bin_data and bin_data['raw_contributions']:
                # Calculate total spatial weight from sensors that CAN measure this wavelength
                total_spatial_weight = sum(contrib['spatial_weight'] for contrib in bin_data['raw_contributions'])
                
                # Renormalize spatial weights for this specific wavelength bin
                for contrib in bin_data['raw_contributions']:
                    normalized_spatial_weight = contrib['spatial_weight'] / total_spatial_weight
                    combined_weight = normalized_spatial_weight * contrib['quality_weight']
                    
                    bin_data['value'] += contrib['contribution'] * combined_weight
                    bin_data['confidence'] += combined_weight
                    bin_data['sources'].append({
                        'sensor_type': contrib['sensor_type'],
                        'contribution': contrib['contribution'],
                        'spatial_weight': normalized_spatial_weight,
                        'quality_weight': contrib['quality_weight'],
                        'sensor_index': contrib['sensor_index']
                    })
                
                # Clean up temporary data
                del bin_data['raw_contributions']
        
        # Normalize and create final spectrum
        final_spectrum = {}
        wavelength_centers = []
        intensities = []
        confidences = []
        
        for bin_idx, bin_data in fused_spectrum.items():
            bin_range = spectrum_bins[bin_idx]
            wavelength_center = (bin_range[0] + bin_range[1]) / 2
            
            # Normalize intensity by confidence (acts as weighted average)
            if bin_data['confidence'] > 0:
                normalized_intensity = bin_data['value'] / bin_data['confidence']
            else:
                normalized_intensity = 0.0
                
            wavelength_centers.append(wavelength_center)
            intensities.append(normalized_intensity)
            confidences.append(bin_data['confidence'])
            
            final_spectrum[f'bin_{wavelength_center:.0f}nm'] = {
                'wavelength_range': bin_range,
                'intensity': normalized_intensity,
                'confidence': bin_data['confidence'],
                'sources': bin_data['sources']
            }
        
        return {
            'fused_spectrum': final_spectrum,
            'wavelength_centers': wavelength_centers,
            'intensities': intensities,
            'confidences': confidences,
            'target_position': target_pos,
            'source_sensors': [s.get('sensor_type', 'UNKNOWN') for s in sensors_data],
            'spatial_weights': spatial_weights,
            'spectrum_bins': spectrum_bins
        }
    
    @staticmethod
    def create_histogram_data(fused_result: Dict) -> Dict:
        """Convert fused spectrum to histogram format for plotting."""
        wavelengths = fused_result['wavelength_centers']
        intensities = fused_result['intensities'] 
        confidences = fused_result['confidences']
        
        # Filter out bins with very low confidence
        min_confidence = max(confidences) * 0.1 if confidences else 0
        filtered_data = [(w, i, c) for w, i, c in zip(wavelengths, intensities, confidences) 
                        if c >= min_confidence]
        
        if not filtered_data:
            return {'wavelengths': [], 'intensities': [], 'confidences': []}
        
        wavelengths, intensities, confidences = zip(*filtered_data)
        
        return {
            'wavelengths': list(wavelengths),
            'intensities': list(intensities), 
            'confidences': list(confidences),
            'bin_width': 20,  # nm
            'units': 'lux_per_nm',
            'interpolation_quality': sum(confidences) / len(confidences)
        }


# Example usage functions
def estimate_midpoint_spectrum(tcs34725_data: Dict, tcs34725_pos: Tuple[float, float],
                              tsl2591_data: Dict, tsl2591_pos: Tuple[float, float]) -> Dict:
    """
    Estimate spectrum at midpoint between TCS34725 and TSL2591 sensors.
    
    Example usage:
        tcs_data = {'sensor_type': 'TCS34725', 'raw_color_data': {...}}
        tsl_data = {'sensor_type': 'TSL2591', 'raw_spectrum_data': {...}}
        
        spectrum = estimate_midpoint_spectrum(
            tcs_data, (0, 0),    # TCS34725 at origin
            tsl_data, (2, 0)     # TSL2591 2 units away
        )
    """
    # Calculate midpoint
    midpoint = (
        (tcs34725_pos[0] + tsl2591_pos[0]) / 2,
        (tcs34725_pos[1] + tsl2591_pos[1]) / 2
    )
    
    # Fuse sensor data
    sensors_data = [tcs34725_data, tsl2591_data]
    positions = [tcs34725_pos, tsl2591_pos]
    
    fused_result = SpectralDataFusion.fuse_sensor_spectra(sensors_data, positions, midpoint)
    histogram_data = SpectralDataFusion.create_histogram_data(fused_result)
    
    return {
        'fused_spectrum': fused_result,
        'histogram': histogram_data,
        'fusion_summary': {
            'target_position': midpoint,
            'source_sensors': ['TCS34725', 'TSL2591'],
            'fusion_method': 'inverse_distance_weighted_spectral_mapping',
            'quality_score': histogram_data.get('interpolation_quality', 0)
        }
    }