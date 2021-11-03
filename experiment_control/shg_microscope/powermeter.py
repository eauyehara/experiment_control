from datetime import datetime
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
from TLPM import TLPM, TLPM_ATTR_SET_VAL
import time
from instrumental import u

pm_def = b"USB0::0x1313::0x8079::P1001951::INSTR"
# pm_def = b"USB0::0x1313::0x8079::::INSTR"

def list_pms():
    tlPM = TLPM()
    deviceCount = c_uint32()
    tlPM.findRsrc(byref(deviceCount))
    print("Thorlabs PowerMeters found: " + str(deviceCount.value))
    resourceName = create_string_buffer(1024)
    pms = []
    for i in range(0, deviceCount.value):
        tlPM.getRsrcName(c_int(i), resourceName)
        pms.append(c_char_p(resourceName.raw).value)
    tlPM.close()
    return pms

def get_power(pm=pm_def):
    tlPM = TLPM()
    resourceName = create_string_buffer(pm)
    tlPM.open(resourceName, c_bool(True), c_bool(True))
    power =  c_double()
    tlPM.measPower(byref(power))
    tlPM.close()
    return power.value * u.watt

def set_wavelength(λ,pm=pm_def):
    tlPM = TLPM()
    resourceName = create_string_buffer(pm)
    tlPM.open(resourceName, c_bool(True), c_bool(True))
    tlPM.setWavelength(c_double(λ.to(u.nm).m))
    tlPM.close()
    return

def get_wavelength(pm=pm_def):
    tlPM = TLPM()
    resourceName = create_string_buffer(pm)
    tlPM.open(resourceName, c_bool(True), c_bool(True))
    λ_nm =  c_double()
    tlPM.getWavelength(TLPM_ATTR_SET_VAL,byref(λ_nm))
    tlPM.close()
    return λ_nm.value * u.nm

def get_calibration_msg(pm=pm_def):
    tlPM = TLPM()
    resourceName = create_string_buffer(pm)
    tlPM.open(resourceName, c_bool(True), c_bool(True))
    message = create_string_buffer(1024)
    tlPM.getCalibrationMsg(message)
    cal_msg = c_char_p(message.raw).value.decode('utf-8')
    tlPM.close()
    return cal_msg
