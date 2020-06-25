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
import csv
#import matplotlib.pyplot as plt
from pint import Quantity as Q_
from utils import *

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
#USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

if len(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''




Vbd = Q_(35.0, 'V') # [V]
max_overbias = 10 # [%]
step_overbias = 0.5 # [%] Each step 1% more overbias


# Frequency measurements settings
slope = 'POS' # Positive('POS')/ Negative('NEG') slope trigger
delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV





# Open Frequency Counter and set it to count measurement
def open_FreqCounter():
	COUNTER = rm.open_resource(USB_adress_COUNTER)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:TOT:TIM 1') # Collect the number of events in 1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER






# Set bias at Vbias and collect counts during 1 sec
def take_measure(COUNTER, SOURCEMETER, Vbias, Vthres):
    # Set voltage to Vbias
    SOURCEMETER.set_voltage(Q_(Vbias, 'V'))
    time.sleep(1.0)

    COUNTER.write('INP1:LEV {}'.format(Vthres)) # Set threshold
    res = 0
    reps = 1
    for i in range(0, reps):
        COUNTER.write('INIT') # Initiate couting
        COUNTER.write('*WAI')
        num_counts = COUNTER.query_ascii_values('FETC?')
        res = res + num_counts[0]

    return res/reps


# Collect dark counts at different trigger levels until no count is registered
def sweep_threshold(COUNTER, SOURCEMETER, Vbias):
	# Vthresh = [-0.025, -0.05, -0.075]

	# for V in Vthresh:
	Vthresh = -0.025 # Start with -25 mV threshold
	counts = [take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh)]

	return [Vthresh, counts]
'''
	Vthresh = -0.050
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
	# return [Vthresh, counts]

	Vthresh = -0.075
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
	return [Vthresh, counts]

	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	Vthresh = Vthresh + delta_thres
	counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))

	while (counts[-1] != 0):
		Vthresh = Vthresh + 0.05
		counts = np.append(counts, take_measure(COUNTER, SOURCEMETER, Vbias, Vthresh))
'''




#---------------------------------------------------------------------------------------


# Open the instruments
rm = pyvisa.ResourceManager()
COUNTER = open_FreqCounter()
try:
	from instrumental.drivers.sourcemeasureunit.hp import HP_4156C

	SOURCEMETER = HP_4156C(visa_address='GPIB0::17::INSTR')
except:
	try:
		from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
		SOURCEMETER = Keithley_2400(visa_address='GPIB0::15::INSTR')
	except:
		print('no sourcemeter available. exiting.')
		exit()
	else:
		print('Keithley connected.')
else:
	print('HP opened')
	SOURCEMETER.set_channel(channel=2)


SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
bring_to_breakdown(SOURCEMETER, Vbd)


# Start with dark measurements
num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
dark_counts = []
max_threshold = np.empty(num_measures) # Max threshold to measure counts (peak's height)

print('Performing Dark counts measurement...')

for i in range (0, num_measures):
    result = sweep_threshold(COUNTER, SOURCEMETER, vec_overbias[i])
    max_threshold[i] = result[0]
    dark_counts.append(result[1])

print('Dark counts measurement finished...')

# Save results
with open("light-TC1_W2-16_PD4A-16um_Vbd_{}_{}max_{}step_Vth-0.25mV_OD5+3.csv".format(Vbd, max_overbias, step_overbias), "w", newline="\n") as file:
    #writer = csv.writer(file)

    file.write('Light counts'  + "\n")
    for i in range (0, num_measures):
        file.write(str(vec_overbias[i]) + ',  ' + ','.join(map(str, dark_counts[i])) + "\n")
'''
    writer.writerows('Laser counts' + "\n")
    for i in range (0, num_measures):
        writer.writerows(str(vec_overbias[i]) + ',  ' + ','.join(map(str, laser_counts[i])) + "\n")

    writer.writerows('Figure of merit' + "\n")
    for i in range (0, num_measures):
        writer.writerows(str(vec_overbias[i]) + ',  ' + ','.join(map(str, fm[i])) + "\n")
'''
bring_down_from_breakdown(SOURCEMETER, Vbd)
COUNTER.close()
#SOURCEMETER.close()
