'''
Created 04/18/2020 @ 13:16

Not tried yet.

Instruments:
    SMU Keysight B2902A

Description:
    Measures current at different voltages and calculates Quantum Efficiency.
    Saves current and QE data.

'''


import sys
import pyvisa
import numpy as np
import time
import csv
import matplotlib.pyplot as plt
from pint import Quantity as Q_
from experiment-calculations.spad.conversions import *

USB_adress_SOURCEMETER = 'USB0::0x0957::0x8C18::MY51141236::INSTR'

Die = 'W2-PD6D-20um'

power_at_sample = 1e-15 # Incident power in watts
wavelength = 650 # Wavelength in nm

voltage_max = 3
voltage_min = 0
num_measures = 10



# Open SourceMeter Keysight B2902A
def open_SourceMeter():
    SOURCEMETER = rm.open_resource(USB_adress_SOURCEMETER)
    SOURCEMETER.write('*RST') # Reset to default settings
    SOURCEMETER.write(':SOUR1:FUNC:MODE VOLT')
    SOURCEMETER.write(':SENS1:CURR:PROT 100E-06') # Set compliance at 100 uA

    return SOURCEMETER

def measure_current():
    SOURCEMETER.write(':FORM:ELEM:SENS1 CURR') # Perform a spot measurement of the voltage
    SOURCEMETER.write(':SENS1:CURR:APER 1E-4') # Measure during 1ms
    output = SOURCEMETER.query(':MEAS?')
    return output

def apply_voltage(Va):
    SOURCEMETER.write(':SOUR1:VOLT {}'.format(Va))
    SOURCEMETER.write(':OUTP ON')




step = (voltage_max - voltage_min)/(num_measures - 1)
current = np.empty(num_measures)
qe = np.empty(num_measures)
voltage = np.linspace(voltage_min, voltage_max, num = num_measures)

for i in range (0:num_measures):
    apply_voltage(voltage[i])
    current[i] = measure_current()
    qe[i] = calculate_qe(power_at_sample, current[i], wavelength)

# Save data
filename = Die + '_qe_{}_to_{}_in_{}_steps.csv'.format(voltage_min, voltage_max, num_measures)
with open(filename, "w", newline="") as file:
    writer = csv.writer(file, dialect='excel')
    writer.writerows( ','.join(map(str, voltage)) )
    writer.writerows( ','.join(map(str, current)) )
    writer.writerows( ','.join(map(str, qe)) )
