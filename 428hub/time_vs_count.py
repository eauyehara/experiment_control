'''
Instruments:
	Frequency counter: Keysight 53220A
    SMU: Keithley 2400 or HP Parameter Analyzer

Description
	Collects time traces of dark counts and laser counts.

'''

import sys
import pyvisa
import numpy as np
import time
from datetime import datetime
import csv
#import matplotlib.pyplot as plt
from pint import Quantity as Q_
from utils.utils import *
import matplotlib.pyplot as plt
from textwrap import wrap
from utils.progress import progress

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
#USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

if len(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''

Vbd = Q_(38.0, 'V') # [V]
num_measures = 100
time_interval = 1.0 # sec
integration_time = 10.0 # sec
bias_settle_time = 1.0 # sec

# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
# thresholds = np.arange(-0.005, -0.095, -0.01) # V
# thresholds = [-0.025, -0.05, -0.075]
thresholds = [-0.015] # V

timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
fname = 'TC2_W3-23_PD4A-30um'
csvname = './output/'+timestamp_str+ fname+  '.csv'
imgname = './output/'+timestamp_str+ fname+  '.png'

second_plot = 'bias_current' # 'levels' or 'temp' or 'bias_current'
temperature = 25.0

experiment_info = 'Dark-Vbias={}, Vth={}V, integration {} sec, slope {}, bias settle time {} sec'.format(Vbd, thresholds[0], integration_time, slope, bias_settle_time)

# Open Frequency Counter and set it to count measurement
def open_FreqCounter():
	COUNTER = rm.open_resource(USB_adress_COUNTER)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:TOT:TIM {}'.format(integration_time)) # Collect the number of events in 1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.write('DISP OFF')
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
		# print(num_counts)
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

# initialize source meter
try:
	from instrumental.drivers.sourcemeasureunit.hp import HP_4156C
	SOURCEMETER = HP_4156C(visa_address='GPIB0::17::INSTR')
except:
	print('no sourcemeter available. exiting.')
	exit()
else:
	print('HP opened')
	SOURCEMETER.set_channel(channel=2)

SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
bring_to_breakdown(SOURCEMETER, Vbd)

for t in range(round(bias_settle_time)):
	progress(t+1, round(bias_settle_time), status='Bias settle wait {}/{:g} sec'.format(t+1, bias_settle_time))
	time.sleep(1.0)

# Start measurements
timestamp = []
measurements = []
bias_current = []
maxlevel = []
minlevel = []
temperatures = []

print('\nPerforming measurement...')

for i in range(num_measures):
	progress(i+1, num_measures, status='Running measurement')
	# print('{} out of {}'.format(i, num_measures))
	result = take_measure(COUNTER, SOURCEMETER, Vbd, thresholds[0])
	measurements.append(result)
	timestamp.append(time.time())
	minlevel.append(COUNTER.query_ascii_values('INP1:LEV:MIN?')[0])
	bias_current.append(SOURCEMETER.measure_current().magnitude)
	maxlevel.append(COUNTER.query_ascii_values('INP1:LEV:MAX?')[0])
	temperatures.append(COUNTER.query_ascii_values('SYST:TEMP?')[0])

	time.sleep(time_interval)
timestamp = [ts-timestamp[0] for ts in timestamp]

print('\nMeasurement finished...')

# Save results
stats = ', Avg={:g}, stdev={:g}({:g}%) [cps]'.format(np.mean(measurements), np.std(measurements), np.std(measurements)/np.mean(measurements)*100)
with open(csvname, 'w', newline='') as csvfile:
	csvwriter = csv.writer(csvfile, dialect='excel')
	csvwriter.writerow([experiment_info])
	csvwriter.writerow([stats])
	csvwriter.writerow(['Time [s]', 'Temperature', 'Counts [cps]', 'Min level [V]', 'Max Level [V]', 'Bias current [A]'])

	for i in range(num_measures):
		csvwriter.writerow([str(timestamp[i]), str(temperatures[i]), str(measurements[i]), str(minlevel[i]), str(maxlevel[i]), str(bias_current[i])])

bring_down_from_breakdown(SOURCEMETER, Vbd)

fig, ax1 = plt.subplots()

# 1st axis: counts
ax1.plot(timestamp, measurements, 'go-')

ax1.set_xlabel('Time [s]')
ax1.set_ylabel('Counts [cps]', color='g')

ax2 = ax1.twinx()

# 2nd axis
if second_plot == 'temp':
	# plot temperature
	ax2.plot(timestamp, temperatures, 'b^-')
	ax2.set_ylabel('Temperature [$\degree$C]', color='b')
	ax2.set_ylim([round(np.min(temperatures))-1, round(np.max(temperatures))+1])
elif second_plot =='levels':
	# plot levels
	ax2.plot(timestamp, minlevel, 'b^-')
	ax2.plot(timestamp, maxlevel, 'c^-')
	ax2.set_ylabel('Pulse levels [V]', color='b')
	ax2.set_ylim([-0.2, 0])

elif second_plot =='bias_current':
	# plot levels
	ax2.plot(timestamp, bias_current, 'b^-')
	ax2.set_ylabel('Bias Current [A]', color='b')
	# ax2.set_ylim([-0.2, 0])

plt.title("\n".join(wrap(experiment_info+stats, 60)))
plt.savefig(imgname, dpi=300, bbox_inches='tight')
plt.show()

COUNTER.write('DISP ON')
COUNTER.close()
# SOURCEMETER.close()
