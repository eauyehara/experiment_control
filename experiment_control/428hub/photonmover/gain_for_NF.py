import time
import numpy as np
from instruments.Microwave_spectrum_analyzers.HP70900A import HP70900A
from instruments.Arbitrary_waveform_generators.Agilent81180A import Agilent81180A
import csv

# Get spectrum sweeping signal amplitude and offset.
# We assume the MSA is already set at the desired parameters

# --------------------------------------
# Sweep parameters
vgs_amps = [0.05]  # [0.1, 0.05]
vgs_offsets = [0.17, 0.18, 0.19, 0.2, 0.21, 0.22, 0.23, 0.24, 0.25]  # [0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11]

freq = 500e3
base_file_name = 'Pin=1mW_no_EDFA_10dB_attenuation_electrical'


# ------------------------------------
msa = HP70900A()
awg = Agilent81180A()

msa.initialize()
awg.initialize()

# Configure AWG and turn on
awg.set_waveform('SIN', freq, vgs_amps[0], vgs_offsets[0])
awg.turn_on()


# Sweep frequency and get spectrum for each one 
for amp in vgs_amps:

    awg.set_voltage(amp, None)

    for off in vgs_offsets:

        # Set offset
        awg.set_voltage(None, off)
        print('Measuring %.4f mVpp, %.4f mV offset...' % (amp*1e3, off*1e3))
        print('Set driving signal')

        # Wait 1 second
        time.sleep(1)

        # Get trace
        time_tuple = time.localtime()
        file_name = "NF_gain-%s-freq=%.4fMHz-Vgs_pp=%.3fV-Vgs_offs=%.3fV--%d#%d#%d_%d#%d#%d.csv" % (base_file_name,
                                                                                            freq*1e-6,
                                                                                            amp,
                                                                                            off,
                                                                                            time_tuple[0],
                                                                                            time_tuple[1],
                                                                                            time_tuple[2],
                                                                                            time_tuple[3],
                                                                                            time_tuple[4],
                                                                                            time_tuple[5])

        msa.read_data(file_name)

        print('Got trace')
        print('-----------------------------')


msa.close()
awg.close()
