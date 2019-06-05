"""
A GUI that can be used to view live spectrum video from our
Ocean Optics HR2000 spectrometer. Nothing special. I copied Nate's code.
python live_ocean_optics_HR2000_spectrometer_gui.py figure_size peakzoom wavelength
Ex)
python live_ocean_optics_HR2000_spectrometer_gui.py 20,5 No 500,600
- creates a 20 unit wide, 5 unit high window
- without peak zooming
- and plots wavelength from 500 nm to 600 nm
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
import seabreeze.spectrometers as sb
from time import sleep
from instrumental import u

devices = sb.list_devices()
oo = sb.Spectrometer(devices[0])
oo.integration_time_micros(100000)

InbandThreshold = 2000

if len(sys.argv) > 1:
	figure_size = [int(s) for s in sys.argv[1].split(',')]
	fig, ax = plt.subplots(1,1,figsize=(figure_size[0],figure_size[1]))
else:
	fig, ax = plt.subplots(1,1,figsize=(5,5))

if len(sys.argv) > 3:
	lambdaRange = [int(s) for s in sys.argv[3].split(',')]

plt.ion()
ln, = ax.plot(852,100,'bo')
ax.grid(which='both')
ax.set_ylabel('Counts [1]')
ax.set_xlabel('Wavelength [nm]')
font = {'family': 'serif',
        'color':  'darkred',
        'weight': 'normal',
        'size': 20,
        }
delta_lm = 15
text = plt.text(500, 100, 'Measure', fontdict=font)

while True:
	spec = oo.spectrum()
	spec_wavelength = spec[0, :]
	spec_val = spec[1, :]
	InbandThreshold = np.max(spec_val)/2.0
	sleep(0.02)

	ln.remove()

	if len(sys.argv) > 2 and sys.argv[2]=='Yes':
		lm_pump = spec[0,1319+np.argmax(spec[1,1319:1469])] * u.nm
		lm_stokes = spec[0,1689+np.argmax(spec[1,1689:1909])] * u.nm
		shift = ( 1/lm_pump - 1/lm_stokes ).to(1/u.cm)
		lm_peak = spec[0,np.argmax(spec[1,:])]

	    	#text.set_text('pump @ {:4.5g} \n Stokes @ {:4.5g} \n shift: {:4.4g}'.format(lm_pump,lm_stokes,shift))
		text.set_text('peak @ {:4.5g} nm'.format(lm_peak))
		text.set_x(lm_peak-delta_lm/2.+1)

		ax.set_xlim([lm_peak-delta_lm/2.,lm_peak+delta_lm/2.])
	elif len(sys.argv) > 3:
		ax.set_xlim(lambdaRange[0], lambdaRange[1])
		if len(spec_val[np.where(spec_val > InbandThreshold)])>0 :

			BWmin = np.min(spec_wavelength[np.where(spec_val > InbandThreshold)])
			BWmax = np.max(spec_wavelength[np.where(spec_val > InbandThreshold)])
			text.set_text('FWHM is {:g} nm ~ {:g} nm'.format(BWmin, BWmax))
		else:
			text.set_text('No BW detected')
	else :
    		ax.set_xlim([np.min(spec[0,:]), np.max(spec[0,:])])

	ln, = ax.plot(spec[0,:],spec[1,:],'b')
	plt.pause(0.05)
