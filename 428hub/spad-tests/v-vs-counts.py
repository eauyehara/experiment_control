'''
Script for measuring SPAD counts for various overbias voltages
which_measurement variable can be specified for dark or light measurements

Instruments:
	Frequency counter Keysight 53220A
    SMU Keysight B2902A
	or HP Parameter Analyzer
	Thorlabs PM100A power meter

Description
	Collects dark counts and laser counts for different bias voltages.

	1) Collect dark counts sweeping threshold from -2.5mV up to peak's height.
	2) Collect laser counts sweeping threshold from -2.5mV up to the height of a
	dark peak (different for each bias)
	3) Calculate a figure of merit
	4) Save data under ./output folder

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
import pickle

if len(sys.argv)>1:
	Die = sys.argv[1]
else:
	Die = ''

##############################################################################
## Variables to set
##############################################################################
which_measurement = "Dark" # or "Light"

Vbd = Q_(5.0, 'V') # [V]
max_overbias = 10 # [%]
step_overbias =5 # to test 0.5 # [%] Each step 1% more overbias
integration_time = 5.0 # sec
bias_settle_time = 3.0 # sec

# Frequency measurements settings
slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV
# thresholds = np.arange(-0.005, -0.095, -0.01) # V
# thresholds = [-0.025, -0.05, -0.075]
thresholds = [-0.015] # V

# Filenames
timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
fname = 'TC2_W3-5_PD4A-30um'
csvname = './output/'+timestamp_str+ fname+'-{}.csv'.format(which_measurement)
imgname = './output/'+timestamp_str+ fname+ '-{}.png'.format(which_measurement)
temperature = 25.0

experiment_info = '{}-integration {} sec, slope {}, bias settle time {} sec'.format(which_measurement, integration_time, slope, bias_settle_time)


# Tap power to Incident Power coefficient
 power_measurement = np.genfromtxt('C:/Users/poegroup/Documents/GitHub/jhwnkim/20200622/ND filter calibration/Pi-NE10B.csv', delimiter=',', skip_header=1)
 wavelength = np.round(power_measurement[0])
 tap_to_incident = power_measurement[5]


# ND filter calibration values -
nd_cfg = ["NE10B"]
try:
	pickle_in = open("config/nd_cal.pickle", "rb")
	nd_filters = pickle.load(pickle_in)
except:
	nd_cal_dir = 'C:/Users/poegroup/Documents/GitHub/jhwnkim/20200622/ND filter calibration/'

	print('No ND calibration value pickle file, generating from csv data set in {}'.format(nd_cal_dir))

	nd_filters = {
		"NE10B": 0,
		"NE20B": 0,
		"NE30B": 0,
		"NE40B": 0,
		"NE50A-A": 0,
	}
	for (filter, value) in nd_filters.items():
		Pi = np.genfromtxt(nd_cal_dir+'Pi-'+filter+'.csv', delimiter=',', skip_header=1)
		Po = np.genfromtxt(nd_cal_dir+'Po-'+filter+'.csv', delimiter=',', skip_header=1)

		nd_filters[filter] = Po[1]/Pi[1]

	pickle_out = open("config/nd_cal.pickle", "wb")
	pickle.dump(nd_filters, pickle_out)
	pickle_out.close()
else:
	print('ND calibration values loaded from nd_cal.pickle file')

# Global instrument variables
COUNTER = None
SOURCEMETER = None
POWERMETER = None

USB_address_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
USB_address_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'
USB_address_POWERMETER = 'USB0::0x1313::0x8079::P1001952::INSTR'


##############################################################################
## Measurement code
##############################################################################

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




def take_measure(COUNTER, POWERMETER, Vbias, Vthres):
	'''
		Collect counts during integration_time and measures power

		Input Parameters:
		COUNTER: frequency counter object
		POWERMETER: powermeter object
		Vthres: threshold voltage for frequency counter

		Returns: (cps, int_power)
		cps: counts per second
		power: average optical power during measurement returned as pint.Measurement object
	'''

    COUNTER.write('INP1:LEV {}'.format(Vthres)) # Set threshold

    COUNTER.write('INIT') # Initiate couting
    COUNTER.write('*WAI')

	power = POWERMETER.measure(n_samples = np.round(integration_time/0.003) # each sample about 3ms
    num_counts = COUNTER.query_ascii_values('FETC?')

	cps = num_counts[0]/integration_time

    return (cps, power)


# Collect dark counts at different trigger levels until no count is registered
def sweep_threshold(COUNTER, SOURCEMETER, POWERMETER, Vbias):
	'''
	Sweeps threshold values for the frequency counter and takes measurements

	returns
	'''
	SOURCEMETER.set_voltage(Vbias)
	time.sleep(bias_settle_time)

	counts = []
	power = []

	for Vthresh in thresholds:
		print('Counting at Vth = {} V'.format(Vthresh))

		measured = take_measure(COUNTER, POWERMETER, Vthresh)
		counts.append(measured[0])
		power.append(measured[1])

	return (counts, power)


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


# Initialize tap Power meter
try:
	from instrumental.drivers.powermeters.thorlabs import PM100A
	POWERMETER = PM100A(visa_address=USB_address_POWERMETER)
except:
	print('no powermeter available. exiting.')
	exit()
else:
	print('powermeter opened')
	POWERMETER.wavelength = wavelength

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

# Start with dark measurements
num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
count_measurements = []
tap_avg_measurements = []
tap_std_measurements = []
max_threshold = np.empty(num_measures) # Max threshold to measure counts (peak's height)

print('Performing measurement...')

for i in range(num_measures):
	(counts, power) = sweep_threshold(COUNTER, SOURCEMETER, vec_overbias[i])
	count_measurements.append(counts)
	tap_avg_measurements.append(power.value.magnitude)
	tap_std_measurements.append(power.error.magnitude)
	print(power)

count_measurements = np.array(count_measurements)
tap_avg_measurements = np.array(tap_avg_measurements)
tap_std_measurements = np.array(tap_std_measurements)

print('Measurement finished...')

# Save results
if which_measurement == "Dark":
	header = 'Bias [V],'+','.join(['cps @ vth={}'.format(vth) for vth in thresholds])
	data_out = np.array(list(zip(vec_overbias, count_measurements))
	np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info)
elif which_measurement == "Light":
	# load latest dark measurements
	import glob
	# get latest Dark count data file name
	dark_fname = glob.glob('./output/*'+fname+'-Dark.csv')[-1]
	# or manually specify
	# dark_fname = './output/'

	dark_counts=np.genfromtxt(dark_fname, delimiter=',', skip_header=1, skip_footer=1)
	print('Checking shape of arrays: dark - {}, light- {}'.format(dark_counts.shape, count_measurements.shape))

	# compute things
	actual_power = tap_avg_measurements*tap_to_incident
	incident_cps = actual_power/(6.62607015E-34*299792458/(wavelength*1e-9))
	pdp = np.divide((count_measurements-dark_counts), incident_cps, out=np.zeros_like(incident_cps), where=incident_cps!=0)

	# Assemble data
	header = 'Bias [V],'+','.join(
		['cps @ vth={}'.format(vth) for vth in thresholds] +
		['Tap power avg[W] @ vth={}'.format(vth) for vth in thresholds] +
		['Tap power std[W] @ vth={}'.format(vth) for vth in thresholds] +
		['Actual power[W] @ vth={}'.format(vth) for vth in thresholds] +
		['Incident cps @ vth={}'.format(vth) for vth in thresholds] +
		['PDP[%] @ vth={}'.format(vth) for vth in thresholds] )

	data_out = np.concatenate((vec_overbias, tap_avg_measurements, tap_std_measurements, actual_power, incident_cps, pdp), axis=1)

	np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info)

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
