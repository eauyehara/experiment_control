import pyvisa
import numpy as np
import time
import csv
import matplotlib.pyplot as plt
import math

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
threshold = -5e-03 # V

num_counts = 1e1 # Number of counts to be taken

# Find, open and configure the FreqCounter
def open_FreqCounter():
	rm = pyvisa.ResourceManager()
	COUNTER = rm.open_resource(USB_adress)

	COUNTER.write('*RST') # Reset to default settings
	COUNTER.write('CONF:SPER') # Configure instrument for single period measurement

	COUNTER.write('INP1:COUP DC') # DC coupled
	COUNTER.write('INP1:IMP 50') # 50 ohm imput impedance
	COUNTER.write('INP1:SLOP {}'.format(slope)) # Positive slope trigger
	COUNTER.write('INP1:LEV {}'.format(threshold)) #0 V threshold
	COUNTER.timeout = 600000 # Timeout of 60000 msec
	time.sleep(2)

	return COUNTER

COUNTER = open_FreqCounter()
num_meas = [1e03]
ex_time = np.zeros(len(num_meas))

for i in range (0, 1):
	COUNTER.write('SAMP:COUN {}'.format(num_meas[i])) # Collect num_counts counts
	print('Measure interarrival times of {} counts'.format(num_meas[i]))
	start = time.time()
	COUNTER.write('INIT')
	COUNTER.write('*WAI')
	time_list = COUNTER.query('FETC?')
	elapsed = time.time() - start
	data = list(np.float_(time_list.split(","))) # Converts the output string to a float list
	print('Measuring time: {} sec'.format(elapsed))
	with open("results-{}-{}.csv".format(num_meas[i], threshold), "w", newline="") as file:
	    writer = csv.writer(file)
	    writer.writerow(["Number of measures: {}".format(num_meas[i])])
	    writer.writerow(["Elapsed time: {} sec".format(elapsed)])
	    writer.writerows(map(lambda x: [x], data))

plt.figure()
plt.hist(data, bins = 100)
plt.show()

'''
time_trigger = data
for i in range (1, num_counts):
	time_trigger[i] = time_trigger[i] + time_trigger[i-1]

driving_period = 1/driving_freq
for i in range (0, num_counts):
	data[i] = time_trigger[i] % driving_period

plt.figure()
plt.hist(data, bins = 10)
plt.show()

'''
#---------------------------------------------------------------------
'''
plt.figure()
plt.title('Registered counts')
plt.plot(data, np.ones(num_counts)) #should sum delta_T
plt.xlabel('Time [s]')
plt.ylabel('Count')
#plt.ylim([-0.25, 1.25])
plt.show()


total_time = np.sum(data)
num_bins = int(drving_period/delta_T)
data_bins = np.zeros(num_bins)

t_end = 0
j = 0
for i in range (0, num_bins):
	t_now = data[j]
	bin_counts = 0
	while(t_now - t_end < delta_T and j < num_counts - 1):
		bin_counts = bin_counts + 1
		t_now = t_now + data[j]
		j = j + 1
	data_bins[i] = bin_counts


plt.figure()
plt.title('Counts in {} sec'.format(delta_T))
print(np.linspace(0, total_time, num_bins))
print(data_bins)
plt.plot(np.linspace(0, total_time, num_bins), data_bins) #should sum delta_T
plt.xlabel('Time [s]')
plt.ylabel('Counts in {} sec'.format(delta_T))
#plt.ylim([0, np.max(data) + 5])
plt.show()
'''
