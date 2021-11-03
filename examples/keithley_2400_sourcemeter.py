#!/usr/local/bin python
# clear variables
#import sys
#sys.modules[__name__].__dict__.clear()

# Responsivity DAQ routine

import time
from datetime import date
from math import *
from numpy import *
from scipy import io
from scipy import optimize
import visa
from matplotlib import pyplot as plt

print('Import successful')

#bv1= linspace(-1.5, -0.5, 101)
#bv2= linspace(-0.49, 0, 50)
#bv3= linspace(0.01, 0.25, 25)
#bv4= linspace(0.26, 0.5, 25)

#bva = append(bv1,bv2)
#bvb = append(bv3,bv4)

#bias_voltages = append(bva,bvb)
# linspace(start, stop, number of points)
bias_voltages = linspace(1, -10, 11)

start_voltage = min(bias_voltages)
end_voltage = max(bias_voltages)

bias_steps = len(bias_voltages)

device_description = "pSi_PD_fixed_7_1220_tap70uW"

timeTuple = time.localtime()
DirectoryName = 'C:\\Users\\POE\\Desktop\\'
Resp_OutFileName = "iv_%s_%d-%d-%d_on_%d#%d#%d--%d#%d#%d.mat" % (
                            device_description,
                            start_voltage,
                            bias_steps,
                            end_voltage,
                            timeTuple[0],
                            timeTuple[1],
                            timeTuple[2],
                            timeTuple[3],
                            timeTuple[4],
                            timeTuple[5])
Resp_OutFileName = DirectoryName + Resp_OutFileName

Figure_OutFileName = "iv_%s_%d-%d-%d_on_%d#%d#%d--%d#%d#%d.png" % (
                            device_description,
                            start_voltage,
                            bias_steps,
                            end_voltage,
                            timeTuple[0],
                            timeTuple[1],
                            timeTuple[2],
                            timeTuple[3],
                            timeTuple[4],
                            timeTuple[5])
Figure_OutFileName = DirectoryName + Figure_OutFileName


print('Set file names ok')

# Setup interface
rm = visa.ResourceManager()
print('Available resources {}'.format(rm.list_resources()))

# timeout is 3 sec
keithley = rm.open_resource('GPIB::15::INSTR', open_timeout=3000)

# Initialize semiconductor parameter analyzer
keithley.write('*RST')
time.sleep(1.0)
keithley.write(':SOUR:FUNC VOLT')
keithley.write(':SENS:FUNC "CURR"')
keithley.write(':SOUR:SWE:RANG AUTO')
keithley.write(':SENS:CURR:PROT 0.001')
keithley.write(':SENS:CURR:RANG:AUTO 1')
keithley.write(':SENS:CURR:NPLC 1')
keithley.write(':SOUR:VOLT:LEV:AMPL 0.0')

keithley.write(':OUTP ON')


measurements = zeros((bias_steps,2))

row=0
# Enter measurement loop
bias_index = 0
for bias_current in bias_voltages:

    keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % bias_current)
    print('Setting bias to {:g} V'.format(bias_current))

    time.sleep(0.01)
        
    measurements[bias_index,0] = bias_current

    keithley.write(':INIT')
            
    time.sleep(0.1)
                            
    # Test    
    #current_meas_array = keithley.ask_for_values(":FETC?")
    #current_meas = current_meas_array[1]
    
    current_meas_array = keithley.query_ascii_values(':FETC?')
    current_meas = current_meas_array[1]


    print('current {:g} uA'.format(current_meas*1e6))
    measurements[bias_index,1] = current_meas

    bias_index = bias_index+1


keithley.write(':OUTP OFF')

# Plot
plt.figure(0)
#plt.plot(measurements[:,0], measurements[:,1], 'b-')
plt.plot(measurements[:,0], log10(abs(measurements[:,1])), 'b-')

#plt.xlim([0, 20])
plt.xlabel("Bias Voltage [V]")
plt.ylabel("Diode Current [uA]")
plt.savefig(Figure_OutFileName, dpi=300)
plt.show()

#plt.close(0)


# Save to .mat file
io.savemat(Resp_OutFileName, {'IV_data': measurements})
