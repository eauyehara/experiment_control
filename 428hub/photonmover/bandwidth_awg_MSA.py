import time
import numpy as np
from instruments.Microwave_spectrum_analyzers.HP70900A import HP70900A
from instruments.Arbitrary_waveform_generators.Agilent81180A import Agilent81180A
import csv

# --------------------------------------
# Sweep parameters
start_freq = 100e3
end_freq = 100e6
num_freq = 50
log_sweep = True  # If True, it does a logarithmic sweep
base_file_name = 'awg_ref'

vgs_amp = 0.1 
vgs_offset = 0.05
# ------------------------------------


msa = HP70900A()
awg = Agilent81180A()

msa.initialize()
awg.initialize()

# Configure AWG and turn on
awg.set_waveform('SIN', start_freq, vgs_amp, vgs_offset)
awg.turn_on()


if log_sweep:
    freq_list = np.logspace( np.log10(start_freq) , np.log10(end_freq), num_freq)
else:
    freq_list = np.linspace(start_freq, end_freq, num_freq)


peak_freqs = []
peak_amps = []


# Sweep frequency and get spectrum for each one 
for freq in freq_list:

    print('Measuring %.4f MHz...' % (freq*1e-6))

    # Change the frequency of the applied signal
    awg.set_frequency(freq)

    print('Set AWG Freq.')

    # Wait 1 second
    time.sleep(1)

    # Set the MSA to get the signal of interest
    freq_string = "%.4f MHZ" % (freq*1e-6)
    span_string = "%.4f MHZ" % np.minimum(np.maximum((2*freq*1e-6), 0.5), 1)
    msa.set_freq_axis(freq_string, span_string, None, None)
    time.sleep(2)

    # input('Set MSA freq. axis.')

    # Get peak information
    f_peak, amp_val = msa.get_peak_info()
    peak_freqs.append(f_peak)
    peak_amps.append(amp_val)
    print('Peak at %.4f MHz with strength %.4f dB' % (f_peak*1e-6, amp_val))

    print('Got peak data')

    # Get the spectrum and save it
    time_tuple = time.localtime()
    file_name = "%s-freq=%.4fMHz-Vgs_amp=%.3fV-Vgs_offs=%.3fV--%d#%d#%d_%d#%d#%d.csv" % (base_file_name,
                                                                                        freq*1e-6,
                                                                                        vgs_amp,
                                                                                        vgs_offset,
                                                                                        time_tuple[0],
                                                                                        time_tuple[1],
                                                                                        time_tuple[2],
                                                                                        time_tuple[3],
                                                                                        time_tuple[4],
                                                                                        time_tuple[5])

    msa.read_data(file_name)

    print('Got trace')
    print('-----------------------------')


summary_filename = "%s-peaks_vs_freq_summary-Vgs_amp=%.3fV-Vgs_offs=%.3fV--%d#%d#%d_%d#%d#%d.csv" % (base_file_name,
                                                                                                    vgs_amp,
                                                                                                    vgs_offset,
                                                                                                    time_tuple[0],
                                                                                                    time_tuple[1],
                                                                                                    time_tuple[2],
                                                                                                    time_tuple[3],
                                                                                                    time_tuple[4],
                                                                                                    time_tuple[5])

# Save the peak vs frequency data
with open(summary_filename, 'w+') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(freq_list)
    writer.writerow(peak_freqs)
    writer.writerow(peak_amps)

msa.close()
awg.close()
