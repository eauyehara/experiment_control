'''
Created 04/18/2020 @ 11:40

Not tried yet.

Instruments:
	Frequency counter Keysight 53220A
    SMU Keysight B2902A
	or HP Parameter Analyzer

Description
	Collects dark counts and laser counts for different bias voltages.

	1) Collect dark counts sweeping threshold from -2.5mV up to peak's height.
	2) Collect laser counts sweeping threshold from -2.5mV up to the height of a
	dark peak (different for each bias)
	3) Calculate a figure of merit
	4) Save data

'''

import sys
import pyvisa
import numpy as np
import time
from datetime import datetime
import csv
#import matplotlib.pyplot as plt
from pint import Quantity as Q_
from utils import *
import matplotlib.pyplot as plt

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
#USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

if len(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''

Vbd = Q_(37.0, 'V') # [V]
max_overbias = 10 # [%]
step_overbias = 0.5 # [%] Each step 1% more overbias
integration_time = 5.0 # sec
bias_settle_time = 3.0 # sec

# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV
# thresholds = np.arange(-0.005, -0.095, -0.01) # V
# thresholds = [-0.025, -0.05, -0.075]
thresholds = [-0.015] # V



timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
fname = 'TC2_W3-5_PD4A-30um'
csvname = timestamp_str+ fname+  '.csv'
imgname = timestamp_str+ fname+  '.png'
temperature = 25.0

experiment_info = 'Dark-integration {} sec, slope {}, bias settle time {} sec'.format(integration_time, slope, bias_settle_time)

# Open Frequency Counter and set it to count measurement
def open_FreqCounter():
	COUNTER = rm.open_resource(USB_adress_COUNTER)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:TOT:TIM {}'.format(integration_time)) # Collect the number of events in 1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER



# Collect counts during 1 sec
def take_measure(COUNTER, SOURCEMETER, Vbias, Vthres):

    COUNTER.write('INP1:LEV {}'.format(Vthres)) # Set threshold
    res = 0
    reps = 1
    for i in range(0, reps):
        COUNTER.write('INIT') # Initiate couting
        COUNTER.write('*WAI')
        num_counts = COUNTER.query_ascii_values('FETC?')
        res = res + num_counts[0]

    return res/reps/integration_time


# Collect dark counts at different trigger levels until no count is registered
def sweep_threshold(COUNTER, SOURCEMETER, Vbias):
	SOURCEMETER.set_voltage(Vbias)
	time.sleep(bias_settle_time)

	counts = []
	for Vthresh in thresholds:
		print('Counting at Vth = {} V'.format(Vthresh))
		counts.append(take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	return counts


#---------------------------------------------------------------------------------------


# Open the instruments
rm = pyvisa.ResourceManager()
try:
	COUNTER = open_FreqCounter()
except:
	print('no frequency counter available. exiting.')
	exit()
else:
	print('frequency counter connected.')
	temperature = COUNTER.query_ascii_values('SYST:TEMP?')[0]
	print('temp is {}'.format(temperature))
	experiment_info = experiment_info + ', T={} C'.format(temperature)

try:
	from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
	SOURCEMETER = Keithley_2400(visa_address='GPIB1::15::INSTR')
except:
	print('no sourcemeter available. exiting.')
	exit()
else:
	print('Keithley connected.')

SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
bring_to_breakdown(SOURCEMETER, Vbd)

# Start with dark measurements
num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
measurements = []
max_threshold = np.empty(num_measures) # Max threshold to measure counts (peak's height)

print('Performing measurement...')

for i in range(num_measures):
	result = sweep_threshold(COUNTER, SOURCEMETER, vec_overbias[i])
	measurements.append(result)

print('Measurement finished...')

# Save results

with open(csvname, 'w', newline='') as csvfile:
	csvwriter = csv.writer(csvfile, dialect='excel')
	csvwriter.writerow([experiment_info])
	csvwriter.writerow(['', 'Threshold Voltages [V]'])
	csvwriter.writerow(['Bias [V]'] + [str(vth) for vth in thresholds])

	for i in range(num_measures):
		csvwriter.writerow([str(vec_overbias[i].magnitude)] + [str(count) for count in measurements[i]])

bring_down_from_breakdown(SOURCEMETER, Vbd)

plt.figure()
plt.semilogy([vbias.magnitude for vbias in vec_overbias], np.array(measurements)[:,0], 'o-') # plot first threshold data
plt.title(experiment_info)
plt.xlabel('Bias [V]')
plt.ylabel('Counts [cps]')
plt.grid(True, which='both', linestyle=':', linewidth=0.3)
plt.savefig(imgname, dpi=300)
plt.show()


COUNTER.close()
# SOURCEMETER.close()
