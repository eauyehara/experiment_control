#%%
from instrumental.drivers.daq.ni import Task # NIDAQ,
from instrumental import instrument
from util.units import Q_, u
import numpy as np
import matplotlib.pyplot as plt

# daq = instrument("NIDAQ_USB-6259", reopen_policy='reuse')
daq2 = instrument("NIDAQ_USB-6259_2", reopen_policy='reuse')
#%% Test external sync Counter Out >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# VCSEL daq
ch_Vout, ch_Vout_str = daq2.ao3, 'Dev2/ao3'
ch_ctr, ch_ctr_str = daq2.ctr0, 'Dev2/ctr0' #p89 sig, p90 gnd
fsamp = 1*u.kHz
nsamp = 100

waveform_base = np.array((1,0))
waveform = np.tile(waveform_base, int(nsamp//2))*u.V

trig_params = {
    "freq" : fsamp,
    "duty_cycle" : 0.5,
    "initial_delay" : 0,
}
scan_task = Task(
    ch_Vout,
    ch_ctr,
    trig_params=trig_params
    )

write_data = {
    ch_Vout_str :   waveform,
}

# Set DAQ sampling rate and number of samples to write/read
scan_task.set_timing(fsamp=fsamp, n_samples=nsamp)
scan_task.run(write_data)
scan_task.unreserve()

#%% Test Counter output >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# Galvo daq
trig_input = '/Dev2/PFI12'  #Need the / at beginning!
ch_ctr1, ch_ctr1_str = daq2.ctr1, '/Dev2/PFI13'
ch_Vout, ch_Vout_str = daq2.ao3, 'Dev2/ao0'

# AO sample clock (Ctr1 output)
N_wav = 10
low_ticks = 2
high_ticks = low_ticks
ext_freq = 10*u.kHz
nsamples = N_wav
fsamp = 1*u.kHz
fsamp = ext_freq / low_ticks

# AO output
waveform_base = np.array((1,0))
waveform = np.tile(waveform_base, int(nsamples//2))*u.V

# Configure AO sample clock (from CTR1)
mtask = daq2._create_mini_task('CO') 
mtask.add_CO_channel(ch_ctr1, low_ticks=low_ticks, high_ticks=high_ticks, source_terminal=trig_input)
mtask.config_implicit_timing(nsamples=nsamples)

scan_task = Task(
    ch_Vout,
)

write_data = {
    ch_Vout_str :   waveform,
}

# Set DAQ sampling rate and number of samples to write/read
scan_task.set_timing(fsamp=fsamp, n_samples=nsamples, clock=ch_ctr1_str)
mtask.start()
mtask.wait_until_done()
scan_task.run(write_data)
scan_task.unreserve()
mtask.unreserve()


#%% Test digital edge trigger >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# clock = '/Dev2/PFI0/SampleClock'
trig_source = '/Dev2/PFI12'
ch_Vout, ch_Vout_str = daq2.ao3, 'Dev2/ao3'
fsamp = 10*u.kHz
nsamp = 1000

waveform_base = np.array((1,0))
waveform = np.tile(waveform_base, int(nsamp//2))*u.V

scan_task = Task(
    ch_Vout,
    )

write_data = {
    ch_Vout_str :   waveform,
}

# Set DAQ sampling rate and number of samples to write/read
scan_task.set_timing(fsamp=fsamp, n_samples=nsamp) #Outputs nsamp at fsamp from internal clock, starts every rising edge of slow external trigger
scan_task.config_digital_edge_trigger(source=trig_source, edge='rising', n_pretrig_samples=0)
# scan_task.set_start_trig_retriggerable()
scan_task.run(write_data)
scan_task.unreserve()


#%%
# ch_ctr = daq2.ctr1
# freq = 10*u.kHz
# nsamples = 1000
# ch_ctr.generate_pulse_train(freq=freq, nsamples=nsamples)


# freq=2000*u.Hz
# nsamples=1000
# with daq2._create_mini_task('CO') as mtask:
#     mtask.add_CO_channel(daq2.ctr0, freq=freq)
#     mtask.config_implicit_timing(nsamples=nsamples)
#     # mtask.config_digital_edge_trigger(source)
#     mtask.start()
#     mtask.wait_until_done()
#%% Testing minitasks >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Configure channels
trig_input = '/Dev2/PFI12'  #Need the / at beginning!
ch_ctr1, ch_ctr1_str = daq2.ctr1, '/Dev2/PFI13'
ch_Vout, ch_Vout_str = daq2.ao3, 'Dev2/ao3'

# AO sample clock (Ctr1 output)
ext_freq = 10*u.kHz
# div = (ext_freq / fsamp).m
low_ticks = 2
high_ticks = low_ticks
nsamples = 10
fsamp = ext_freq / low_ticks

# # AO output
waveform_base = np.array((1,0))
waveform = np.tile(waveform_base, int(nsamples//2))*u.V

# # Configure AO sample clock (from CTR1)
mtask = daq2._create_mini_task('CO') 
# mtask.add_CO_channel(ch_ctr1, freq=ext_freq)
mtask.add_CO_channel(ch_ctr1, low_ticks=low_ticks, high_ticks=high_ticks, source_terminal=trig_input)
mtask.config_digital_edge_trigger(trig_input)
mtask.config_implicit_timing(nsamples=nsamples)
# # mtask.set_start_trig_retriggerable()
# mtask.start()
# mtask.wait_until_done()
# mtask.unreserve()

# Configure AO3 to output samples at CTR1 sample clock
mtask2 = daq2._create_mini_task('AO')
mtask2.add_AO_channel(daq2.ao3)
mtask2.set_AO_only_onboard_mem(daq2.ao3.path, True)
mtask2.config_timing(fsamp, nsamples, clock=ch_ctr1_str)  
mtask2.write_AO_channels({daq2.ao3.path: waveform})

mtask.start()
mtask.wait_until_done()
mtask.stop()
mtask.unreserve()
mtask2.wait_until_done()
mtask2.stop()
mtask2.unreserve()
#%%


#%% Test external sync Counter Out >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# VCSEL daq
# Configure DAQ ctr1 channel
daq = instrument("NIDAQ_USB-6259", reopen_policy='reuse')
ch_clock, ch_clock_str = daq.ctr1, '/Dev1/PFI13'
ch_Vout, ch_Vout_str = daq.ao0, 'Dev1/ao0'
# ch_ctr, ch_ctr_str = daq2.ctr1, 'Dev2/ctr1' #p89 sig, p90 gnd
fsamp = 10*u.Hz
nsamp = 10

waveform_base = np.array((0.5,0))
waveform = np.tile(waveform_base, int(nsamp//2))*u.V

trig_params = {
    "freq" : fsamp,
    "duty_cycle" : 0.5,
    "initial_delay" : 0,
}
scan_task = Task(
    ch_Vout,
    ch_ctr,
    trig_params=trig_params
    )

write_data = {
    ch_Vout_str :   waveform,
}

# Set DAQ sampling rate and number of samples to write/read
scan_task.set_timing(fsamp=fsamp, n_samples=nsamp)
scan_task.run(write_data)
scan_task.unreserve()

#%% Test daq ai/ao sync >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

import matplotlib.pyplot as plt

# VCSEL daq
ch_Vin, ch_Vin_str = daq2.ai1, 'Dev2/ai1'
ch_Vout, ch_Vout_str = daq2.ao3, 'Dev2/ao3'

# AO sample clock (Ctr1 output)
nsamples = 100
fsamp = 1*u.kHz

# AO output
waveform_base = np.array((1,0))
waveform = np.tile(waveform_base, int(nsamples//2))*u.V

scan_task = Task(
    ch_Vout,
    ch_Vin,
)

write_data = {
    ch_Vout_str :   waveform,
}

# Set DAQ sampling rate and number of samples to write/read
scan_task.set_timing(fsamp=fsamp, n_samples=nsamples)
read_data = scan_task.run(write_data)
scan_task.unreserve()

t = read_data['t']
meas = read_data[ch_Vin_str]

plt.figure()
plt.plot(t, waveform)
plt.plot(t, meas)
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.show()

print(f"waveform: {waveform}")
print(f"meas: {meas}")
# %%
