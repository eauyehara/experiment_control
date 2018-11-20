### define function to write voltage to XHR 300-2

from instrumental import u
import labjack_client as ljc
import numpy as np
from experiment_utilities import print_statusline
import time


# Labjack DAC channel used as set-temperature input to temperature controller
xantrex_DAC_ch = 0 # Labjack DAC channel connected to Xantrex 300V power supply control port
xantrex_V_max = 30.0*u.volt # Software limit for Xantrex 300V power supply set voltage, can be up to 300V

### Function to control Xantrex XHR 300-2 300V, 2A programmable DC power supply
### using Analog output channel setV_out_ch of LabJack

## Now written to use the labjack TCP client I wrote for multi-kernel simultaneous access

## also note that at the moment the labjack client python
## code I'm running uses unitless voltages (so 1.0 = 1.0 Volt, duh)

def xhr_write(voltage,lj_dac_channel=0,v_ctl_max=5*u.volt,V_max=xantrex_V_max):
    if (voltage < (V_max)):
        ctl_voltage = (voltage / (300 * u.volt) * v_ctl_max).to(u.volt)
        ljc.write(ctl_voltage.to(u.volt).m,xantrex_DAC_ch)
    else:
        raise Exception('Bad input voltage to xhr_write: {}'.format(voltage))
