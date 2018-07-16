#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot as rapidly as possible to measure speed.
"""

import socket
import sys
import struct
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
from pyqtgraph.ptime import time
from time import sleep

Npts = 3000
wait_sec = 0.03
current_amp = 1e-5
calc_temp = True
rescale = True
 # parameters for RL10 NTC thermistor, RL1006-53.4K-140-D1, Digikey part KC009N-ND
beta = 4615 # degK
R_ohm_25C = 1e5 # ohm
T0 = 25 + 273.15 # degK
r_inf = R_ohm_25C * np.exp( - beta / T0 )
### set up TCP communication ################
HOST, PORT = "localhost", 9999
data = " ".join(sys.argv[1:])


##############################################

def inverse_thermistance(R_ohm,R_ohm_25C,beta):
    return  beta / np.log(R_ohm / r_inf) - 273.15

def get_val(ch,calc_temp=True):
    try:
        # open connection to server
        # Create a socket (SOCK_STREAM means a TCP socket)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        # Request AI0 data from server
        sock.sendall(bytes('AI{}'.format(ch), "utf-8"))
        # Receive float voltage from the server
        val = struct.unpack('f',sock.recv(1024))[0]
        # # Request AI1 data from server
        # sock.sendall(bytes('AI1', "utf-8"))
        # # Receive float voltage from the server
        # val1 = struct.unpack('f',sock.recv(1024))[0]
    finally:
        # close server
        sock.close()
    if calc_temp:
        val_ohm = val / current_amp
        val = inverse_thermistance(val_ohm,R_ohm_25C,beta)
    return val


    #received = str(sock.recv(1024), "utf-8")



app = QtGui.QApplication([])

p = pg.plot()
p.setWindowTitle('pyqtgraph example: PlotSpeedTest')
p.setRange(QtCore.QRectF(0, -10, 5000, 20))
p.setLabel('bottom', 'Index', units='B')
p.showGrid(x=True,y=True,alpha=0.8)
#p.setXRange(0,Npts*wait_sec, padding=0)
p.setLimits(xMin=0,
            xMax=2*Npts*wait_sec,
            yMin=0,
            yMax=100,
            minXRange=10*wait_sec,
            maxXRange=2*Npts*wait_sec,
            minYRange=0.01,
            maxYRange=100)
p.enableAutoScale()
p.setLabel('bottom',text='time',units='s')
p.setLabel('left',text='temperature',units='C')
vb = p.getViewBox()

# vb.autoRange(padding=0.1)
#curve.setFillBrush((0, 0, 100, 100))
#curve.setFillLevel(0)

#lr = pg.LinearRegionItem([100, 4900])
#p.addItem(lr)

init_val0 = get_val(0,calc_temp=calc_temp)
init_val1 = get_val(1,calc_temp=calc_temp)

# data0 = np.ones(Npts)*init_val0
# data1 = np.ones(Npts)*init_val1
# time_array = np.linspace(0,wait_sec/10.0,Npts)
data0 = np.array([init_val0])
data1 = np.array([init_val1])
time_array = np.array([0])
curve0 = p.plot(time_array,data0,pen=(0,2),name='meas temp')
curve1 = p.plot(time_array,data1,pen=(1,2),name='set temp')
t0 = time()
ptr = 1
lastTime = t0
fps = None
leg = p.addLegend(size=[80,30],offset=[10,300])
leg.addItem(curve0,name='meas temp')
leg.addItem(curve1,name='set temp')
def update():
    global leg,vb,data0, data1, curve0, curve1, time_array, ptr, p, lastTime, fps
    val0 = get_val(0,calc_temp=calc_temp)
    val1 = get_val(1,calc_temp=calc_temp)
    now = time()-t0
    # update data
    if ptr<=Npts:
        data0 = np.append(data0, np.array(val0))
        data1 = np.append(data1, np.array(val1))
        time_array = np.append(time_array, np.array([now]))
    else:
        data0 = np.append(data0[1:], np.array(val0))
        data1 = np.append(data1[1:], np.array(val1))
        time_array = np.append(time_array[1:], np.array([now]))
    ptr+=1
    curve0.setData(time_array-time_array[0],data0)
    curve1.setData(time_array-time_array[0],data1)

    # if rescale:
    #     vb.setXRange(time_array.min(),time_array.max(),padding=0.05)
    #     p.setXRange(time_array.min(),time_array.max(),padding=0.05)
    #
    #     p.setYRange(min([data0.min(),data1.min()]), max([data0.max(),data1.max()]), padding=0.1)

    dt = now - lastTime
    lastTime = now
    if fps is None:
        fps = 1.0/dt
    else:
        s = np.clip(dt*3., 0, 1)
        fps = fps * (1-s) + (1.0/dt) * s
    p.setTitle('%0.2f fps' % fps)
    # ta_max_str = 'time_array max: {:3.3f}, '.format(time_array.max())
    # vb_range_str = 'vb_range: {}, '.format(vb.viewRange())
    # vb_rect_str = 'vb_rect: {}'.format(vb.viewRect())
    # p.setTitle(ta_max_str+vb_range_str+vb_rect_str)
    app.processEvents()  ## force complete redraw for every plot
    sleep(wait_sec)
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(0)

## Start Qt event loop unless running in interactive mode.
if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
