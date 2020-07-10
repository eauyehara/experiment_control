import time
import numpy as np
from instruments.Microwave_spectrum_analyzers.HP70900A import HP70900A
from instruments.Arbitrary_waveform_generators.Agilent81180A import Agilent81180A
import csv

# Get SFDR

# --------------------------------------
# Sweep parameters
Vpp_list = [0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
channel_2_Vpp_compensate = 0.02  # channel 2 needs a slightly larger power

vgs_offset = 0
freq1 = 500e3
freq2 = 510e3

base_file_name = 'SFDR_no_DUT_awg_good'

# ------------------------------------
msa = HP70900A()
awg = Agilent81180A()

msa.initialize()
awg.initialize()

# Configure AWG channels and turn on
awg.select_channel(1)
awg.set_waveform('SIN', freq1, Vpp_list[0], vgs_offset)
awg.select_channel(2)
awg.set_waveform('SIN', freq2, Vpp_list[0] + channel_2_Vpp_compensate, vgs_offset)

awg.turn_on()


# Sweep power and get spectrum for each one
for Vpp in Vpp_list:

    awg.select_channel(1)
    awg.set_voltage(Vpp, None)
    awg.select_channel(2)
    awg.set_voltage(Vpp + channel_2_Vpp_compensate, None)

    print('Measuring %.4f mVpp' % (Vpp*1e3))
    print('Set driving signal')

    # Wait 1 second
    time.sleep(1)

    # Get trace
    time_tuple = time.localtime()
    file_name = "SFDR-%s-freq1=%.4fMHz-freq2=%.4fMHz-Vgs_pp=%.3fV-Vgs_offs=%.3fV--%d#%d#%d_%d#%d#%d.csv" % (base_file_name,
                                                                                        freq1*1e-6,
                                                                                        freq2*1e-6,
                                                                                        Vpp,
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


msa.close()
awg.close()
