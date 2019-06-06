#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot of peak wavelength measured by Bristol 721 (LSA) or 621 (wavemeter).
"""

import socket
import sys
import struct
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
from pyqtgraph.ptime import time
from time import sleep
from keithley2400_client import *

Npts = 500
wait_sec = 2
sample_time_sec = 0.45 # estimate of time taken by server to return value
rescale = True

### set up TCP communication ################
HOST, PORT = "localhost", 9998
data = " ".join(sys.argv[1:])

width_pix = 1280
height_pix = 960
##############################################

# Global variables
voltage = 0.0
current = 0.0
iv_params = [0.0, 10.0, 10]
output = 'OFF'

# Functions from client script
def get_val():
    val = get_i()
    return val


app = QtGui.QApplication([])

## Define a top-level widget to hold everything
w = QtGui.QWidget()

## Create some widgets to be placed inside
label_i = QtGui.QLabel('Output off')
edit_v = QtGui.QLineEdit('{:g}'.format(voltage))
btn_sv = QtGui.QPushButton('Set Voltage')

btn_out = QtGui.QPushButton('Toggle Output')

edit_start = QtGui.QLineEdit('{:g}'.format(iv_params[0]))
edit_stop = QtGui.QLineEdit('{:g}'.format(iv_params[1]))
edit_step = QtGui.QLineEdit('{:d}'.format(iv_params[2]))
btn_iv = QtGui.QPushButton('Run IV')
btn_save = QtGui.QPushButton('Save IV')
plot = pg.PlotWidget()

## Create a grid layout to manage the widgets size and position
layout = QtGui.QGridLayout()
w.setLayout(layout)

## Add widgets to the layout in their proper positions
layout.addWidget(QtGui.QLabel('Current'), 0,0)
layout.addWidget(label_i, 0, 1)
layout.addWidget(QtGui.QLabel('Voltage setpoint [V]'), 1,0)
layout.addWidget(edit_v, 1, 1)
layout.addWidget(btn_sv, 2, 0, 1,2)

layout.addWidget(QtGui.QLabel('IV start'), 3,0)
layout.addWidget(edit_start, 3, 1)
layout.addWidget(QtGui.QLabel('IV stop'), 4,0)
layout.addWidget(edit_stop, 4, 1)
layout.addWidget(QtGui.QLabel('IV steps'), 5,0)
layout.addWidget(edit_step, 5, 1)

layout.addWidget(btn_iv, 6, 0, 1, 2)
layout.addWidget(btn_save, 7, 0, 1, 2)
layout.addWidget(btn_out, 8, 0, 1, 2)

layout.addWidget(plot, 0, 3, 8, 1)  # plot goes on right side, spanning 3 rows

# Button event handler functions
def set_voltage():
    setpoint = float(edit_v.text())
    set_v(voltage = setpoint)

# edit_v.textChanged.connect(set_voltage)
edit_v.returnPressed.connect(set_voltage)
btn_sv.clicked.connect(set_voltage)

def toggle_output():
    global output
    if output == 'OFF':
        set_out(output='ON')
        output = 'ON'
    else:
        set_out(output='OFF')
        output='OFF'

btn_out.clicked.connect(toggle_output)

def update_current():
    global output
    if output=='ON':
        current_value = get_i()
        label_i.setText('{:e} A'.format(current_value))
    else:
        label_i.setText('Output off')

timer = QtCore.QTimer()
timer.timeout.connect(update_current)
timer.start(1000) # msec


def exitHandler():
    global output
    if output == 'ON':
        set_out(output='OFF')
        output = 'OFF'

app.aboutToQuit.connect(exitHandler)

## Display the widget as a new window
w.show()

## Start the Qt event loop
app.exec_()





#
#
# # Use pyqtgraph's GraphicsItems
# view = pg.GraphicsView()
# layout = pg.GraphicsLayout()
# view.setCentralItem(layout)
# view.setMaximumWidth(width_pix)
# view.setMaximumHeight(height_pix)
# view.showMaximized()
#
# ### use QWidgets
# # w = QtGui.QWidget()
# # layout = QtGui.QGridLayout()
# # w.setLayout(layout)
# # w.setMaximumWidth(width_pix)
# # w.setMaximumHeight(height_pix)
# # w.showMaximized()
#
#
#
# #p = layout.addPlot(col=0,row=0,rowspan=8)
# p = pg.PlotItem()
# #p = pg.PlotWidget()
# p.setWindowTitle('Keithley 2400 Current data')
# p.setRange(QtCore.QRectF(0, -10, 5000, 20))
# p.showGrid(x=True,y=True,alpha=0.8)
# #p.setXRange(0,Npts*wait_sec, padding=0)
# p.setLimits(xMin=0,
#             xMax=2*Npts*wait_sec,
#             yMin=1200,
#             yMax=5000,
#             minXRange=10*wait_sec,
#             maxXRange=2*Npts*(wait_sec+sample_time_sec),
#             minYRange=0.01,
#             maxYRange=3810)
# p.enableAutoRange()
# # should be p.enableAutoRange(axis, enable) but I don't know what 'axis' and 'enable' should be
# xlab = p.setLabel('bottom',text='time',units='s')
# ylab = p.setLabel('left',text='wavelength',units='nm')
#
#
#
# #vb = p.getViewBox()
#
# # vb.autoRange(padding=0.1)
# #curve.setFillBrush((0, 0, 100, 100))
# #curve.setFillLevel(0)
#
# #lr = pg.LinearRegionItem([100, 4900])
# #p.addItem(lr)
#
# init_val0 = get_val()
#
#
# # data0 = np.ones(Npts)*init_val0
# # data1 = np.ones(Npts)*init_val1
# # time_array = np.linspace(0,wait_sec/10.0,Npts)
# data0 = np.array([init_val0])
# #data1 = np.array([init_val1])
# time_array = np.array([0.0])
# init_time = np.arange(1000)
# init_data = np.zeros(init_time.shape)
# curve0 = p.plot(x=init_time,y=init_data,pen=(255,165,0),name='wavelength')
# #curve1 = p.plot(time_array,data1,pen=(1,2),name='set temp')
# t0 = time()
# ptr = 1
# lastTime = t0
# fps = None
# fps_text = pg.TextItem(text='fps: ',
#                         color=(200,200,200),
#                         anchor=(1,0),
#                         )
# # leg = pg.LegendItem()
# # leg.addItem(curve0,name='meas')
# # leg.addItem(curve1,name='set')
#
# #p.addItem(fps_text)
# fps_text.setPos(0.5,0.5)
# layout.addItem(p,0,0,1,1)
# #layout.addItem(leg,1,0,10,1)
# #layout.layout.setRowStretchFactor(0, 3)
# #layout.layout.setRowStretchFactor(0, 10)
# #layout.layout.setRowStretchFactor(1, 1)
# #layout.addWidget(p,0,0,5,1)
# #layout.addWidget(leg,5,0,1,1)
#
# def update():
#     global fps_text,leg,layout,data0,curve0,time_array, ptr, p, lastTime, fps
#     # val0 = get_i()
#     # now = time()-t0
#     # # update data
#     # if ptr<=Npts:
#     #     data0 = np.append(data0, np.array(val0))
#     #     #data1 = np.append(data1, np.array(val1))
#     #     time_array = np.append(time_array, np.array([now]))
#     # else:
#     #     data0 = np.append(data0[1:], np.array(val0))
#     #     #data1 = np.append(data1[1:], np.array(val1))
#     #     time_array = np.append(time_array[1:], np.array([now]))
#     # ptr+=1
#     # curve0.setData(x=time_array-time_array[0],y=data0)
#     # #curve1.setData(time_array-time_array[0],data1)
#     #
#     # # if rescale:
#     # #     vb.setXRange(time_array.min(),time_array.max(),padding=0.05)
#     # #     p.setXRange(time_array.min(),time_array.max(),padding=0.05)
#     # #
#     # #     p.setYRange(min([data0.min(),data1.min()]), max([data0.max(),data1.max()]), padding=0.1)
#     #
#     # dt = now - lastTime
#     # lastTime = now
#     # if fps is None:
#     #     fps = 1.0/dt
#     # else:
#     #     s = np.clip(dt*3., 0, 1)
#     #     fps = fps * (1-s) + (1.0/dt) * s
#     # fps_str = '%0.2f fps' % fps
#     #
#     # title_str = r'<font color="white">Bristol Peak Wavelength</font>, ' + fps_str
#     # p.setTitle(title_str,color=(255,255,255))
#     # # ta_max_str = 'time_array max: {:3.3f}, '.format(time_array.max())
#     # # vb_range_str = 'vb_range: {}, '.format(vb.viewRange())
#     # # vb_rect_str = 'vb_rect: {}'.format(vb.viewRect())
#     # # p.setTitle(ta_max_str+vb_range_str+vb_rect_str)
#     app.processEvents()  ## force complete redraw for every plot
#     sleep(wait_sec)
# timer = QtCore.QTimer()
# timer.timeout.connect(update)
# timer.start(0)
#
# ## Start Qt event loop unless running in interactive mode.
# if __name__ == '__main__':
#     import sys
#     if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#         QtGui.QApplication.instance().exec_()
