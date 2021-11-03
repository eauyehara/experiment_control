from numpy import linspace, repeat, concatenate, tile
import instrumental
from instrumental import u, instrument
from instrumental.drivers.daq.ni import NIDAQ, Task

daq = instrument("NIDAQ_USB-6259")

def scan_vals(n0,n1,pp0,pp1,os0,os1):
    os0V = os0.to(u.volt).m
    pp0V = pp0.to(u.volt).m
    os1V = os1.to(u.volt).m
    pp1V = pp1.to(u.volt).m

    v0 = linspace(os0V-(pp0V/2.0),os0V+(pp0V/2.0),n0)*u.volt
    v1 = linspace(os1V-(pp1V/2.0),os1V+(pp1V/2.0),n1)*u.volt

    return v0, v1

def raster_vals(n0,n1,pp0,pp1,os0,os1):
    v0,v1 = scan_vals(n0,n1,pp0,pp1,os0,os1)
    vrstr0 = tile(concatenate((v0.m,v0.m[::-1])),n1//2)*u.volt
    vrstr1 = repeat(v1.m,n0)*u.volt

    return vrstr0, vrstr1

def configure_scan(n0,n1,pp0,pp1,os0,os1,fsamp):
    vrstr0, vrstr1 = raster_vals(n0,n1,pp0,pp1,os0,os1)
    scan_task = Task(daq.ao0,daq.ao1,daq.ai0,daq.ai1,daq.ai2,daq.ai3)
    scan_task.set_timing(fsamp=fsamp,n_samples=n0*n1)

    scan_time = (1/fsamp).to(u.second)*n0*n1
    print(f"scan time: {scan_time:3.2f}")

    write_data = {'Dev1/ao0':vrstr0,'Dev1/ao1':vrstr1}
    return scan_task, write_data


# tests
n0, n1      =   300           ,       300
pp0, pp1    =   1*u.volt      ,       1*u.volt
os0, os1    =   2.37*u.volt   ,       1.5*u.volt
fsamp       =   1*u.kHz
scan_task, write_data = configure_scan(n0,n1,pp0,pp1,os0,os1,fsamp)



import matplotlib.pyplot as plt
p0 = plt.plot(range(n0*n1),vr0.m,range(n0*n1),vr1.m)
plt.show()
