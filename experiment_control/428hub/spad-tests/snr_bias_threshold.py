import sys
import pyvisa
import numpy as np
import time
import csv
import matplotlib.pyplot as plt
from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
from pint import Quantity as Q_
from utils import *

USB_adress_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
# USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

if length(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''

Vbd = 24.2 # [V]
max_overbias = 10 # [%]
step_overbias = 1 # [%] Each step 1% more overbias
num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included

# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger

# def open_SourceMeter():
#     SOURCEMETER = rm.open_resource(USB_adress_SOURCEMETER)
#     SOURCEMETER.write('*RST') # Reset to default settings
#     SOURCEMETER.write(':SOUR1:FUNC:MODE VOLT')
#     SOURCEMETER.write(':SENS1:CURR:PROT 100E-06') # Set compliance at 100 uA
#
#     return SOURCEMETER

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
    # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vbias))
    # SOURCEMETER.write(':OUTP ON')
    SOURCEMETER.set_voltage(Q_(Vbias, 'V'))
    time.sleep(0.5)

    # Initiate couting
    COUNTER.write('INP1:LEV {}'.format(-Vthres)) # Set threshold
    COUNTER.write('INIT') # Initiate couting
    COUNTER.write('*WAI')
    num_counts = COUNTER.query_ascii_values('FETC?')
    return num_counts[0]


# For each bias collect dark counts for all possible threshold levels
def scan_threshold(COUNTER, SOURCEMETER, Vbias):
	v_counts = []
	v_thres = []
	np.append(v_thres, 0)
	np.append(v_counts, take_measure(COUNTER, SOURCEMETER, Vbias, 0))

	delta_thres = 0.025
	while (v_counts[-1] != 0):
		np.append(v_thres, v_thres[-1] + delta_thres)
		np.append(v_counts, take_measure(COUNTER, SOURCEMETER, Vbias, v_thres[-1]))

	return [ v_thres, v_counts ]



rm = pyvisa.ResourceManager()
COUNTER = open_FreqCounter()
SOURCEMETER = Keithley_2400(visa_address='GPIB0::15::INSTR')
SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
bring_to_breakdown(SOURCEMETER, Vbd)

vec_overbias = np.linspace(0, max_overbias, num = num_measures)
voltage_counts = [vec_overbias , np.empty(num_measures), np.empty(num_measures)]

for i in range (0, num_measures):
    voltage_counts[1][i] = Vbd + Vbd*vec_overbias[i]/100 # New overbias
    voltage_counts[2][i] = scan_threshold(COUNTER, SOURCEMETER, voltage_counts[1][i])

bring_down_from_breakdown(SOURCEMETER, Vbd)

'''
plt.figure()
plt.plot(voltage_counts[1], voltage_counts[2], 'ro')
plt.title('Dark counts')
plt.xlabel('Reverse Bias Voltage [V]')
plt.ylabel('Dark counts [1/s]')
plt.grid(True)
plt.savefig("{}-dark_counts_vs_overbias_Vbd_{}_{}max_{}step.png".format(Die, Vbd.magnitude, max_overbias, step_overbias))
'''

with open("{}-optimal_{}_{}max_{}step.csv".format(Die, Vbd.magnitude, max_overbias, step_overbias), "w", newline="") as file:
    writer = csv.writer(file, dialect='excel')
    for i in range (0, num_measures):
        writer.writerows(str(voltage_counts[1][i]) + ', ' + numpy.array2string(voltage_counts[2][i][1]))

COUNTER.close()
SOURCEMETER.close()
