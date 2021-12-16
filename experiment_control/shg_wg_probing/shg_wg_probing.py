import os
import time
import numpy as np
import matplotlib.pyplot as plt
from instrumental import instrument
from instrumental.drivers.daq.ni import Task

from .HPLightWave import *
import seabreeze.spectrometers as sb

from ..util.units import Q_, u
from ..util.io import *

data_dir = os.path.join(home_dir,"Dropbox (MIT)","data","shg_wg_probing")

daq     =   instrument('DAQ2_NIDAQ_USB-6259_21146242')
laser = HPLightWave(1,3)
laser.initialize()

# HR4000 parameters
hr4000_params={'IntegrationTime_micros':100000}
devices = sb.list_devices()
spec = sb.Spectrometer(devices[0])
spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])



# Configure DAQ channels
ch_sweep_wl         =   daq.ai0
ch_fund_tap         =   daq.ai1
ch_fund_thru        =   daq.ai3
ch_shg_thru         =   daq.ai2
ch_sweep_trigger    = daq.port0
ch_sweep_trigger.as_output()


def configure_sweep(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp):
    Vx_scan, Vy_scan = raster_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    scan_task = Task(
        ch_Vx_p,
        ch_Vx_n,
        ch_Vy_p,
        ch_Vy_n,
        ch_Vshg_x,
        ch_Vshg_y,
        ch_Vx_meas,
        ch_Vy_meas,
        # ch_Vpm,
    )
    scan_task.set_timing(fsamp=fsamp,n_samples=nx*ny)

    scan_time = (1/fsamp).to(u.second)*nx*ny
    print(f"scan time: {scan_time:3.2f}")

    write_data = {
        ch_Vx_p_str :   Vx_scan/2,
        ch_Vx_n_str :   -Vx_scan/2,
        ch_Vy_p_str :   Vy_scan/2,
        ch_Vy_n_str :   -Vy_scan/2,
    }

    return scan_task, write_data


# def instrument_info():
#     print("daq:")
#     print("\t" + "module" + ":\t" + str(daq._paramset["module"]))
#     print("\t" + "name"   + ":\t" + str(daq.name))
#     print("\t" + "model"  + ":\t" + str(daq._paramset["model"].decode("utf-8")))
#     print("\t" + "serial" + ":\t" + str(daq._paramset["serial"]))
#
#     print("scope:")
#     print("\t" + "module" + ":\t" + str(scope._paramset["module"]))
#     print("\t" + "model"  + ":\t" + str(scope.model))
#     print("\t" + "serial" + ":\t" + str(scope.serial))
#     print("\t" + "visa address" + ":\n\t\t" + str(scope._paramset["visa_address"]))
#
