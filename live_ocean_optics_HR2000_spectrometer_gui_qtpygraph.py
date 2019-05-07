"""
A GUI that can be used to view live spectrum video from our
Ocean Optics HR2000 spectrometer. Nothing special. I copied Nate's code.
"""

# Import libraries
import numpy as np
import matplotlib.pyplot as plt
import seabreeze.spectrometers as sb
from instrumental import u

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
from pyqtgraph.ptime import time
from time import sleep

# Parameters
Npts = 500
wait_sec = 0.1
sample_time_sec = 0.45 # estimate of time taken by server to return value
rescale = True

width_pix = 1280
height_pix = 960

# Setup spectrometer
devices = sb.list_devices()
oo = sb.Spectrometer(devices[0])
oo.integration_time_micros(20)

def get_val():
    spec = oo.spectrum()
    return spec



# Setup window
app = QtGui.QApplication([])

# Use pyqtgraph's GraphicsItems
view = pg.GraphicsView()
layout = pg.GraphicsLayout()
view.setCentralItem(layout)
view.setMaximumWidth(width_pix)
view.setMaximumHeight(height_pix)
view.showMaximized()

p = pg.PlotItem()
p.setWindowTitle('Bristol Wavelength Data')
p.setRange(QtCore.QRectF(0, -10, 5000, 20))
p.showGrid(x=True,y=True,alpha=0.8)
#p.setXRange(0,Npts*wait_sec, padding=0)
p.setLimits(xMin=0,
            xMax=2*Npts*wait_sec,
            yMin=1200,
            yMax=5000,
            minXRange=10*wait_sec,
            maxXRange=2*Npts*(wait_sec+sample_time_sec),
            minYRange=0.01,
            maxYRange=3810)
p.enableAutoScale()

# should be p.enableAutoRange(axis, enable) but I don't know what 'axis' and 'enable' should be
xlab = p.setLabel('bottom',text='time',units='s')
ylab = p.setLabel('left',text='wavelength',units='nm')

init_val0 = get_val()
data0 = np.array([init_val0])
time_array = np.array([0])
curve0 = p.plot(time_array,data0,pen=(255,165,0),name='wavelength')
t0 = time()
ptr = 1
lastTime = t0
fps = None
fps_text = pg.TextItem(text='fps: ',
                        color=(200,200,200),
                        anchor=(1,0),
                        )

fps_text.setPos(0.5,0.5)
layout.addItem(p,0,0,1,1)
#layout.addItem(leg,1,0,10,1)
#layout.layout.setRowStretchFactor(0, 3)
#layout.layout.setRowStretchFactor(0, 10)
#layout.layout.setRowStretchFactor(1, 1)
#layout.addWidget(p,0,0,5,1)
#layout.addWidget(leg,5,0,1,1)

def update():
    global fps_text,leg,layout,data0,curve0,time_array, ptr, p, lastTime, fps
    val0 = get_val()
    now = time()-t0
    # update data
    if ptr<=Npts:
        data0 = np.append(data0, np.array(val0))
        #data1 = np.append(data1, np.array(val1))
        time_array = np.append(time_array, np.array([now]))
    else:
        data0 = np.append(data0[1:], np.array(val0))
        #data1 = np.append(data1[1:], np.array(val1))
        time_array = np.append(time_array[1:], np.array([now]))
    ptr+=1
    curve0.setData(time_array-time_array[0],data0)
    #curve1.setData(time_array-time_array[0],data1)

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

    title_str = r'<font color="white">Bristol Peak Wavelength</font>, ' + fps_str
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

#fig, ax = plt.subplots(1,1,figsize=(15,15))
##ax = plt.axis([0, 10, 0, 1])
#plt.ion()
#ln, = ax.plot(852,100,'bo')
#ax.grid()
#ax.set_ylabel('Counts [1]')
#ax.set_xlabel('Wavelength [nm]')
#font = {'family': 'serif',
#        'color':  'darkred',
#        'weight': 'normal',
#        'size': 20,
#        }
#delta_lm = 15
#text = plt.text(786, 2800, 'inital text', fontdict=font)
#
#while True:
#    spec = oo.spectrum()
#    # lm_pump = spec[0,1319+np.argmax(spec[1,1319:1469])] * u.nm
#    # lm_stokes = spec[0,1689+np.argmax(spec[1,1689:1909])] * u.nm
#    # shift = ( 1/lm_pump - 1/lm_stokes ).to(1/u.cm)
#    lm_peak = spec[0,np.argmax(spec[1,:])]
#    sleep(0.02)
#    ln.remove()
#    #text.set_text('pump @ {:4.5g} \n Stokes @ {:4.5g} \n shift: {:4.4g}'.format(lm_pump,lm_stokes,shift))
#    text.set_text('peak @ {:4.5g} nm'.format(lm_peak))
#    text.set_x(lm_peak-delta_lm/2.+1)
#    ln, = ax.plot(spec[0,:],spec[1,:],'b')
#    ax.set_xlim([lm_peak-delta_lm/2.,lm_peak+delta_lm/2.])
#    plt.pause(0.05)
