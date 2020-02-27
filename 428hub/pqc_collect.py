import pyvisa
import numpy as np
import time
import csv

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

delta_T = 1 # Measuring time (sec)
slope = 'POS' # Positive('POS')/ Negative('NEG') slope trigger
threshold = 0 # V 
num_bins = 1 # Number of bins to be measured



	# Find an open the instrument
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
	COUNTER.write('INP1:LEV {}'.format(Vt)) #0V threshold
	data = np.zeros(bins)
	for i in range (0, bins):
		new_data = COUNTER.query_ascii_values('MEAS:TOT:TIM? {}'.format(delta_T))[0]
		data[i] = new_data
	return data


COUNTER = open_FreqCounter()
data = single_totalize_meas(COUNTER, threshold, num_bins)

print(data)



