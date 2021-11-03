#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Ocean Optics HR4000 spectrometer plot GUI
Supports csv export of IV curves
"""

import socket
import sys
import struct
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from pyqtgraph.ptime import time
from time import sleep
import csv
from os import path
from datetime import datetime
from oceanoptics_hr4000_client import *


Npts = 500
wait_sec = 2
sample_time_sec = 0.45 # estimate of time taken by server to return value
rescale = True

### set up TCP communication ################
HOST, PORT = "localhost", 9997
data = " ".join(sys.argv[1:])

width_pix = 1280
height_pix = 960
##############################################

data_dir = path.normpath('./')


import seabreeze.spectrometers as sb
# HR4000 parameters
hr4000_params={'IntegrationTime_micros':100000}

# Setup spectrometer
devices = sb.list_devices()
spec = sb.Spectrometer(devices[0])
spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])


# Global variables
spectra_data = np.array([])

# Functions from client script
def get_val():
    val = get_sp()
    return val


app = QtGui.QApplication([])

## Define a top-level widget to hold everything
w = QtGui.QWidget()

## Create some widgets to be placed inside
btn_save = QtGui.QPushButton('Save Spectra')

edit_intTime = QtGui.QLineEdit('{:f}'.format(hr4000_params['IntegrationTime_micros']))
btn_setparam = QtGui.QPushButton('Set Spectrometer Params')
edit_deviceName = QtGui.QLineEdit('TC0')
btn_setdirec = QtGui.QPushButton('Set Data Directory')

statusbar = QtGui.QStatusBar()

p = pg.PlotWidget()
xlabel = p.setLabel('bottom',text='Wavelength',units='nm')
ylabel = p.setLabel('left',text='Counts',units='Arb. Unit')




## Create a grid layout to manage the widgets size and position
layout = QtGui.QGridLayout()
w.setLayout(layout)

## Add widgets to the layout in their proper positions
layout.addWidget(QtGui.QLabel('Device Name'), 0, 0)
layout.addWidget(edit_deviceName, 0, 1) # save spectra button
layout.addWidget(btn_save, 1, 0) # save spectra button

layout.addWidget(QtGui.QLabel('Integration Time [usec]'), 2,0)
layout.addWidget(edit_intTime, 2, 1)
layout.addWidget(btn_setparam, 3, 0) # Set parameters button
layout.addWidget(btn_setdirec, 4, 0) # Set parameters button

layout.addWidget(statusbar, 8,0, 1,10)

layout.addWidget(p, 0, 2, 8, 8) # Plot on right spans 8x8

# Button event handler functions
def save_spectra():
    global spectra_data, data_dir

    timer.stop()
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

    # Save csv
    fname = edit_deviceName.text()+'-'+timestamp_str+'.csv'
    fpath = path.normpath(path.join(data_dir,fname))

    with open(fpath, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, dialect='excel')
        csvwriter.writerow(['Wavelength nm', 'Count', 'Integration time', str(hr4000_params['IntegrationTime_micros'])])

        for i in range(spectra_data.shape[0]):
            csvwriter.writerow([str(spectra_data[i,0]), str(spectra_data[i,1])])

    # Save png
    fname = edit_deviceName.text()+'-'+timestamp_str+'.png'
    fpath = path.normpath(path.join(data_dir,fname))

    # QtGui.QApplication.processEvents()
    # create an exporter instance, as an argument give it
    # the item you wish to export
    exporter = pg.exporters.ImageExporter(p.scene())
    exporter.export(fpath)

    statusbar.showMessage('Saved spectra to {}'.format(fpath), 5000)
    # restart timer
    timer.start(max([timer_factor*hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

btn_save.clicked.connect(save_spectra)

def set_measurement_params():
    global hr4000_params

    timer.stop()
    hr4000_params['IntegrationTime_micros'] = float(edit_intTime.text())
    spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])
    timer.start(max([timer_factor*hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    statusbar.showMessage('Set spectrometer parameters', 5000)

btn_setparam.clicked.connect(set_measurement_params)

def set_directory():
    global data_dir

    timer.stop()
    data_dir = QtGui.QFileDialog.getExistingDirectory()

    timer.start(max([timer_factor*hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    statusbar.showMessage('Set data director to {}'.format(data_dir), 5000)
btn_setdirec.clicked.connect(set_directory)


# Timer function
def refresh_live_spectra():
    global spectra_data

    # print('Refreshing plot')
    spectra_data = np.transpose( spec.spectrum() )

    p.plot(spectra_data, clear=True)

timer_factor = 1.2e-3
timer = QtCore.QTimer()
timer.timeout.connect(refresh_live_spectra)
timer.start(timer_factor*hr4000_params['IntegrationTime_micros']) # in msec


def exitHandler():
    print('Exiting script')
    timer.stop()

app.aboutToQuit.connect(exitHandler)

## Display the widget as a new window
w.show()

## Start the Qt event loop
app.exec_()
