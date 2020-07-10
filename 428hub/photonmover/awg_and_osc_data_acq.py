import time
import numpy as np
from instruments.Oscilloscopes.RigolDS1000 import RigolDS1000
from instruments.Arbitrary_waveform_generators.Agilent33201A import Agilent33201A

start_vgs_bias = 0.1
stop_vgs_bias = 0.46
num_vgs_bias = 37


vgs_amp = 0.1  # Was 0.1
vgs_freq = 100

osc = RigolDS1000()
awg = Agilent33201A()

osc.initialize()
awg.initialize()

#vpp = []

for vgs_bias in np.linspace(start_vgs_bias, stop_vgs_bias, num_vgs_bias):

    # Set the awg
    awg.set_waveform('SQU', vgs_freq, vgs_amp, vgs_bias)
    time.sleep(1)
    # Autoscale the oscilloscope
    osc.autoscale()
    time.sleep(8)

    # Acquire and save data
    osc.read_waveform([1, 2], "N=4_long_gate_Isc=10uA-Vgs_bias=%.3fV--Vgs_amp=%.3fV--Vgs_freq=%.3fkHz" % (vgs_bias,
                                                                                vgs_amp,
                                                                                vgs_freq*1e-3))
    # vpp.append(osc.measure_item(2, 'VPP'))


#print(vpp)

osc.close()
awg.close()