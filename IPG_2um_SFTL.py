"""
Module for software control of IPG SFTL-Cr-Sn/Se-2300-500-3000 using spectra
measured using Bristol 721 FTIR (scanning Michelson) optical spectrum analyzer
and the grating stepper-motor (USMC, Standa) and piezo stages (Thorlabs APT)
inside the laser.
"""

from instrumental import instrument, Q_, u
from instrumental.drivers.motion import USMC
from instrumental.drivers.spectrometers import bristol
from instrumental.drivers.spectrometers.bristol import ignore_stderr
import numpy as np

###############################################
#                 Parameters                  #

# Standa motor inside IPG 2um laser
motor_id = 0
travel_per_microstep = 156 * u.nm # from looking at motor model on Standa website

# Bristol 721
bristol_port = 4

# IPG 2um SFTL tuning calibration save location

###############################################



### Open instruments
#spec = instrument('Bristol') can't do this here or you get tons of error messages
sm = USMC(motor_id,travel_per_microstep)

@ignore_stderr
def calibrate_grating(speed=3000,x_min=0*u.mm,x_max=None,nx=10):
    spec = instrument('Bristol')
    # prepare data arrays
    if not x_max:
        x_max = (sm.limit_switch_2_pos - sm.limit_switch_1_pos) * sm.travel_per_microstep

    x_comm = np.linspace(x_min.to(u.mm).magnitude,x_max.to(u.mm).magnitude,nx=10) * u.mm
    lm = np.empty(len(x_comm)) * u.nm
    # collect data
    for xind, x in enumerate(x_comm):
        print('Acquiring wavelength {} of {}...'.format(xind+1,len(x_comm)))
        sm.go_and_wait(x,speed=speed)
        lm[xind] = spec.get_lambda()
        print('...found to be {:4.4g} nm'.format(lm[xind].to(u.nm).magnitude))
    # close spectrometer to end errors
    spec.close()

    # perform fit

    return x_comm, lm
