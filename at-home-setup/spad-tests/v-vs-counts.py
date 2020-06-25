'''
Script for measuring SPAD counts for various overbias voltages
which_measurement variable can be specified for dark or light measurements

Instruments:
	Frequency counter Keysight 53220A
    SMU Keithley 2400
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

# from utils import *
import sys
import pyvisa
import numpy as np
import time
from datetime import datetime
import csv
#import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import pickle
from instrumental import Q_
from instrumental.drivers.util import visa_timeout_context


def main():
	##############################################################################
	## Variables to set
	##############################################################################
	which_measurement = "Light" # "Dark" or "Light"

	Vbd = Q_(35.0, 'V') # [V]
	max_overbias = 10 # [%]
	step_overbias = 0.5 # [%] Each step 1% more overbias
	integration_time = 10.0 # sec
	bias_settle_time = 3.0 # sec

# # for testing
# 	Vbd = Q_(1.0, 'V') # [V]
# 	max_overbias = 10.0 # [%]
# 	step_overbias = 5.0 # [%] Each step 1% more overbias
# 	integration_time = 1.0 # sec
# 	bias_settle_time = 1.0 # sec


	# Frequency measurements settings
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV
	# thresholds = np.arange(-0.005, -0.095, -0.01) # V
	# thresholds = [-0.025, -0.05, -0.075]
	thresholds = [-0.015] # V

	# Filenames
	timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
	fname = 'TC2_W4-x_PD4A-30um'
	csvname = './output/'+timestamp_str+ fname+'-{}.csv'.format(which_measurement)
	imgname = './output/'+timestamp_str+ fname+ '-{}.png'.format(which_measurement)
	temperature = 25.0

	experiment_info = '{}-integration {} sec, slope {}, bias settle time {} sec'.format(which_measurement, integration_time, slope, bias_settle_time)


	# Tap power to Incident Power coefficient
	power_measurement = np.genfromtxt('./output/Pi-NE10B.csv', delimiter=',', skip_header=1)
	wavelength = Q_(float(np.round(power_measurement[0])), 'nm')
	print(wavelength)
	tap_to_incident = power_measurement[5]


	# ND filter calibration values -
	# nd_cfg = ["NE10B"]
	nd_cfg = []
	try:
		pickle_in = open("nd_cal.pickle", "rb")
		nd_filters = pickle.load(pickle_in)
	except:
		nd_cal_dir = './output/'

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

		pickle_out = open("nd_cal.pickle", "wb")
		pickle.dump(nd_filters, pickle_out)
		pickle_out.close()
	else:
		print('ND calibration values loaded from nd_cal.pickle file')
		print(nd_filters)

	# Global instrument variables
	COUNTER = None
	SOURCEMETER = None
	POWERMETER = None

	USB_address_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
	USB_address_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'
	USB_address_POWERMETER = 'USB0::0x1313::0x8079::P1001951::INSTR'
	GPIB_address_SOURCEMETER = 'GPIB1::15::INSTR'
	#---------------------------------------------------------------------------------------

	# Initialize tap Power meter
	try:
		from instrumental.drivers.powermeters.thorlabs import PM100A
		# POWERMETER = PM100A(visa_address=USB_address_POWERMETER)'USB0::0x1313::0x8079::P1001951::INSTR'
		POWERMETER = PM100A(visa_address='USB0::0x1313::0x8079::P1001951::INSTR')
	except:
		print('no powermeter available. exiting.')
		exit()
	else:
		print('powermeter opened')
		# # print(wavelength)
		# print(POWERMETER.wavelength)
		POWERMETER.wavelength = wavelength
		POWERMETER.auto_range = 1

	# Open the instruments
	try:
		from instrumental.drivers.frequencycounters.keysight import FC53220A
		COUNTER = FC53220A(visa_address=USB_address_COUNTER)
	except:
		print('no frequency counter available. exiting.')
		exit()
	else:
		print('frequency counter connected.')
		# initialize
		with visa_timeout_context(COUNTER._rsrc, 1000): # timeout of 60,000 msec
			COUNTER.set_mode_totalize(integration_time=integration_time)
			COUNTER.coupling = 'DC'
			COUNTER.impedance = Q_(50, 'ohm')
			COUNTER.slope = 'NEG'

			temperature = COUNTER.temp
			print('temp is {}'.format(temperature))
			experiment_info = experiment_info + ', T={} C'.format(temperature.magnitude)

	# initialize source meter
	try:
		from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
		SOURCEMETER = Keithley_2400(visa_address=GPIB_address_SOURCEMETER)
	except:
		print('no sourcemeter available. exiting.')
		exit()
	else:
		print('Keithley connected.')

	SOURCEMETER.set_current_compliance(Q_(100e-6, 'A'))
	bring_to_breakdown(SOURCEMETER, Vbd)

	# Start with dark measurements
	if which_measurement=="Dark":
		num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
		vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
	elif which_measurement=="Light":
		# load latest dark measurements
		import glob
		# get latest Dark count data file name
		dark_fname = glob.glob('./output/*'+fname+'-Dark.csv')[-1]
		# or manually specify
		# dark_fname = './output/'

		dark_data = np.genfromtxt(dark_fname, delimiter=',', skip_header=1)
		vec_overbias = Q_(dark_data[:,0], 'V')
		num_measures = len(vec_overbias)
		dark_counts= dark_data[:,1].reshape((num_measures,len(thresholds)))
		# print(dark_counts)
	else:
		print('Choose Dark or Light for which_measurement, currently: {}'.format(which_measurement))
		exit()

	count_measurements = []
	tap_avg_measurements = []
	tap_std_measurements = []

	print('Performing measurement...')

	for i in range(num_measures):
		# (counts, power) = sweep_threshold(COUNTER, SOURCEMETER, POWERMETER, vec_overbias[i], bias_settle_time)
		SOURCEMETER.set_voltage(vec_overbias[i])
		time.sleep(bias_settle_time)

		counts = []
		power = []
		power_std = []

		for Vthresh in thresholds:
			print('Counting at Vth = {} V'.format(Vthresh))

			measured = take_measure(COUNTER, POWERMETER, Vthresh, integration_time)
			counts.append(measured[0])
			power.append(measured[1].value.magnitude)
			power_std.append(measured[1].error.magnitude)
		count_measurements.append(counts)
		tap_avg_measurements.append(power)
		tap_std_measurements.append(power_std)
		# print(power)

	count_measurements = np.array(count_measurements)
	tap_avg_measurements = np.array(tap_avg_measurements)
	tap_std_measurements = np.array(tap_std_measurements)

	print(count_measurements)
	print('Measurement finished...')

	# Save results
	if which_measurement == "Dark":
		header = 'Bias [V],'+','.join(['cps @ vth={}'.format(vth) for vth in thresholds])
		data_out = np.array(list(zip(vec_overbias.magnitude, count_measurements)))

		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info)
	elif which_measurement == "Light":
		print('Checking shape of arrays: dark - {}, light- {}'.format(dark_counts.shape, count_measurements.shape))

		# compute things
		actual_power = tap_avg_measurements*tap_to_incident
		print(tap_to_incident)
		for nd_filter in nd_cfg: # attenuate
			actual_power = actual_power*nd_filters[nd_filter]
		incident_cps = actual_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))
		pdp = np.divide((count_measurements-dark_counts), incident_cps, out=np.zeros_like(incident_cps), where=incident_cps!=0)

		# Assemble data
		header = 'Bias [V],'+','.join(
			['cps @ vth={}'.format(vth) for vth in thresholds] +
			['Tap power avg[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Tap power std[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Actual power[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Incident cps @ vth={}'.format(vth) for vth in thresholds] +
			['PDP[%] @ vth={}'.format(vth) for vth in thresholds] )

		experiment_info = experiment_info + ', {}nm'.format(wavelength.value)

		# data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, tap_avg_measurements), axis=1)
		# data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, tap_avg_measurements, tap_std_measurements), axis=1)
		# data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, tap_avg_measurements, tap_std_measurements, actual_power), axis=1)
		# data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, tap_avg_measurements, tap_std_measurements, actual_power, incident_cps), axis=1)
		data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_measurements, tap_avg_measurements, tap_std_measurements, actual_power, incident_cps, pdp), axis=1)

		print(data_out)
		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info)

	bring_down_from_breakdown(SOURCEMETER, Vbd)

	plt.figure()

	from textwrap import wrap
	plt.title("\n".join(wrap(experiment_info+' at Vth={}'.format(thresholds[0]), 60)))

	plt.semilogy(vec_overbias.magnitude, count_measurements[:,0], 'o-') # plot first threshold data

	plt.xlabel('Bias [V]')
	plt.ylabel('Counts [cps]')
	plt.grid(True, which='both', linestyle=':', linewidth=0.3)
	plt.savefig(imgname, dpi=300, bbox_inches='tight')
	# plt.show()

	# COUNTER.close()
	# SOURCEMETER.close()


#############################################################################
## Measurement code
##############################################################################

# Bring the SPAD from 0V to Vbias at Vbias V/step
def bring_to_breakdown(SOURCEMETER, Vbd):
    Vinit = Q_(0, 'V')
    Vstep = Q_(1.0, 'V')

    while (Vinit < Vbd):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit + Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Vbd)
    time.sleep(5.0)
    print('Sourcemeter at breakdown voltage {}'.format(Vbd))

# Bring the SPAD from breakdown to 0V at Vstep V/step
def bring_down_from_breakdown(SOURCEMETER, Vbd):
    Vstep = Q_(1.0, 'V')
    Vinit = Vbd-Vstep

    while (Vinit > Q_(0, 'V')):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit - Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Q_(0, 'V'))
    print('Sourcemeter at 0V')

def take_measure(COUNTER, POWERMETER, Vthresh, integration_time):
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
	with visa_timeout_context(COUNTER._rsrc, 60000): # timeout of 60,000 msec
		# COUNTER.write('INP1:LEV {}'.format(Vthres)) # Set threshold
		COUNTER.Vthreshold = Q_(Vthresh, 'V')
		COUNTER.write('INIT') # Initiate couting
		COUNTER.write('*WAI')

		power = POWERMETER.measure(n_samples = int(integration_time/0.003)) # each sample about 3ms
		num_counts = float(COUNTER.query('FETC?'))

		cps = num_counts/integration_time

	return (cps, power)


# Collect dark counts at different trigger levels until no count is registered
def sweep_threshold(COUNTER, SOURCEMETER, POWERMETER, Vbias, bias_settle_time):
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


if __name__ == '__main__':
	main()
