# Measures signal frequency using Keysight 53220A

import pyvisa
import numpy as np
import csv
import time

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
threshold = -0.01 # V (absolute)

# Find, open and configure instrument
def open_FreqCounter():
	rm = pyvisa.ResourceManager()
	COUNTER = rm.open_resource(USB_adress)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:FREQ') # Configure instrument for frequency measurement
	COUNTER.write('FREQ:GATE:TIME 0.1') # Set a gate of 0.1 sec

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.write('INP1:LEV {}'.format(threshold)) # Set threshold
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER

COUNTER = open_FreqCounter()

COUNTER.write('INIT') # Initiate the measurement
COUNTER.write('*WAI') # Wait for the measurement to be completed
time_list = COUNTER.query('FETC?') # Read instrument

print('Frequency: {} sec'.format(time_list))
