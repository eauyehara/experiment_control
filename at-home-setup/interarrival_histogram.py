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
	fname = 'TC1_W12-35_PD4A-16um'

	which_measurement = "Dark" # "Dark" or "Light"
	# input_file = './output/20200704_165548-TC1_W13-34_PD4A-16um-Dark.csv'
	input_file = None
	# input_file = './output/20200704_194025-TC1_W13-34_PD4A-16um-Dark.csv'
	pqc = "pcb" # "pcb" or "chip"

	Vbd = Q_(34.8, 'V') # Breakdown voltage PD4A-16um 34.8V
	Vbias = Q_(37.8, 'V')
	bias_settle_time = 30.0 # sec

	# Frequency counter settings
	num_samples = 50000
	slope = 'NEG' # Positive('POS')/ Negative('NEG') slope trigger
	threshold = -0.050 # V

	reps = 10

	if pqc=='chip':
		if Vbias > Vbd+Q_(2.5, 'V'):
			print('Adjusting bias from {} to {} to protect on chip quench circuit'.format(Vbias, Vbd+Q_(2.5, 'V')))
			Vbias = Vbd+Q_(2.5, 'V')
	experiment_info = '{}, Number of samples: {}, slope {}, threshold {} V, Bias {:.4g}, bias settle time {} sec'.format(which_measurement, num_samples, slope, threshold, Vbias, bias_settle_time)

# # for testing
	if False:
		which_measurement = "Light" # "Dark" or "Light"
		Vbd = Q_(1.0, 'V') # [V]
		max_overbias = 10.0 # [%]
		step_overbias = 5.0 # [%] Each step 1% more overbias
		integration_time = 1.0 # sec
		bias_settle_time = 1.0 # sec

	# Filenames
	if input_file is None:
		timestamp_str = datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S-')
		csvname = './output/'+timestamp_str+ fname+'-{}.csv'.format(which_measurement)
		imgname = './output/'+timestamp_str+ fname+ '-{}'.format(which_measurement)
	else:
		csvname = input_file
		imgname = input_file[0:-4]
		print(imgname)
	temperature = 25.0


	#
	# # Tap power to Incident Power coefficient
	# power_measurement = np.genfromtxt('./output/Pi-NE10B.csv', delimiter=',', skip_header=1)
	# wavelength = Q_(float(np.round(power_measurement[0])), 'nm')
	# print(wavelength)
	# tap_to_incident = power_measurement[5]



	# Global instrument variables
	COUNTER = None
	SOURCEMETER = None
	POWERMETER = None

	USB_address_COUNTER = 'USB0::0x0957::0x1807::MY50009613::INSTR'
	USB_address_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'
	USB_address_POWERMETER = 'USB0::0x1313::0x8079::P1001951::INSTR'
	GPIB_address_SOURCEMETER = 'GPIB0::15::INSTR'
	#---------------------------------------------------------------------------------------

	# Initialize tap Power meter
	# try:
	# 	from instrumental.drivers.powermeters.thorlabs import PM100A
	# 	POWERMETER = PM100A(visa_address=USB_address_POWERMETER)
	# 	#POWERMETER = PM100A(visa_address='USB0::0x1313::0x8079::P1001951::INSTR')
	# except:
	# 	print('no powermeter available.')
	# 	POWERMETER=None
	# else:
	# 	print('powermeter opened')
	# 	POWERMETER.wavelength = wavelength
	# 	POWERMETER.auto_range = 1
	POWERMETER = None

	# Open the instruments
	# initialize counter
	try:
		from instrumental.drivers.frequencycounters.keysight import FC53220A
		COUNTER = FC53220A(visa_address=USB_address_COUNTER)
	except:
		print('no frequency counter available. exiting.')
		exit()
	else:
		print('frequency counter connected.')
		COUNTER._rsrc.timeout = num_samples*60
		COUNTER.set_mode_single_period(num_counts = num_samples)
		COUNTER.coupling = 'DC'
		if pqc == "pcb":
			print('pcb pqc setting to 50Ohm')
			COUNTER.impedance = Q_(50, 'ohm')
		elif pqc == "chip":
			print('on chip pqc setting to 1MOhm')
			COUNTER.impedance = Q_(1e6, 'ohm')
		COUNTER.slope = 'NEG'

		temperature = COUNTER.temp
		print('temp is {}'.format(temperature))
		experiment_info = experiment_info + ', T={} C'.format(temperature.magnitude)

		COUNTER.display = 'ON'

	# initialize source meter
	try:
		from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
		SOURCEMETER = Keithley_2400(visa_address=GPIB_address_SOURCEMETER)
	except:
		print('no sourcemeter available. exiting.')
		exit()
	else:
		print('Keithley connected.')
		SOURCEMETER.set_current_compliance(Q_(8e-3, 'A'))

	if input_file is None:
		# perform measurement
		bring_to_breakdown(SOURCEMETER, Vbias)
		time.sleep(bias_settle_time)

		print('Performing {} samples interarrival time measurement...'.format(num_samples))
		try:
			COUNTER.write('INIT') # Initiate the measurements
			COUNTER.write('*WAI') # Wait for the measurements to be completed
			time_list = COUNTER.query('FETC?') # Read instrument
		except:
			print("Unexpected error:", sys.exc_info()[0])
			data = None
		else:
			data = np.float_(time_list.split(",")) # Converts the output string to a float list

			print('Measurement finished...')

			# Save raw results
			np.savetxt(csvname, data, delimiter=',', header=experiment_info, comments="")



		bring_down_from_breakdown(SOURCEMETER, Vbias)
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


		plt.plot(bin_center[1:], single_exp(bin_center[1:], *popt), label='Fit')
		plt.title("\n".join(wrap('Interarrvial time Histogram for {}\n'.format(fname) \
			+ 'Fitted DCR: {:.4g}, Pap={:.4g}%\n'.format(popt[0], Pap*100) \
			+ experiment_info, 60)))
		plt.legend()

		plt.savefig(imgname+'-Histogram.png', dpi=300, bbox_inches='tight')


		# Sequence of ranged amplitudes - based on Kramnik's script
		sorted_data = np.sort(data)[::-1] # sort in descending order
		len = sorted_data.size
		n  = np.arange(1., len+1., 1.)
		cdf_vec = (len - n)/len

		# % Estimate holdoff time (assuming dense data set for characterization)
		holdoff_time = sorted_data[-1]

		# Pap: after pulsing probability, DCR: primary dark count rate, APR: afterpulsing rate
		func = lambda tn, Pap, DCR, APR: 1. - (1.-Pap) * np.exp(-DCR*(tn-holdoff_time)) - Pap*np.exp(-APR*(tn-holdoff_time))
		# Constrain the optimization to the region of 0 <= Pap <= 1, 0 <= DCR <= 1e9 and 0 <= APR <= 1e9
		bounds = (0, [1., 1.e9, 1.e9])
		# Initial guess Pap= DCR= Ttrap
		DCR_guess = 1/np.mean(sorted_data)
		APR_guess = 10*DCR_guess
		p0 = [0.5, DCR_guess, APR_guess]

		# possibility need to give sigma option

		# perform fit
		popt, pcov = curve_fit(func, sorted_data, cdf_vec, p0=p0, bounds=bounds)
		perr = np.sqrt(np.diag(pcov))
		# x_plot_data_realistic = - np.log10( 1. - cdf_vec )
		# x_plot_fit_realistic = - np.log10( 1 - func(sorted_data, *popt))
		# y_plot_realistic = sorted_data / np.mean( sorted_data )

        # Make the plot
		pm = u"\u00B1"
		plt.figure()
		plt.title("\n".join(wrap( \
			'SRA fit for {}\n'.format(fname) \
			+ 'Pap={:.4g}% {} {:.4g}%, '.format(popt[0]*100, pm, perr[0]*100) \
			+'DCR={:.4g} {} {:.4g}, '.format(popt[1], pm, perr[1]) \
			+ 'APR={:.4g} {} {:.4g}\n'.format(popt[2], pm, perr[2]) \
			+ experiment_info, 60)))
		print('Pap from SRA = {:.4g}%'.format(popt[0]*100))
		plt.semilogx( sorted_data, cdf_vec, 'o', linestyle='None', label='Measurement')
		plt.semilogx( sorted_data, func(sorted_data, *popt), label='fit')
		plt.xlabel('Interarrival time [s]')
		plt.ylabel('CDF=Sorted Index/Total Samples')
		plt.savefig(imgname+'-SRA.png', dpi=300, bbox_inches='tight')
        # title( plot_title );




	# if which_measurement == "Dark":
	# 	header = 'Bias [V],'+','.join(['cps @ vth={}'.format(vth) for vth in thresholds])
	# 	data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_measurements), axis=1)
	# 	# print(data_out)
	# 	np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")
	# elif which_measurement == "Light":
	# 	print('Checking shape of arrays: dark - {}, light- {}'.format(dark_counts.shape, count_measurements.shape))
	#
	# 	# compute things
	# 	actual_power = tap_avg_measurements*tap_to_incident
	# 	print(tap_to_incident)
	# 	for nd_filter in nd_cfg: # attenuate
	# 		actual_power = actual_power*nd_filters[nd_filter]
	# 	incident_cps = actual_power/(6.62607015E-34*299792458/(wavelength.magnitude*1e-9))
	# 	pdp = np.divide((count_measurements-dark_counts), incident_cps, out=np.zeros_like(incident_cps), where=incident_cps!=0)
	#
	# 	# Assemble data
	# 	header = 'Bias [V],'+','.join(
	# 		['cps @ vth={}'.format(vth) for vth in thresholds] +
	# 		['Tap power avg[W] @ vth={}'.format(vth) for vth in thresholds] +
	# 		['Tap power std[W] @ vth={}'.format(vth) for vth in thresholds] +
	# 		['Actual power[W] @ vth={}'.format(vth) for vth in thresholds] +
	# 		['Incident cps @ vth={}'.format(vth) for vth in thresholds] +
	# 		['PDP[%] @ vth={}'.format(vth) for vth in thresholds] )
	#
	# 	experiment_info = experiment_info + ', {}nm'.format(wavelength.magnitude)
	#
	# 	data_out = np.concatenate((vec_overbias.reshape(num_measures,1).magnitude, count_measurements, tap_avg_measurements, tap_std_measurements, actual_power, incident_cps, pdp), axis=1)
	#
	# 	plt.figure()
	# 	plt.title("\n".join(wrap('PDP '+experiment_info+' at Vth={}'.format(thresholds[0]), 60)))
	# 	plt.plot(vec_overbias.magnitude, pdp, 'o-') # plot first threshold data
	# 	plt.xlabel('Bias [V]')
	# 	plt.ylabel('PDP [%]')
	# 	plt.ylim([0,1.0])
	# 	plt.grid(True, which='both', linestyle=':', linewidth=0.3)
	# 	plt.savefig(imgname+'PDP.png', dpi=300, bbox_inches='tight')
	#
	# 	print(data_out)
	# 	np.savetxt(csvname, data_out, delimiter=',', header=header, footer=experiment_info, comments="")



	# plt.figure()

	#
	# plt.semilogy(vec_overbias.magnitude, count_measurements[:,0], 'o-') # plot first threshold data
	#
	# plt.xlabel('Bias [V]')
	# plt.ylabel('Counts [cps]')
	# plt.grid(True, which='both', linestyle=':', linewidth=0.3)
	# plt.savefig(imgname, dpi=300, bbox_inches='tight')
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

if __name__ == '__main__':
	main()
