############################################
#  Driver for control of Micron Optics FFP
#  fiber coupled Fabry-Perot filter
#  using a LabJack T7 via LJM
#  written by Dodd, Nov 1 2017
############################################
import numpy as np
from labjack import ljm

# Open first found LabJack
lj = ljm.openS("ANY", "ANY", "ANY")
# Call eReadName to read the serial number from the LabJack.
lj_serial = ljm.eReadName(lj, "SERIAL_NUMBER")
print("Openned LabJack with serial {}".format(lj_serial))
