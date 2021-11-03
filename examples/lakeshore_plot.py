#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot of temperature values grabbed from Lake Shore 331S cryo temperature controller.
Measure and display framerate.
"""

import socket
import sys
import struct
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
from matplotlib.colors import to_rgba_array                                     # for use of matplotlib named colors
from pyqtgraph.ptime import time
from time import sleep
from lakeshore_client import get_temperature



width_pix = 600
height_pix = 450
Npts = 500
wait_sec = 0.3
sample_time_sec = 0.3 # estimate of time taken by server to return value
rescale = True

def get_vals():
    Tmeas_A = get_temperature(Temp_data='Tmeas_A').m
    Tset_A = get_temperature(Temp_data='Tset_A').m
    Tmeas_B = get_temperature(Temp_data='Tmeas_B').m
    vals = (Tmeas_A, Tset_A, Tmeas_B)
    return vals

def mpl2pg(c):
    return tuple((to_rgba_array(c)[0]*255).astype(int).tolist())

app = QtGui.QApplication([])

# Use pyqtgraph's GraphicsItems
view = pg.GraphicsView()
layout = pg.GraphicsLayout()
view.setCentralItem(layout)
view.setMaximumWidth(width_pix)
view.setMaximumHeight(height_pix)
view.showMaximized()

### use QWidgets
# w = QtGui.QWidget()
# layout = QtGui.QGridLayout()
# w.setLayout(layout)
# w.setMaximumWidth(width_pix)
# w.setMaximumHeight(height_pix)
# w.showMaximized()



#p = layout.addPlot(col=0,row=0,rowspan=8)
p = pg.PlotItem()
#p = pg.PlotWidget()
p.setWindowTitle('Sample Thermostat Data')
p.setRange(QtCore.QRectF(0, -10, 5000, 20))
p.showGrid(x=True,y=True,alpha=0.8)
#p.setXRange(0,Npts*wait_sec, padding=0)
p.setLimits(xMin=0,
            xMax=2*Npts*wait_sec,
            yMin=0,
            yMax=300,
            minXRange=10*wait_sec,
            maxXRange=2*Npts*wait_sec,
            minYRange=0.01,
            maxYRange=300)
p.enableAutoScale()
xlab = p.setLabel('bottom',text='time',units='s')
ylab = p.setLabel('left',text='temperature',units='K')



#vb = p.getViewBox()

# vb.autoRange(padding=0.1)
#curve.setFillBrush((0, 0, 100, 100))
#curve.setFillLevel(0)

#lr = pg.LinearRegionItem([100, 4900])
#p.addItem(lr)


init_vals = get_vals()


# prepare Pen objects for curve styles
pen0 = pg.mkPen(color=mpl2pg('C0'),
                width=1,
                style=QtCore.Qt.SolidLine,
                )
pen1 = pg.mkPen(color=mpl2pg('C0'),
                width=1,
                style=QtCore.Qt.DashLine,
                )
pen2 = pg.mkPen(color=mpl2pg('C3'),
                width=1,
                style=QtCore.Qt.SolidLine,
                )


# initalize data
data0 = np.array([init_vals[0]])
data1 = np.array([init_vals[1]])
data2 = np.array([init_vals[2]])
time_array = np.array([0])
# initialize curve objects
curve0 = p.plot(time_array,data0,pen=pen0,name='Tmeas_A')
curve1 = p.plot(time_array,data1,pen=pen1,name='Tset_A')
curve2 = p.plot(time_array,data1,pen=pen2,name='Tmeas_B')
t0 = time()
ptr = 1
lastTime = t0
fps = None
fps_text = pg.TextItem(text='fps: ',
                        color=(200,200,200),
                        anchor=(1,0),
                        )
leg = pg.LegendItem()
leg.addItem(curve0,name='Tmeas_A')
leg.addItem(curve1,name='Tset_A')
leg.addItem(curve2,name='Tmeas_B')

#p.addItem(fps_text)
fps_text.setPos(0.5,0.5)
layout.addItem(p,0,0,1,1)
#layout.addItem(leg,1,0,10,1)
#layout.layout.setRowStretchFactor(0, 3)
#layout.layout.setRowStretchFactor(0, 10)
#layout.layout.setRowStretchFactor(1, 1)
#layout.addWidget(p,0,0,5,1)
#layout.addWidget(leg,5,0,1,1)

def update():
    global fps_text,leg,layout,data0, data1, data2, curve0, curve1, curve2, time_array, ptr, p, lastTime, fps
    vals = get_vals()
    now = time()-t0
    # update data
    if ptr<=Npts:
        data0 = np.append(data0, np.array(vals[0]))
        data1 = np.append(data1, np.array(vals[1]))
        data2 = np.append(data2, np.array(vals[2]))
        time_array = np.append(time_array, np.array([now]))
    else:
        data0 = np.append(data0[1:], np.array(vals[0]))
        data1 = np.append(data1[1:], np.array(vals[1]))
        data2 = np.append(data2[1:], np.array(vals[2]))
        time_array = np.append(time_array[1:], np.array([now]))
    ptr+=1
    curve0.setData(time_array-time_array[0],data0)
    curve1.setData(time_array-time_array[0],data1)
    curve2.setData(time_array-time_array[0],data2)

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
    fps_str = '%0.2f fps' % fps

    #title_str = r'<font color="red">T<sub>meas</sub></font>, <font color="cyan">T<sub>set</sub></font>, ' + fps_str
    title_str = r'Cryo Probe Station temperatures, ' + fps_str
    p.setTitle(title_str,color=(255,255,255))
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
