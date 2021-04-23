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
	fname = 'TC1_W12-14_PD6D-16um'
	# fname = 'TC1_W12-7_PD6D-12um-9K11p5um'
	# fname ='TC1_W12-14_PD6D-12um-9K10um'

	which_measurement = "Pap"
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
	device = 'PD6D-16um-50'
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
		'test': [Q_(25.5, 'V'), Q_(25.8, 'V'), 4, 1000, -0.05],
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
			dark_fname = glob.glob('./output/*'+fname+'-Dark.csv')[-1]
		except:
			print('Dark results not available, run Dark measurement first.')
			exit()
		else:
			print(dark_fname)

		dark_data = np.genfromtxt(dark_fname, delimiter=',', skip_header=1, comments='#') # skip_footer=1
		# print(dark_data)
		vec_overbias = Q_(dark_data[:,0], 'V')
		num_measures = len(vec_overbias)
	else:
		print('Choose Dark or Light for illum, currently: {}'.format(illum))
		exit()


	bias_settle_time = 5.0 # sec
	integration_time = 1.0

	# Frequency counter settings
	# num_samples = 1000
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	Zin=  50 #1.0e6 # 50.0

	reps = 10

	experiment_info = '# {}; Number of samples: {}; slope {}; threshold {} V; Zin={}; Max Bias {:.4g}; bias settle time {} sec'.format(which_measurement, num_samples, slope, Zin, threshold, max_bias.magnitude, bias_settle_time)


	# Filenames
	if input_file is None:
		timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
		rawcsvname = './output/'+timestamp_str+ fname+'-{}-{}-intertimes.csv'.format(which_measurement, illum)
		csvname = './output/'+timestamp_str+ fname+'-{}-{}-fitted.csv'.format(which_measurement, illum)
		imgname = './output/'+timestamp_str+ fname+ '-{}-{}'.format(which_measurement, illum)
	else:
		csvname = input_file
		imgname = input_file[0:-4]
		print(imgname)
	temperature = 25.0


	# power_measurement = np.genfromtxt('./output/850-cal-20210311.csv', delimiter=',', skip_header=1)
	power_measurement = np.genfromtxt('./output/nd-cal/830-od0.csv', delimiter=',', skip_header=1)
	wavelength = Q_(float(np.round(power_measurement[0], decimals=1)), 'nm')
	print(wavelength)
	tap_to_incident = power_measurement[5]

	# ND filter calibration values -
	nd_cfg = ["od5", "od4"]
	if illum=="Light":
		experiment_info = experiment_info + '; ND filters: {}'.format(nd_cfg)
	try:
		pickle_in = open("nd_cal.pickle", "rb")
		nd_filters = pickle.load(pickle_in)
	except:
		nd_cal_dir = './output/nd-cal/'

		print('No ND calibration value pickle file, generating from csv data set in {}'.format(nd_cal_dir))

		nd_filters = {
			"wavelength": 830,
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

		Pi = np.genfromtxt(nd_cal_dir+'{}-od0.csv'.format(nd_filters["wavelength"]), delimiter=',', skip_header=1)
		for (filter, value) in nd_filters.items():
			Po = np.genfromtxt(nd_cal_dir+'{}-'.format(nd_filters["wavelength"])+filter+'.csv', delimiter=',', skip_header=1)

			# use coefficient to adjust for power fluctuations
			nd_filters[filter] = Po[5]/Pi[5]

		pickle_out = open("nd_cal.pickle", "wb")
		pickle.dump(nd_filters, pickle_out)
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
			experiment_info = experiment_info + ', T={} C'.format(temperature.magnitude)

			COUNTER.timeout = 100.0
			COUNTER.display = 'OFF'

		# initialize source meter
		try:
			from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
			SOURCEMETER = Keithley_2400(visa_address=address_SOURCEMETER)
		except:
			print('no sourcemeter available. exiting.')
			# exit()
		else:
			print('Keithley connected.')
			SOURCEMETER.set_current_compliance(Q_(8e-3, 'A'))


		# perform measurement
		bring_to_breakdown(SOURCEMETER, Vbd)

		print('Performing {} samples interarrival time measurement on {}...'.format(num_samples, fname))

		raw_data_array = []
		pap_vec = []
		dcr_vec = []


		for i in range(num_measures): # loop through biases
			print('\n{} out of {}'.format(i+1, num_measures))
			SOURCEMETER.set_voltage(vec_overbias[i])
			time.sleep(bias_settle_time)
			try:
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
						power = np.mean(power_arr).plus_minus(np.std(power_arr))
					else:
						print('Counter is still measuring')

				print('Fetching interarrival times')
				time_list = COUNTER.query('FETC?') # Read from counter

				act_power = power.value.magnitude*tap_to_incident
				for nd_filter in nd_cfg: # attenuate
					act_power = act_power*nd_filters[nd_filter]
				inc_cps = act_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))

			except:
				print("Unexpected error:", sys.exc_info()[0])
				data = None
			else:
			# 	# time_list = np.genfromtxt('./output/20210314 TC1-W12-14 PD6D 16um light interarrival/20210314_215837-TC1_W12-14_PD6D-16um-interarrival_histogram.csv')
				data = np.array(time_list.split(",")).astype(np.float) # Converts the output string to a float list

				Pap, DCR = histogramFit(data)
				print('Fitted DCR: {:.4g}, Pap={:.4g}%\n'.format(DCR, Pap*100) \
					+ 'at Bias={:.4g}V and Threshold={:.4g}V'.format(vec_overbias[i].magnitude, threshold))

				raw_data_array.append(data)
				pap_vec.append(Pap)
				dcr_vec.append(DCR)


		print('Measurement finished...')

		# print(np.array(pap_vec).shape)
		# print(np.array(dcr_vec).shape)
		# print(np.array(vec_overbias.magnitude).shape)
		# Save results to csvname
		output_array = np.vstack((np.array(vec_overbias.magnitude), np.array(pap_vec), np.array(dcr_vec)))
		np.savetxt(csvname, output_array, delimiter=',', header=experiment_info, comments="#")

		output_array = np.hstack((np.array([vec_overbias.magnitude]).T, np.array(raw_data_array)))
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

	# Parameter fit
	if data is not None:
		# Histogram method
		plt.figure()
		N, bin_borders, patches = plt.hist(data, bins=1000, label='Data') # Try: Calculate the apropiate num of bins from data
		bin_center = bin_borders[:-1] + np.diff(bin_borders) / 2
		plt.xlabel('Interarrival time [s]')
		plt.ylabel('Counts per bin')


		# poisson = lambda k, A, euler: euler**k *  np.exp(-euler) / np.factorial(k)
		single_exp = lambda t, DCR, A: A* np.exp(-DCR*t)
		bounds = (0, [1.e9, 1.e9])
		p0 = [1/np.mean(data), N[1]]

		Nshift = np.roll(N, -1)
		ap_index = max(1, (N>Nshift+num_samples/100).argmin())
		print('afterpulses included before {}'.format(ap_index))
		Pap = np.sum(N[0:ap_index])/num_samples
		print('Pap from histogram = {:.4g}%'.format(Pap*100))
		# final fit excluding afterpulses are in first bin
		popt, pcov = curve_fit(single_exp, bin_center[ap_index:], N[ap_index:], p0=p0, bounds=bounds)


		plt.plot(bin_center[1:]*1e3, single_exp(bin_center[1:], *popt), label='Fit')
		plt.yscale('log')
		plt.title("\n".join(wrap('Interarrival time Histogram for {}\n'.format(fname) \
			+ 'Fitted DCR: {:.4g}, Pap={:.4g}%\n'.format(popt[0], Pap*100) \
			+ 'at Bias={:.4g}V and Threshold={:.4g}V'.format(Vbd.magnitude, threshold), 60)))
		plt.legend()
		plt.xlabel('Interarrival Time [ms]')

		plt.savefig(imgname+'-Histogram.png', dpi=300, bbox_inches='tight')

		fig,ax = plt.subplots(2,1, figsize=(15,10))
		ax[0].set_title('Bias vs $P_{ap}$'+' and DCR Plot for {}'.format(fname))
		ax[0].plot(vec_overbias.magnitude, np.array(pap_vec)*100)
		ax[0].set_xlabel('Bias [V]')
		ax[0].set_ylabel('$P_{ap}$ [%]')

		# ax[1].set_title('Primary DCR Bias dependence')
		ax[1].plot(vec_overbias.magnitude, np.array(dcr_vec))
		ax[1].set_xlabel('Bias [V]')
		ax[1].set_ylabel('Primary DCR [Hz]')
		ax[1].set_yscale('log')

		plt.savefig(imgname+'-fitted.png'.format(illum), dpi=300, bbox_inches='tight')




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

def histogramFit(data):
	num_samples = len(data)
	hist, bin_borders = np.histogram(a=data, bins=1000)
	bin_center = bin_borders[:-1] + np.diff(bin_borders) / 2

	single_exp = lambda t, DCR, A: A* np.exp(-DCR*t)
	bounds = (0, [1.e9, 1.e9])
	p0 = [1/np.mean(data), hist[1]]

	histShift = np.roll(hist, -1)
	ap_index = max(1, (hist>histShift+num_samples/100).argmin())
	print('afterpulses included before {}, afterpulse rate {:.4g}'.format(ap_index, 1/bin_center[ap_index]))
	Pap = np.sum(hist[0:ap_index])/num_samples
	# print('Pap from histogram = {:.4g}%'.format(Pap*100))
	# final fit excluding afterpulses are in first bin
	popt, pcov = curve_fit(single_exp, bin_center[ap_index:], hist[ap_index:], p0=p0, bounds=bounds)

	DCR = popt[0]

	return Pap, DCR

if __name__ == '__main__':

	start = time.time()

	main()

	print('Experiment took {}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()-start))))

	try:
	    import winsound
	    winsound.Beep(1500, 1000)
	except:
	    print('winsound not available no beeping')
