from control.spectral_fusion import SpectralDataFusion
from background_scheduler import SensorScheduler

# Sample AS7262 data with estimated_lux ~15000 and plausible channel values
sensor_data = {
    'sensor_type': 'AS7262',
    'raw_spectrum_data': {
        'raw_values': {
            'violet': 57300.0,
            'blue': 71300.0,
            'green': 62000.0,
            'yellow': 60000.0,
            'orange': 59000.0,
            'red': 58000.0
        }
    },
    'estimated_lux': 15000.0
}

bins = SpectralDataFusion.create_spectrum_bins(min_wavelength=280, max_wavelength=850, bin_width=20)
contrib = SpectralDataFusion.map_sensor_to_bins('AS7262', sensor_data, bins)
intensities = [contrib.get(i, 0.0) for i in range(len(bins))]

sched = SensorScheduler()
photopic = sched._estimate_lux_from_spectrum(bins, intensities)

sum_lux = 0.0
for (lo, hi), v in zip(bins, intensities):
    center = (lo + hi) / 2.0
    if 400 <= center <= 700:
        sum_lux += v * (hi - lo)

print("Non-zero bins:", sum(1 for v in intensities if v>0))
print("Integrated lux (flat):", round(sum_lux,3))
print("Photopic lux (weighted):", photopic)

visible = [(i, (lo+hi)/2.0, intensities[i]) for i,(lo,hi) in enumerate(bins) if 400 <= (lo+hi)/2.0 <= 700 and intensities[i] > 0]
print("Visible bin densities (first 6):")
for i, c, v in visible[:6]:
    print(i, c, round(v,3))
