'''
Script for collecting a given number of interarrival times from Keysight 53220A
which_measurement variable can be specified for dark or light measurements

Instruments:
	Frequency counter Keysight 53220A
    SMU Keithley 2400
	Thorlabs PM100A power meter

Description
	1) Collects a given number of interarrival times from Keysight 53220A
	2) Save data under ./output folder

'''


# from utils import *
import sys
import numpy as np
from scipy.optimize import curve_fit
import time
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter
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
	# fname = 'TC1_W12-14_PD6D-16um'
	# fname = 'TC1_W12-7_PD6D-12um-9K11p5um'
	# fname ='TC1_W12-14_PD6D-12um-9K10um'
	fname ='TC1_W12-14_PD4A-16um'

	which_measurement = "itimes"
	if len(sys.argv) > 1:
		illum = sys.argv[1]
	else:
		illum = "Dark" # "Dark" or "Light"

	# input_file = './output/20200704_165548-TC1_W13-34_PD4A-16um-Dark.csv'
	input_file = None
	# input_file = './output/20210312_204949-TC1_W12-35_PD6D-16um-interarrival_histogram.csv'
	# input_file = './output/20200704_194025-TC1_W13-34_PD4A-16um-Dark.csv'
	pqc = "pcb" # "pcb" or "chip"


	# device = 'PD6D-zoom'
	# device = 'PD6D-12um-9K'
	# device = 'PD6D-16um-50'
	# device = 'PD6D-16um'
	# device = 'test'
	device = 'PD4A-12um'
	exp_setting = {
	# device: Vbd, max bias, num of points, number of samples, threshold]
		'PD6D': [Q_(24, 'V'), Q_(28.8, 'V'), 21, 1000, -0.05],
		'PD6D-wide': [Q_(24, 'V'), Q_(28.8, 'V'), 21, 1000, -0.05],
		'PD6D-4um': [Q_(30.0, 'V'), Q_(36.0, 'V'), 21, 1000, -0.05],
		'PD6D-12um': [Q_(24.5, 'V'), Q_(26.95, 'V'), 21, 10000, -0.05],
		'PD6D-16um': [Q_(25.5, 'V'), Q_(25.7, 'V'), 21, 10000, -0.05],
		'PD6D-16um-50': [Q_(25.5, 'V'), Q_(25.7, 'V'), 21, 10000, -0.020],
		'PD6D-12um-9K': [Q_(25.9, 'V'), Q_(26.9, 'V'), 21, 10000, -0.05],
		'PD4A': [Q_(33.5, 'V'), Q_(40.2, 'V'), 21, 1000, -0.05],
		'PD4A-12um': [Q_(35.0, 'V'), Q_(37.0, 'V'), 21, 10000, -0.05],
		'test': [Q_(25, 'V'), Q_(25.5, 'V'), 2, 1000, -0.05],
	}

	Vbd = exp_setting[device][0]
	max_bias = exp_setting[device][1]
	num_measures = exp_setting[device][2]
	# max_overbias = exp_setting[device][1]
	# step_overbias = exp_setting[device][2]
	num_samples = exp_setting[device][3]
	threshold = exp_setting[device][4]

	# # for testing
	if False:
		which_measurement = "interarrival"
		illum = 'Light' # "Dark" or "Light"
		Vbd = Q_(1.0, 'V') # [V]
		max_overbias = 10.0 # [%]
		step_overbias = 5.0 # [%] Each step 1% more overbias
		integration_time = 1.0 # sec
		bias_settle_time = 1.0 # sec

		num_samples = 1000



	try:
		max_bias # check if defined
	except:  # if not defined calculate bias vector based on overbias percentage
		max_bias = (max_overbias/100.0+1.0) * Vbd
		num_measures = int(max_overbias/step_overbias) + 1 # 0% and max_overbias% included

	if pqc=='chip':
		if max_bias > Q_(2.5, 'V'):
			print('Adjusting max bias from {} to {} to protect on chip quench circuit'.format(max_bias, Vbd+Q_(2.5, 'V')))
			max_bias = Q_(2.5, 'V')+Vbd

	if illum == "Dark":
		vec_overbias = np.linspace(Vbd, max_bias, num = num_measures)
	elif illum == "Light":
		# load latest dark measurements
		import glob
		# get latest Dark count data file name
		try:
			dark_fname = glob.glob('./output/*'+fname+'*-Dark.csv')[-1]
		except:
			print('Dark results not available, run Dark measurement first.')
			exit()
		else:
			print(dark_fname)

		dark_data = np.genfromtxt(dark_fname, delimiter=',', skip_header=1, comments='#') # skip_footer=1
		# print(dark_data)
		vec_overbias = Q_(dark_data[0,:], 'V')
		num_measures = len(vec_overbias)
		# get fitted dark counts
		dark_data = np.genfromtxt(dark_fname[:-4]+'-fit.csv', delimiter=',', skip_header=1, comments='#') # skip_footer=1
		dcr_vec = dark_data[2,:]

	else:
		print('Choose Dark or Light for illum, currently: {}'.format(illum))
		exit()


	bias_settle_time = 5.0 # sec
	integration_time = 1.0

	# Frequency counter settings
	# num_samples = 1000
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	Zin=  50.0 #1.0e6 # 50.0

	reps = 10
	if illum =='Dark':
		experiment_info = '# Dark {}; Number of samples: {}; slope {}; threshold {} V; Zin={}; Max Bias {:.4g}; bias settle time {} sec'.format(which_measurement, num_samples, slope, threshold,Zin,  max_bias.magnitude, bias_settle_time)
	elif illum == 'Light':
		experiment_info = '# Light {}; Dark data {}; Number of samples: {}; slope {}; threshold {} V; Zin={}; Max Bias {:.4g}; bias settle time {} sec'.format( which_measurement, dark_fname, num_samples, slope, threshold, Zin, max_bias.magnitude, bias_settle_time)


	# Filenames
	if input_file is None:
		timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
		rawcsvname = './output/'+timestamp_str+ fname+'-{}-{}.csv'.format(which_measurement, illum)
		csvname = './output/'+timestamp_str+ fname+'-{}-{}-fit.csv'.format(which_measurement, illum)
		imgname = './output/'+timestamp_str+ fname+ '-{}-{}'.format(which_measurement, illum)
	else:
		csvname = input_file
		imgname = input_file[0:-4]
		print(imgname)
	temperature = 25.0


	target_wavelength = 830
	# power_measurement = np.genfromtxt('./output/850-cal-20210311.csv', delimiter=',', skip_header=1)
	# power_measurement = np.genfromtxt('./output/nd-cal/{}-od0.csv'.format(target_wavelength), delimiter=',', skip_header=1)
	power_file = './output/20210430 830nm PDP/830-od0.csv'
	power_measurement = np.genfromtxt(power_file, delimiter=',', skip_header=1)
	wavelength = Q_(float(np.round(power_measurement[0], decimals=1)), 'nm')
	print(wavelength)
	tap_to_incident = power_measurement[5]

	# ND filter calibration values -
	nd_cfg = ["od5-1", "od4-1",   "od4-2"] # "od5-2"]
	if illum=="Light":
		experiment_info = experiment_info + '; ND filters: {}'.format(nd_cfg)
	try:
		pickle_in = open("nd_cal.pickle", "rb")
		target_wavelength, nd_filters = pickle.load(pickle_in)
		print('nd_filter calibration values loaded from nd_cal.pickle')
		print(nd_filters)
	except:
		nd_cal_dir = './output/nd-cal/'

		print('No ND calibration value pickle file, generating from csv data set in {}'.format(nd_cal_dir))

		nd_filters = {
			#"NE10B": 0,
			#"NE20B": 0,
			#"NE30B": 0,
			# "NE40B": 0,
			# "NE50A-A": 0,
			# 'od4': 0,
			# 'od5': 0,

			'od4-1': 0,
			'od5-1': 0,
			'od4-2': 0,
			'od5-2': 0,
		}

		Pi = np.genfromtxt(nd_cal_dir+'{}-od0.csv'.format(target_wavelength), delimiter=',', skip_header=1)
		for (filter, value) in nd_filters.items():
			Po = np.genfromtxt(nd_cal_dir+'{}-'.format(target_wavelength)+filter+'.csv', delimiter=',', skip_header=1)

			# use coefficient to adjust for power fluctuations
			nd_filters[filter] = Po[5]/Pi[5]

		pickle_out = open("nd_cal.pickle", "wb")
		pickle.dump([target_wavelength, nd_filters], pickle_out)
		pickle_out.close()
	else:
		print('ND calibration values loaded from nd_cal.pickle file')
		# print(nd_filters)



	if input_file is None:
		# Global instrument variables
		COUNTER = None
		SOURCEMETER = None
		POWERMETER = None

		address_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
		address_POWERMETER = 'USB0::0x1313::0x8079::P1001951::INSTR'
		address_SOURCEMETER = 'GPIB0::15::INSTR'
		#---------------------------------------------------------------------------------------

		# Initialize tap Power meter
		try:
			from instrumental.drivers.powermeters.thorlabs import PM100A

			POWERMETER = PM100A(visa_address=address_POWERMETER)
		except:
			print('    no powermeter available. exiting.')
			POWERMETER=None
		else:
			print('    powermeter opened')
			POWERMETER.wavelength = wavelength
			print('    powermeter wavelength set to {}'.format(wavelength))
			POWERMETER.auto_range = 1

		# initialize counter
		try:
			from instrumental.drivers.frequencycounters.keysight import FC53220A
			COUNTER = FC53220A(visa_address=address_COUNTER)
		except:
			print('no frequency counter available. exiting.')
			# exit()
		else:
			print('frequency counter connected.')
			COUNTER._rsrc.timeout = num_samples*60
			COUNTER.set_mode_single_period(num_counts = num_samples)
			COUNTER.coupling = 'DC'
			if pqc == "pcb":
				print('pcb pqc setting to {}Ohm'.format(Zin))
				COUNTER.impedance = Q_(Zin, 'ohm')
			elif pqc == "chip":
				print('on chip pqc setting to 1MOhm')
				COUNTER.impedance = Q_(1e6, 'ohm')
			COUNTER.slope = 'NEG'
			COUNTER.Vthreshold = Q_(threshold,'V')

			temperature = COUNTER.temp
			print('temp is {}'.format(temperature))
			experiment_info = experiment_info + '; T={} C'.format(temperature.magnitude)

			COUNTER.timeout = 100.0
			COUNTER.display = 'OFF'

		# # initialize source meter
		# try:
		# 	from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
		# 	SOURCEMETER = Keithley_2400(visa_address=address_SOURCEMETER)
		# except:
		# 	print('no sourcemeter available. exiting.')
		# 	# exit()
		# else:
		# 	print('Keithley connected.')
		# 	SOURCEMETER.set_current_compliance(Q_(8e-3, 'A'))

		try:
			from instrumental.drivers.sourcemeasureunit.hp import HP_4156C
			SOURCEMETER = HP_4156C(visa_address='GPIB0::17::INSTR')
		except:
			print('no sourcemeter available. exiting.')
			exit()
		else:
			print('HP opened')
			SOURCEMETER.set_channel(channel=2)


		# perform measurement
		bring_to_breakdown(SOURCEMETER, Vbd)

		print('Performing {} samples interarrival time measurement on {}...'.format(num_samples, fname))

		raw_data_array = []
		tap_power_vec = []
		act_power_vec = []
		inc_cps_vec = []
		pap_vec = []
		cr_vec = []


		for i in range(num_measures): # loop through biases
			print('\n{} out of {}'.format(i+1, num_measures))
			SOURCEMETER.set_voltage(vec_overbias[i])
			time.sleep(bias_settle_time)
			# try:
			power_arr = []
			print('Counting interarrival times')
			COUNTER.write('INIT:IMM') # Initiate the measurements

			# Take power meter measurements
			measuring = True
			while measuring:
				if POWERMETER is not None:
					power_arr.append( POWERMETER.measure(n_samples = int(integration_time/0.003)) )# each sample about 3ms
				else:
					power_arr.append( Q_(0.0, 'W').plus_minus(Q_(0.0, 'W')) )

				status = int(COUNTER.query('STAT:OPER:COND?'))
				if status & (1<<4) == 0:
					measuring = False
					print(power_arr)
					if len(power_arr) > 1:
						# If more than one measurement take statistics across multiple measurements
						power_mag_arr = np.array([x.value.magnitude for x in power_arr])
						power = Q_(np.mean(power_mag_arr)).plus_minus(np.std(power_mag_arr))
					else:
						power = power_arr[0]
				else:
					print('Counter is still measuring. tap power {}'.format(power_arr[-1]))

			print('Fetching interarrival times')
			time_list = COUNTER.query('FETC?') # Read from counter

			act_power = power.value.magnitude*tap_to_incident
			for nd_filter in nd_cfg: # attenuate
				act_power = act_power*nd_filters[nd_filter]
			inc_cps = act_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))

			# except:
			# 	print("Unexpected error:", sys.exc_info()[0])
			# 	data = None
			# else:

			data = np.array(time_list.split(",")).astype(np.float) # Converts the output string to a float list

			Pap, CR = histogramFit(data, info=imgname+'_{:.3e}V'.format(vec_overbias[i].magnitude))
			print('Fitted CR: {:.4g}, Pap={:.4g}%\n'.format(CR, Pap*100) \
				+ 'at Bias={:.4g}V and Threshold={:.4g}V'.format(vec_overbias[i].magnitude, threshold))

			raw_data_array.append(data)
			tap_power_vec.append(power.value.magnitude)
			act_power_vec.append(act_power)
			inc_cps_vec.append(inc_cps)
			pap_vec.append(Pap)
			cr_vec.append(CR)


		print('Measurement finished...')

		print(np.array(pap_vec).shape)
		print(np.array(cr_vec).shape)
		print(np.array(vec_overbias.magnitude).shape)

		# Save results to csvname
		pwr_array = np.array([tap_power_vec, act_power_vec, inc_cps_vec])
		print('power array shape {}'.format(pwr_array.shape))

		bias_arr = np.array(vec_overbias.magnitude)
		count_arr = np.array(cr_vec)
		if illum == 'Dark':
			output_array = np.vstack((bias_arr, np.array(pap_vec), count_arr))
		elif illum == "Light":
			pdp_array = (count_arr - dcr_vec) / pwr_array[2, :]
			output_array = np.vstack((bias_arr, np.array(pap_vec), count_arr, pwr_array, pdp_array))
		np.savetxt(csvname, output_array, delimiter=',', header=experiment_info, comments="#")


		output_array = np.vstack((np.array([vec_overbias.magnitude]), pwr_array, np.array(raw_data_array).T))

		print('interrarrival time output array shape {}'.format(output_array.shape))
		np.savetxt(rawcsvname, output_array, delimiter=',', header=experiment_info, comments="#")

		bring_down_from_breakdown(SOURCEMETER, Vbd)
		COUNTER.display = 'ON'

	else:
		print('Loading previous data from '+input_file)
		try:
			data = np.genfromtxt(input_file, delimiter=',', skip_header=1)
		except:
			print("Unexpected error:", sys.exc_info()[0])
			data = None


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
    time.sleep(1.0)
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

def histogramFit(data, bin_borders=None, info=''):
	num_samples = len(data)
	if bin_borders is None:
		N, bin_borders = np.histogram(data, bins=500)
	else:
		N, bin_borders = np.histogram(data, bins=bin_borders)
	bin_center = bin_borders[:-1] + np.diff(bin_borders) / 2

	print('Removing zero data points for plot and fit')

	N_fit = N[N>0]
	bin_centers = bin_center[N>0]

	bounds = ([0.0, 0.0, 1.0], [1.e9, 1.e9, 1.001])
	p0 = [1/np.mean(data), N[1], 1.0]

	ap_index = 0
	max_index = num_samples
	print(max_index)

	min_err = 1e9
	min_index = 0

	log_exp = lambda t, CR, A, d: np.log10(A* np.exp(-CR*t)+d)
	single_exp = lambda t, CR, A, d: A* np.exp(-CR*t)+d
	for ap_index in range(1, 10,1):
		# final fit excluding afterpulses are in first bin
		popt, pcov = curve_fit(log_exp, bin_centers[ap_index:max_index], np.log10(N_fit[ap_index:max_index]), p0=p0, bounds=bounds)
		perr = np.sqrt(np.diag(pcov))

		if perr[0]/popt[0]<min_err: # and perr[0]<90.0:
			min_err = perr[0]/popt[0]
			min_index = ap_index
			CR = popt[0]
			min_popt = popt
			print('abs err {}, prop err {}, CR {}, freq {} Hz'.format(perr[0], min_err, CR, bin_center[ap_index]))

	ap_index = min_index
	print('afterpulses included before {}'.format(ap_index))
	Pap = np.sum(N[0:ap_index])/num_samples
	print('Pap from histogram = {:.4g}%'.format(Pap*100))
	print('CR = {:.4g}'.format(CR))


	# plt.figure(figsize=(3.5,2.5), dpi=300)
	f, ax = plt.subplots()
	# plt.title('Interarrival Histogram {}'.format(info))
	plt.title('Interarrival Histogram {}'.format(info[-10:]))

	formatter0 = EngFormatter()
	prefix = formatter0.format_eng(bin_center[-1])[-1]
	# formatter0 = StrMethodFormatter("{x:.1e}")
	ax.xaxis.set_major_formatter(formatter0)
	ax.set_xlabel('Interarrival time (s)')
	ax.set_ylabel('Counts per bin')
	ax.semilogy(bin_center, single_exp(bin_center, *min_popt), label='Fit: {:.3g} cps'.format(min_popt[0]), color='#5e89b7')
	ax.semilogy(bin_center, N, label='Data', linewidth=0.5, alpha=0.5, color='#5e89b7')
	ax.set_ylim([0.1, np.max(N)*10])
	ax.legend()

	# plt.show(block=False)
	plt.savefig(info+'.png')

	return Pap, CR

if __name__ == '__main__':
	start = time.time()

	main()

	print('Experiment took {}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()-start))))

	try:
		import winsound

		winsound.Beep(1500, 1000)
		# plt.show()

	except:
		print('winsound not available no beeping')
