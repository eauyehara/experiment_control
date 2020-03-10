# Translation to python of Kramnik pqc_get_single_pulse_dist.mat

import pyvisa
import numpy as np
import statistics as stat
import matplotlib.pyplot as plt
import time
import csv

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

delta_T = 0.1 # Measuring time (sec)
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
num_bins = 5 # Number of bins to be measured

delta_thres = 2.5e-03 # 2.5mV steps (resolution of the DAC in the instrument)
Vt_list = np.arange(0, 25e-03, delta_thres) # Attempt, changes in keep_inc



# Find, open and configure the FreqCounter
def open_FreqCounter():
	rm = pyvisa.ResourceManager()
	COUNTER = rm.open_resource(USB_adress)

	COUNTER.write('*RST') #Reset to default settings
	COUNTER.write('INP1:COUP DC') #DC coupled
	COUNTER.write('INP1:IMP 50') #50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) #Positive slope trigger
	COUNTER.timeout = 60000 # Timeout of 60000 msec
	time.sleep(1)
	return COUNTER


def single_totalize_meas(COUNTER, Vt, bins):
	COUNTER.write('INP1:LEV {}'.format(-Vt)) #0V threshold
	data = np.zeros(bins)
	for i in range (0, bins):
		#new_data = COUNTER.query_ascii_values('MEAS:FREQ?')[0]
		new_data = COUNTER.query_ascii_values('MEAS:TOT:TIM? {}'.format(delta_T))[0]
		data[i] = new_data
		time.sleep(delta_T)
	return data


def first_attempt():
	n = len(Vt_list)
	counts_mean = np.zeros(n)
	counts_std = np.zeros(n)

	for i in range (0, n):
		counts = single_totalize_meas(COUNTER, Vt_list[i], num_bins)
		counts_mean[i] = stat.mean(counts)
		counts_std[i] = stat.stdev(counts)

	return [counts_mean, counts_std]


def keep_incr(Vt_list, data):
	while(data[0][-1] != 0): # Stop when we get no counts
		next_Vt = Vt_list[-1] + delta_thres
		Vt_list = np.append(Vt_list, next_Vt)
		counts = single_totalize_meas(COUNTER, next_Vt, num_bins)
		data[0] = np.append(data[0], stat.mean(counts)) # Add the new mean to the data collected
		data[1] = np.append(data[1], stat.stdev(counts)) # Add the new std to the data collected
	return Vt_list, data




COUNTER = open_FreqCounter()
data = first_attempt()


Vt_list, data = keep_incr(Vt_list, data)


PDF = np.zeros(len(Vt_list) - 1)
xaxis = np.zeros(len(Vt_list) - 1)
for i in range (0, len(Vt_list) - 1):
	xaxis[i] = 1e03 * (Vt_list[i] + (Vt_list[i + 1] - Vt_list[i])/2)
	PDF[i] = (data[0][i] - data[0][i + 1])/delta_thres

plt.figure()
plt.title('PDF of height of peaks')
plt.plot(xaxis, PDF)
plt.xlabel('Voltage [mV]')
plt.ylabel('PDF (arb units)')
plt.xlim([40, np.max(xaxis)])
plt.ylim([0, np.max(PDF) + 10000])
plt.show()
