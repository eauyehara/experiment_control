# Collects a given number of interarrival times from Keysight 53220A

import pyvisa
import numpy as np
import csv
import matplotlib.pyplot as plt

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

# Find an open the instrument
rm = pyvisa.ResourceManager()
COUNTER = rm.open_resource(USB_adress)

num_counts = 10 # Number of interarrival times to be measured
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
threshold = 0 # V (absolute)

# Find, open and configure the FreqCounter
def open_FreqCounter():
	rm = pyvisa.ResourceManager()
	COUNTER = rm.open_resource(USB_adress)

	COUNTER.write('*RST') # Reset to default settings

	COUNTER.write('CONF:SPER') # Configure instrument for single period measurement
	COUNTER.write('SAMP:COUN {}'.format(num_counts)) # Collect num_counts counts (for each trigger)

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Set slope trigger
	COUNTER.write('INP1:LEV {}'.format(threshold)) # Set threshold
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(1)

	return COUNTER

COUNTER = open_FreqCounter()

COUNTER.write('INIT') # Initiate the measurements
COUNTER.write('*WAI') # Wait for the measurements to be completed
time_list = COUNTER.query('FETC?') # Read instrument

data = list(np.float_(time_list.split(","))) # Converts the output string to a float list

# Save the results into a csv file
with open("{}counts_{}Vth_interarrival_times.csv".format(num_counts, threshold), "w", newline="") as file:
        writer = csv.writer(file)
		writer.writerows(map(lambda x: [x], data))

# Save an histogram plot of the results
plt.figure()
plt.hist(data, bins = num_counts/100) # Try: Calculate the apropiate num of bins from data
plt.xlabel('Interarrival time [s]')
plt.ylabel('Counts per bin')
plt.savefig('{}counts_{}Vth_interarrival_times.png'.format(num_counts, threshold))
