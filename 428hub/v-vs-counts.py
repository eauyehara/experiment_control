'''
Script for measuring SPAD counts for various overbias voltages
which_measurement variable can be specified for dark or light measurements

Instruments:
	Frequency counter: Keysight 53220A
    SMU: Keithley 2400 or HP Parameter Analyzer
	Power meter: Thorlabs PM100A power meter

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
import numpy as np
import time
from datetime import datetime

import matplotlib.pyplot as plt
from textwrap import wrap
from utils.progress import progress

from instrumental import Q_
from instrumental.drivers.util import visa_timeout_context

import csv
import pickle

def main():
	##############################################################################
	## Variables to set
	##############################################################################
	if len(sys.argv) > 1:
		which_measurement = sys.argv[1]
	else:
		which_measurement = "Light" # "Dark" or "Light"
		# which_measurement = "Light" # "Dark" or "Light"
	pqc = "pcb"# "chip" # "pcb"

	# Vbd = Q_(35, 'V') # [V] for PD4Q
	Vbd = Q_(24.5, 'V') # [V] for PD6D
	max_overbias = 20 # [%] check if it doesn't go over 40V
	max_overbias = 10 # [%] check if it doesn't go over 40V
	step_overbias = 1.0 # [%] Each step 1% more overbias
	integration_time = 10.0 # sec
	bias_settle_time = 3.0 # sec

# # for testing
	if False:
		which_measurement = "Dark" # "Dark" or "Light"
		Vbd = Q_(1.0, 'V') # [V]
		max_overbias = 10.0 # [%]
		step_overbias = 3.0 # [%] Each step 1% more overbias
		integration_time = 1.0 # sec
		bias_settle_time = 1.0 # sec


	# Frequency measurements settings
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	delta_thres = 0.0025 # Resolution of threshold trigger is 2.5 mV
	# thresholds = np.arange(-0.005, -0.095, -0.01) # V
	# thresholds = [-0.05]
	# thresholds = [-0.025, -0.05] #, -0.075, -0.1]
	thresholds = [-0.05, -0.075, -0.1, -0.125] # V
	# thresholds = [-0.025, -0.05, -0.1, -0.15, -0.2] # V
	# thresholds = [-0.05, -0.5, -1, -1.5, -2] # V
	# thresholds = [2.5, 2.45, 2.4, 2.35, 2.3	] # V
	light_threshold = -0.025

	# Filenames
	timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
	# fname = 'TC1_W12-35_PD4A-16um'
	fname ='TC2_W3-20_PD6D-12um'
	csvname = './output/'+timestamp_str+ fname+'-{}.csv'.format(which_measurement)
	imgname = './output/'+timestamp_str+ fname+ '-{}'.format(which_measurement)
	temperature = 25.0

	experiment_info = '{}-integration {} sec, slope {}, bias settle time {} sec'.format(which_measurement, integration_time, slope, bias_settle_time)

	# Tap power to Incident Power coefficient
	power_measurement = np.genfromtxt('./output/nd-cal/850-od0.csv', delimiter=',', skip_header=1)
	wavelength = Q_(float(np.round(power_measurement[0])), 'nm')
	print(wavelength)
	tap_to_incident = power_measurement[5]


	# ND filter calibration values -
	# nd_cfg = ["NE10B"]
	nd_cfg = ["NE40B", "NE20B"]
	nd_cfg = ["NE40B", "NE20B", "NE10B"]
	nd_cfg = ["NE50A-A", "NE40B"]
	nd_cfg = ["od5", "od4"]
	#nd_cfg = ["NE50A-A", "NE30B"]
	if which_measurement=="Light":
		experiment_info = experiment_info + ', ND filters: {}'.format(nd_cfg)
	try:
		pickle_in = open("nd_cal.pickle", "rb")
		nd_filters = pickle.load(pickle_in)
	except:
		nd_cal_dir = './output/nd-cal/'

		print('No ND calibration value pickle file, generating from csv data set in {}'.format(nd_cal_dir))

		nd_filters = {
			#"NE10B": 0,
			#"NE20B": 0,
			#"NE30B": 0,
			# "NE40B": 0,
			# "NE50A-A": 0,
			'od4': 0,
			'od5': 0,
		}

		Pi = np.genfromtxt(nd_cal_dir+'850-od0.csv', delimiter=',', skip_header=1)
		for (filter, value) in nd_filters.items():
			Po = np.genfromtxt(nd_cal_dir+'850-'+filter+'.csv', delimiter=',', skip_header=1)

			nd_filters[filter] = Po[1]/Pi[1]

		pickle_out = open("nd_cal.pickle", "wb")
		pickle.dump(nd_filters, pickle_out)
		pickle_out.close()
	else:
		print('ND calibration values loaded from nd_cal.pickle file')
		# print(nd_filters)

	# Global instrument variables
	COUNTER = None
	SOURCEMETER = None
	POWERMETER = None

	address_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
	#USB_address_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'
	address_SOURCEMETER = 'GPIB0::15::INSTR'
	address_POWERMETER = 'USB0::0x1313::0x8079::P1001951::INSTR'
	#---------------------------------------------------------------------------------------

	# Initialize tap Power meter
	try:
		from instrumental.drivers.powermeters.thorlabs import PM100A
		#POWERMETER = PM100A(visa_address=USB_address_POWERMETER)

		POWERMETER = PM100A(visa_address=address_POWERMETER)
	except:
		print('no powermeter available. exiting.')
		POWERMETER=None
	else:
		print('powermeter opened')
		POWERMETER.wavelength = wavelength
		POWERMETER.auto_range = 1

	# Open the instruments
	try:
		from instrumental.drivers.frequencycounters.keysight import FC53220A
		COUNTER = FC53220A(visa_address=address_COUNTER)
	except:
		print('no frequency counter available. exiting.')
		exit()
	else:
		print('frequency counter connected.')
		# initialize
		with visa_timeout_context(COUNTER._rsrc, 60000): # timeout of 60,000 msec
			COUNTER.set_mode_totalize(integration_time=integration_time)
			COUNTER.coupling = 'DC'
			if pqc == "pcb":
				print('pcb pqc setting to 50Ohm')
				COUNTER.impedance = Q_(50, 'ohm')
				# print('pcb pqc setting to 1MOhm')
				# COUNTER.impedance = Q_(1e6, 'ohm')
			elif pqc == "chip":
				print('on chip pqc setting to 1MOhm')
				COUNTER.impedance = Q_(1e6, 'ohm')
			COUNTER.slope = 'NEG'

			temperature = COUNTER.temp
			print('temp is {}'.format(temperature))
			experiment_info = experiment_info + ', T={} C'.format(temperature.magnitude)

			COUNTER.display = 'OFF'

	# initialize source meter
	# try:
	# 	from instrumental.drivers.sourcemeasureunit.hp import HP_4156C
	# 	SOURCEMETER = HP_4156C(visa_address='GPIB0::17::INSTR')
	# except:
	# 	print('no sourcemeter available. exiting.')
	# 	exit()
	# else:
	# 	print('HP opened')
	# 	SOURCEMETER.set_channel(channel=2)

	# initialize source meter
	try:
		from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
		SOURCEMETER = Keithley_2400(visa_address=address_SOURCEMETER)
	except:
		print('no sourcemeter available. exiting.')
		exit()
	else:
		print('Keithley connected.')

	SOURCEMETER.set_current_compliance(Q_(8e-3, 'A'))
	bring_to_breakdown(SOURCEMETER, Vbd)

	# Start with dark measurements
	if which_measurement=="Dark":
		num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
		vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)
	elif which_measurement=="Light":
		# load latest dark measurements
		import glob
		# get latest Dark count data file name
		try:
			dark_fname = glob.glob('./output/*'+fname+'-Dark.csv')[-1]
		except:
			print('Dark results not available, run Dark measurement first.')
			exit()
		else:
			print(dark_fname)
		# or manually specify
		# dark_fname = './output/'

		dark_data = np.genfromtxt(dark_fname, delimiter=',', skip_header=1, skip_footer=1)
		vec_overbias = Q_(dark_data[:,0], 'V')
		num_measures = len(vec_overbias)
	else:
		print('Choose Dark or Light for which_measurement, currently: {}'.format(which_measurement))
		exit()

	# truncate voltages beyond 2.5V above breakdown
	if pqc=='chip':
		vec_overbias = vec_overbias[vec_overbias < Vbd+Q_(2.5, 'V')]
		num_measures = len(vec_overbias)
		print('Adjusting bias range to {} to {} to protect on chip quench circuit'.format(vec_overbias[0], vec_overbias[-1]))

	count_measurements = []
	tap_avg_measurements = []
	tap_std_measurements = []

	print('Performing {} measurement...'.format(which_measurement))

	for i in range(num_measures): # loop through biases
		print('\n{} out of {}'.format(i+1, num_measures))
		SOURCEMETER.set_voltage(vec_overbias[i])
		time.sleep(bias_settle_time)

		counts = []
		power = []
		power_std = []

		for Vthresh in thresholds:
			print('     Counting at Vth = {} V'.format(Vthresh))

			measured = take_measure(COUNTER, POWERMETER, Vthresh, integration_time)
			counts.append(measured[0])
			power.append(measured[1].value.magnitude)
			power_std.append(measured[1].error.magnitude)

			if which_measurement=="Light":
				# Set dark counts according to current Vthreshold
				try:
					dark_counts= dark_data[:,thresholds.index(Vthresh)+1].reshape((num_measures,1))
				except:
					print('Dark and light measurement thresholds do not match')
					dark_counts= dark_data[:,0].reshape((num_measures,1))
					print('using dark count data {}'.format(dark_counts))

				act_power = power[-1]*tap_to_incident
				for nd_filter in nd_cfg: # attenuate
					act_power = act_power*nd_filters[nd_filter]
				inc_cps = act_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))
				pdpp = np.divide((counts[-1]-dark_counts[i]), inc_cps, where=inc_cps!=0)

				print('     	Counts: {}, dark cps: {}, pdp={:.3g}'.format(measured[0], dark_counts[i], pdpp[0]))
				print('     		Power avg: {:.2g}, std: {:.2g}'.format(measured[1].value.magnitude, measured[1].error.magnitude))
				print('     		Incident pwr: {:.2g}, cps={:.2g}'.format(act_power, inc_cps))
			else:
				print('     Counts: {}, Power avg: {:.2g}, Power std: {:.2g}'.format(measured[0], measured[1].value.magnitude, measured[1].error.magnitude))

		count_measurements.append(counts)
		tap_avg_measurements.append(power)
		tap_std_measurements.append(power_std)

	count_measurements = np.array(count_measurements)
	tap_avg_measurements = np.array(tap_avg_measurements)
	tap_std_measurements = np.array(tap_std_measurements)

	# print(count_measurements)
	print('Measurement finished...')

	# Save results
	if which_measurement == "Dark":
		header = 'Bias [V],'+','.join(['cps @ vth={}'.format(vth) for vth in thresholds])
		data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_measurements), axis=1)
		# print(data_out)
		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")
	elif which_measurement == "Light":
		dark_counts = dark_data[:,1:] # skip bias column
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
			['PDP @ vth={}'.format(vth) for vth in thresholds] )

		experiment_info = experiment_info + ', {}nm'.format(wavelength.magnitude) + ', Dark count data {}'.format(dark_fname)

		data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_measurements, tap_avg_measurements, tap_std_measurements, actual_power, incident_cps, pdp), axis=1)

		plt.figure()
		plt.title("\n".join(wrap('PDP '+experiment_info+' at Vth={}'.format(thresholds[0]), 60)))
		plt.plot(vec_overbias.magnitude, pdp, 'o-') # plot first threshold data
		plt.xlabel('Bias [V]')
		plt.ylabel('PDP')
		plt.legend([str(vth) for vth in thresholds])
		# plt.ylim([0,1.0])
		plt.grid(True, which='both', linestyle=':', linewidth=0.3)
		plt.savefig(imgname+'-PDP.png', dpi=300, bbox_inches='tight')

		#print(data_out)
		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")

	bring_down_from_breakdown(SOURCEMETER, Vbd)
	COUNTER.display = 'ON'
	plt.figure()
	plt.title("\n".join(wrap('Counts '+experiment_info+' at Vth={}'.format(thresholds[0]), 60)))
	plt.semilogy(vec_overbias.magnitude, count_measurements, 'o-') # plot first threshold data
	plt.legend([str(vth) for vth in thresholds])
	# plt.semilogy(vec_overbias.magnitude, count_measurements[:,0], 'o-', label='Light') # plot first threshold data
	# if which_measurement == 'Light':
	# 	plt.semilogy(vec_overbias.magnitude, dark_counts[:,0], 'o-', label='Dark') # plot first threshold data
	# 	plt.legend()

	plt.xlabel('Bias [V]')
	plt.ylabel('Counts [cps]')
	plt.grid(True, which='both', linestyle=':', linewidth=0.3)
	plt.savefig(imgname+'-Counts.png', dpi=300, bbox_inches='tight')
	# plt.show()


#############################################################################
## Measurement code
##############################################################################

# Bring the SPAD from 0V to Vbias at Vbias V/step
def bring_to_breakdown(SOURCEMETER, Vbd):
    Vinit = Q_(0, 'V')
    Vstep = Q_(5.0, 'V')

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
    Vstep = Q_(5.0, 'V')
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
		COUNTER.Vthreshold = Q_(Vthresh, 'V')
		COUNTER.write('INIT') # Initiate couting
		COUNTER.write('*WAI')

		if POWERMETER is not None:
			power = POWERMETER.measure(n_samples = int(integration_time/0.003)) # each sample about 3ms
		else:
			power = Q_(0.0, 'W').plus_minus(Q_(0.0, 'W'))
		num_counts = float(COUNTER.query('FETC?'))

		cps = num_counts/integration_time

	return (cps, power)

if __name__ == '__main__':
	main()

	try:
	    import winsound
	    winsound.Beep(2200, 1000)
	except:
	    print('winsound not available no beeping')
