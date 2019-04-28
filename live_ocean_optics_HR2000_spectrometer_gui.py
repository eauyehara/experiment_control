"""
A GUI that can be used to view live spectrum video from our
Ocean Optics HR2000 spectrometer. Nothing special. I copied Nate's code.
python live_ocean_optics_HR2000_spectrometer_gui.py figure_size peakzoom
Ex)
python live_ocean_optics_HR2000_spectrometer_gui.py 5,5 No
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
import seabreeze.spectrometers as sb
from time import sleep
from instrumental import u
devices = sb.list_devices()
oo = sb.Spectrometer(devices[0])
oo.integration_time_micros(20)
if len(sys.argv) > 1:
	figure_size = [int(s) for s in sys.argv[1].split(',')]
	fig, ax = plt.subplots(1,1,figsize=(figure_size[0],figure_size[1]))
else:
	fig, ax = plt.subplots(1,1,figsize=(5,5))

plt.ion()
ln, = ax.plot(852,100,'bo')
ax.grid()
ax.set_ylabel('Counts [1]')
ax.set_xlabel('Wavelength [nm]')
font = {'family': 'serif',
        'color':  'darkred',
        'weight': 'normal',
        'size': 20,
        }
delta_lm = 15
text = plt.text(786, 2800, 'inital text', fontdict=font)

while True:
	spec = oo.spectrum()
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
	else :
    		ax.set_xlim([np.min(spec[0,:]), np.max(spec[0,:])])

	ln, = ax.plot(spec[0,:],spec[1,:],'b')
	plt.pause(0.05)
