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
	# fname ='TC1_W12-14_PD6D-12um-9K10um'
	# fname = 'TC1_W12-7_PD6D-12um-9K11p5um'
	# fname ='TC1_W12-14_PD6D-12um-9K12um'
	fname ='TC1_W12-14_PD6D-16um'
	# fname='TC1_W12-7_PD6D-12um-STI1500nm'
	# fname='TC1_W12-7_PD6D-12um-Intr1000nm'
	# fname ="ICE1_SiGe_EOS_dopings"

	# fname ='TC1_W12-14_PD6D-20um-HalfCrossHover'
	# fname = 'TC1_W12-14_PD6D-16um'
	pqc = "pcb"# "chip" # "pcb"
	print('Measuring {}'.format(fname))

	# device = 'PD6D-12um-9K'
	# device = 'PD6D-16um'
	device = 'PD6D-16um-50'
	# device = 'ice1'
	exp_setting = {
	# device: Vbd, max bias, num of points, number of samples, thresholds]
		'PD6D': [Q_(24, 'V'), Q_(28.8, 'V'), 21, 1.0, [-0.025, -0.05, -0.075, -0.1, -0.125]],
		'PD6D-wide': [Q_(24, 'V'), Q_(28, 'V'), 21, 1.0, [-0.025, -0.05]],
		'PD6D-zoom': [Q_(25.5, 'V'), 2, 0.1, 1.0, [-0.025, -0.05]],
		'PD6D-4um': [Q_(30.0, 'V'), Q_(36.0, 'V'), 21, 4.0, [-0.02, -0.030, -0.040, -0.05, -0.06]],
		'PD6D-12um': [Q_(24.5, 'V'), Q_(26.95, 'V'), 21, 1.0, [-0.025, -0.05]],
		'PD6D-12um-9K': [Q_(25.9, 'V'), Q_(26.9, 'V'), 21, 1.0, [-0.05]],
		'PD6D-16um': [Q_(25.5, 'V'), Q_(25.7, 'V'), 21, 1.0, [-0.05]],
		'PD6D-16um-50': [Q_(25.5, 'V'), Q_(25.7, 'V'), 21, 1.0, [-0.020, -0.025]],
		'PD4A': [Q_(33.5, 'V'), Q_(40.2, 'V'), 21, 1.0, [-0.025, -0.05, -0.075, -0.1, -0.125]],
		'test': [Q_(25.5, 'V'), Q_(25.8, 'V'), 4, 1.0, [-0.025, -0.05]],
		'ice1': [Q_(20, 'V'), Q_(23, 'V'), 5, 1.0, [-0.015, -0.016, -0.017]],
	}

	Vbd = exp_setting[device][0]
	max_bias = exp_setting[device][1]
	num_measures = exp_setting[device][2]
	# max_overbias = exp_setting[device][1]
	# step_overbias = exp_setting[device][2]
	integration_time = exp_setting[device][3]
	thresholds = exp_setting[device][4]

# # for testing
	if False:
		which_measurement = "Light" # "Dark" or "Light"
		Vbd = Q_(1.0, 'V') # [V]
		max_overbias = 1.5 # [%]
		step_overbias = 1.0 # [%] Each step 1% more overbias
		integration_time = 1.0 # sec
		reps =3 # number of repititions
		bias_settle_time = 1.0 # sec
		thresholds = [-0.025, -0.05]

	if pqc=='chip':
		if max_bias > Q_(2.5, 'V'):
			print('Adjusting max bias from {} to {} to protect on chip quench circuit'.format(max_bias, Vbd+Q_(2.5, 'V')))
			max_bias = Q_(2.5, 'V')+Vbd

	vec_overbias = np.linspace(Vbd, max_bias, num = num_measures)

	bias_settle_time = 3.0 # sec
	reps = 10 # number of repititions

	# Frequency measurements settings
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	Zin = 50 #1.0e6  # 50

	# Filenames
	timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
	# fname = 'TC1_W12-35_PD4A-16um'

	csvname = './output/'+timestamp_str+ fname+'-{}.csv'.format(which_measurement)
	imgname = './output/'+timestamp_str+ fname+ '-{}'.format(which_measurement)
	temperature = 25.0

	try:
		experiment_info = '#{}-integration {} sec x {}; slope {}; bias settle time {} sec; input Z={}; Bias(Vbd={} Vex={}% Vex step={}%)'.format(which_measurement, integration_time, reps, slope, bias_settle_time, Zin, Vbd, max_overbias, step_overbias)
	except:
		experiment_info = '#{}-integration {} sec x {}; slope {}; bias settle time {} sec; input Z={}; Bias(Vbd={} Vex={})'.format(which_measurement, integration_time, reps, slope, bias_settle_time, Zin, Vbd, max_bias.magnitude)

	wl = int(940)
	# Tap power to Incident Power coefficient
	# power_measurement = np.genfromtxt('./output/nd-cal/850-od0.csv', delimiter=',', skip_header=1)
	# power_measurement = np.genfromtxt('./output/850-cal-20210311.csv', delimiter=',', skip_header=1)
	power_measurement = np.genfromtxt('./output/nd-cal/{}-od0.csv'.format(wl), delimiter=',', skip_header=1)
	wavelength = Q_(float(np.round(power_measurement[0])), 'nm')
	# print(wavelength)
	tap_to_incident = power_measurement[5]


	# ND filter calibration values -
	# nd_cfg = ["NE10B"]
	nd_cfg = ["NE40B", "NE20B"]
	nd_cfg = ["NE40B", "NE20B", "NE10B"]
	nd_cfg = ["NE50A-A", "NE40B"]
	nd_cfg = ["od5", "od4"]
	#nd_cfg = ["NE50A-A", "NE30B"]
	if which_measurement=="Light":
		experiment_info = experiment_info + '; ND filters: {}'.format(nd_cfg)
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

		Pi = np.genfromtxt(nd_cal_dir+'{}-od0.csv'.format(wl), delimiter=',', skip_header=1)
		for (filter, value) in nd_filters.items():
			Po = np.genfromtxt(nd_cal_dir+'{}-'.format(wl)+filter+'.csv', delimiter=',', skip_header=1)

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
	print('Initializing instruments: ')
	# Initialize tap Power meter
	try:
		from instrumental.drivers.powermeters.thorlabs import PM100A
		#POWERMETER = PM100A(visa_address=USB_address_POWERMETER)

		POWERMETER = PM100A(visa_address=address_POWERMETER)
	except:
		print('    no powermeter available. exiting.')
		POWERMETER=None
	else:
		print('    powermeter opened')
		POWERMETER.wavelength = wavelength
		POWERMETER.auto_range = 1

	# Open the instruments
	try:
		from instrumental.drivers.frequencycounters.keysight import FC53220A
		COUNTER = FC53220A(visa_address=address_COUNTER)
	except:
		print('    no frequency counter available. exiting.')
		exit()
	else:
		print('    frequency counter connected.')
		# initialize
		with visa_timeout_context(COUNTER._rsrc, 60000): # timeout of 60,000 msec
			COUNTER.set_mode_totalize(integration_time=integration_time)
			COUNTER.coupling = 'DC'
			if pqc == "pcb":
				print('     pcb pqc setting to {}Ohm'.format(Zin))
				COUNTER.impedance = Q_(Zin, 'ohm')
				# print('pcb pqc setting to 1MOhm')
				# COUNTER.impedance = Q_(1e6, 'ohm')
			elif pqc == "chip":
				print('    on chip pqc setting to 1MOhm')
				COUNTER.impedance = Q_(1e6, 'ohm')
			COUNTER.slope = 'NEG'

			temperature = COUNTER.temp
			print('    temp is {}'.format(temperature))
			experiment_info = experiment_info + '; T={} C'.format(temperature.magnitude)

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
		print('     no sourcemeter available. exiting.')
		exit()
	else:
		print('     Keithley connected.')

	SOURCEMETER.set_current_compliance(Q_(8e-3, 'A'))
	bring_to_breakdown(SOURCEMETER, Vbd)

	# Start with dark measurements
	if which_measurement=="Dark":
		try:
			max_bias # check if defined
		except:  # if not defined calculate bias vector based on overbias percentage
			max_bias = (max_overbias/100.0+1.0) * Vbd

			num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included
			vec_overbias = Vbd + Vbd/100 * np.linspace(0, max_overbias, num = num_measures)

		vec_overbias = np.linspace(Vbd, max_bias, num = num_measures)
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

		dark_data = np.genfromtxt(dark_fname, delimiter=',', skip_header=1, comments='#') # skip_footer=1
		# print(dark_data)
		vec_overbias = Q_(dark_data[:,0], 'V')
		num_measures = len(vec_overbias)
	else:
		print('Choose Dark or Light for which_measurement, currently: {}'.format(which_measurement))
		exit()


	count_avg_measurements = []
	count_std_measurements = []
	tap_avg_measurements = []
	tap_std_measurements = []

	print('Performing {} measurement...'.format(which_measurement))

	for i in range(num_measures): # loop through biases
		print('\n{} out of {}'.format(i+1, num_measures))
		SOURCEMETER.set_voltage(vec_overbias[i])
		time.sleep(bias_settle_time)

		counts = []
		counts_std = []
		power = []
		power_std = []

		for Vthresh in thresholds:
			print('     Counting at Vth = {} V'.format(Vthresh))
			# if len(counts)>1 and counts[-1]==0.0:
			# 	# skip measurement for speed up if lower threshold has no counts
			# 	print('     Skipping threshold {} V'.format(Vthresh))
			# 	measured = [0.0, 0.0, measured[2], measured[3]]
			# else:
			measured = take_measure(COUNTER, POWERMETER, Vthresh, integration_time, reps)

			counts.append(measured[0])
			counts_std.append(measured[1])
			power.append(measured[2])
			power_std.append(measured[3])

			if which_measurement=="Light":
				# Set dark counts according to current Vthreshold
				try:
					dark_counts= dark_data[:,thresholds.index(Vthresh)+1].reshape((num_measures,1))
				except:
					print('Dark and light measurement thresholds do not match')
					dark_counts= dark_data[:,1].reshape((num_measures,1))
					print('using dark count data {}'.format(dark_counts))

				act_power = power[-1]*tap_to_incident
				for nd_filter in nd_cfg: # attenuate
					act_power = act_power*nd_filters[nd_filter]
				inc_cps = act_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))
				pdpp = np.divide((counts[-1]-dark_counts[i]), inc_cps, where=inc_cps!=0)

				print('     	Counts: {:.4g} std {:.4g}, dark cps: {:.4g}, pdp={:.4g}'.format(measured[0], measured[1], dark_counts[i][0], pdpp[0]))
				print('     		Tap Power avg: {:.4g}, std: {:.4g} W'.format(measured[2], measured[3]))
				print('     		Incident pwr: {:.4g}, cps={:.4g}'.format(act_power, inc_cps))
			else:
				print('     Counts: {:.4g} std {:.4g}, Power avg: {:.4g}, Power std: {:.4g}'.format(measured[0], measured[1], measured[2], measured[3]))

		count_avg_measurements.append(counts)
		count_std_measurements.append(counts_std)
		tap_avg_measurements.append(power)
		tap_std_measurements.append(power_std)

	# convert to numpy array
	count_avg_measurements = np.array(count_avg_measurements)
	count_std_measurements = np.array(count_std_measurements)
	tap_avg_measurements = np.array(tap_avg_measurements)
	tap_std_measurements = np.array(tap_std_measurements)

	# print(count_measurements)
	print('Measurement finished...')

	# Save results
	if which_measurement == "Dark":
		header = 'Bias [V],'+','.join(
			['cps @ vth={}'.format(vth) for vth in thresholds] +
			['cps std @ vth={}'.format(vth) for vth in thresholds])
		data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_avg_measurements, count_std_measurements), axis=1)
		# print(data_out)
		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")
	elif which_measurement == "Light":
		dark_counts_avg = dark_data[:,1:len(thresholds)+1] # skip bias column
		dark_counts_std = dark_data[:,len(thresholds)+1:2*len(thresholds)+1] # skip bias column
		print('Checking shape of arrays: dark - {}, light- {}'.format(dark_counts_avg.shape, count_avg_measurements.shape))

		# compute things
		actual_power = tap_avg_measurements*tap_to_incident
		# print(tap_to_incident)
		for nd_filter in nd_cfg: # attenuate
			actual_power = actual_power*nd_filters[nd_filter]
		inc_cps = actual_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))
		inc_std = tap_to_incident/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))*tap_std_measurements

		sig_avg =count_avg_measurements-dark_counts_avg
		sig_std = np.sqrt(count_std_measurements**2+dark_counts_std**2)

		pdp = np.divide(sig_avg, inc_cps, out=np.zeros_like(inc_cps), where=inc_cps!=0.0)
		pdp_std = np.abs(pdp) * np.sqrt((np.divide(sig_std, sig_avg, out=np.zeros_like(sig_avg), where=sig_avg!=0.0))**2+(np.divide(inc_std, inc_cps, out=np.zeros_like(inc_cps), where=inc_cps!=0)**2)) # assumes covariance is 0

		# Assemble data
		header = 'Bias [V],'+','.join(
			['cps @ vth={}'.format(vth) for vth in thresholds] +
			['cps std @ vth={}'.format(vth) for vth in thresholds] +
			['Tap power avg[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Tap power std[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Actual power[W] @ vth={}'.format(vth) for vth in thresholds] +
			['Incident cps @ vth={}'.format(vth) for vth in thresholds] +
			['PDP @ vth={}'.format(vth) for vth in thresholds] )

		experiment_info = experiment_info + '; {}nm'.format(wavelength.magnitude) + '; Dark count data {}'.format(dark_fname)

		data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_avg_measurements, count_std_measurements, tap_avg_measurements, tap_std_measurements, actual_power, inc_cps, pdp), axis=1)

		#print(data_out)
		np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")

		(bias_max, th_max) = np.unravel_index(np.argmax(pdp), pdp.shape)
		maxpdp = 'Max PDP={:.4g}% at {:.4g}V Bias and {:.4g} mV Threshold, DCR={:.4g}'.format(np.max(pdp)*100, vec_overbias.magnitude[bias_max], thresholds[th_max]*1000, dark_counts_avg[bias_max, th_max])
		print(maxpdp)

		fig, ax1 = plt.subplots(1,1, figsize=(3.5,2.5), dpi=300)
		ax1.set_title(maxpdp)

		for i in range(len(thresholds)):
		    ax1.errorbar(vec_overbias.magnitude, pdp[:,i]*100, yerr=pdp_std[:,i], linewidth=0.5, elinewidth=0.2, capsize=1.5) # , ecolor='blue') #, fmt='.-')uplims=True, lolims=True
		# ax1.set_yscale('log')

		ax1.set_xlabel('Reverse Bias [V]')
		ax1.set_ylabel('PDP [%]')

		ax1.set_ylim(bottom = 0, top=np.min([100, 2*np.max(pdp*100)]))

		ax1.legend(['$V_{{th}}$={:g} mV'.format(vth*1000) for vth in thresholds])
		ax1.grid(True, which='both', linestyle=':', linewidth=0.3)
		plt.savefig(imgname+'-PDP.png', dpi=300, bbox_inches='tight')


	bring_down_from_breakdown(SOURCEMETER, Vbd)
	COUNTER.display = 'ON'

	fig, ax1 = plt.subplots(1,1)
	ax1.set_title("\n".join(wrap('Counts '+experiment_info, 60)))
	# plt.semilogy(vec_overbias.magnitude, count_avg_measurements, 'o-') # plot first threshold data
	for i in range(len(thresholds)):
		ax1.errorbar(vec_overbias.magnitude, count_avg_measurements[:,i], yerr=count_std_measurements[:,i], linewidth=0.5, elinewidth=0.2, capsize=1.5)
	ax1.set_yscale('log')
	ax1.legend(['$V_{{th}}$={:g} mV'.format(vth*1000) for vth in thresholds])

	# plt.semilogy(vec_overbias.magnitude, count_measurements[:,0], 'o-', label='Light') # plot first threshold data
	# if which_measurement == 'Light':
	# 	plt.semilogy(vec_overbias.magnitude, dark_counts[:,0], 'o-', label='Dark') # plot first threshold data
	# 	plt.legend()

	ax1.set_xlabel('Bias [V]')
	ax1.set_ylabel('Counts [cps]')
	ax1.grid(True, which='both', linestyle=':', linewidth=0.3)
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

def take_measure(COUNTER, POWERMETER, Vthresh, integration_time, reps=1):
	'''
		Collect counts during integration_time and measures power

		Input Parameters:
		COUNTER: frequency counter object
		POWERMETER: powermeter object
		Vthres: threshold voltage for frequency counter

		Returns: (cps, int_power)
		cps: counts per second as pint.Measurement object
		power: average optical power during measurement returned as pint.Measurement object
	'''
	with visa_timeout_context(COUNTER._rsrc, 60000): # timeout of 60,000 msec
		COUNTER.Vthreshold = Q_(Vthresh, 'V')
		# COUNTER.set_mode_totalize(integration_time=integration_time)

		powers = []
		counts = []
		for i in range(reps):
			COUNTER.write('INIT') # Initiate counting
			COUNTER.write('*WAI')

			if POWERMETER is not None:
				power = POWERMETER.measure(n_samples = int(integration_time/0.003)) # each sample about 3ms
			else:
				power = Q_(0.0, 'W').plus_minus(Q_(0.0, 'W'))
			num_counts = float(COUNTER.query('FETC?'))

			cps = num_counts/integration_time

			powers.append(power.value.magnitude)
			counts.append(cps)

	return (np.mean(counts), np.std(counts), np.mean(powers), np.std(powers))

def take_measures(COUNTER, POWERMETER, Vthresh, integration_time, reps):
	'''
		Collect counts during integration_time and measures power with multiple repetitions

		Input Parameters:
		COUNTER: frequency counter object
		POWERMETER: powermeter object
		Vthres: threshold voltage for frequency counter

		Returns: (cps, int_power)
		cps: counts per second as pint.Measurement object
		power: average optical power during measurement returned as pint.Measurement object
	'''
	with visa_timeout_context(COUNTER._rsrc, 60000): # timeout of 60,000 msec
		COUNTER.Vthreshold = Q_(Vthresh, 'V')
		COUNTER.set_mode_totalize(integration_time=integration_time)

		powers = []
		counts = []
		for i in range(reps):
			COUNTER.write('INIT') # Initiate counting
			COUNTER.write('*WAI')

			if POWERMETER is not None:
				power = POWERMETER.measure(n_samples = int(integration_time/0.003)) # each sample about 3ms
			else:
				power = Q_(0.0, 'W').plus_minus(Q_(0.0, 'W'))
			num_counts = float(COUNTER.query('FETC?'))

			cps = num_counts/integration_time

			powers.append(power.value.magnitude)
			counts.append(cps)

	return (cps, power)

if __name__ == '__main__':
	start = time.time()

	main()

	print('Experiment took {}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()-start))))

	try:
	    import winsound
	    winsound.Beep(1500, 1000)
	except:
	    print('winsound not available no beeping')
