

# Try to use the driver provided by Agilent to do wavelength sweeps

import clr
import sys
import matplotlib.pyplot as plt

sys.path.append("C:\Program Files (x86)\IVI Foundation\VISA\WinNT\Bin")
sys.path.append("C:\Program Files (x86)\IVI Foundation\VISA\WinNT\Include")
# Add the dll
clr.AddReference('hp816x_32')

# Initialize the driver
address = "GPIB0::20::INSTR"

success, gpib_handle = hp816x.hp816x_init(address, hp816x.VI_FALSE, hp816x.VI_TRUE)

# Register at least the mainframe containing the tunable laser source
success = hp816x.hp816x_registerMainframe(gpib_handle)


# get original logged wavelength points(no interpolation)
success = hp816x.hp816x_returnEquidistantData(gpib_handle, hp816x.VI_FALSE)


# prepare the lambda scan operation
power = 0.0
unit = hp816x.hp816x_PU_DBM
startWavelength = 1550.0e-9
stopWavelength = 1555.0e-9
stepSize = 5.0e-12
opticalOutput = hp816x.hp816x_HIGHPOW
numberofScans = hp816x.hp816x_NO_OF_SCANS_1
PWMChannels = 1

num_data_points, num_value_arrays = hp816x.hp816x_prepareMfLambdaScan(gpib_handle,
                                  unit, power, opticalOutput, numberofScans, PWMChannels,
                                  startWavelength, stopWavelength, stepSize, None, None)


# perform the lambda scan operation
success, wavs = hp816x.hp816x_executeMfLambdaScan(gpib_handle, None)


# fetch the results
success, powers, wavs = hp816x.hp816x_getLambdaScanResult(gpib_handle,
                                        0, # channel number starts from 0!! * /
                                        hp816x.VI_TRUE,
                                        -50,
                                        None,
                                        None)


# Unreguster mainframes
success = hp816x.hp816x_unregisterMainframe(0)

# close the driver
success = hp816x.hp816x_close(gpib_handle)

plt.plot(wavs, powers)
plt.show()

