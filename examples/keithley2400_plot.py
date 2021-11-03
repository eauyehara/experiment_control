#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Keithley 2400 Source Meter
GUI for controlling and reading values from the source meter
Supports csv export of IV curves
"""

import socket
import sys
import struct
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
from pyqtgraph.ptime import time
from time import sleep
import csv
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
iv_data = np.array([])
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

p = pg.PlotWidget()
xlabel = p.setLabel('bottom',text='Voltage',units='V')
ylabel = p.setLabel('left',text='Current',units='A')

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

layout.addWidget(p, 0, 3, 8, 1)  # plot goes on right side, spanning 3 rows

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

def get_iv_curve():
    global measured_currents, iv_params, iv_data

    iv_params =  np.array([float(edit_start.text()), float(edit_stop.text()), float(edit_step.text())])
    bias_voltages = np.linspace(start=iv_params[0], stop=iv_params[1], num=iv_params[2])
    measured_currents = get_iv(iv_params = iv_params)
    p.plot(bias_voltages, measured_currents)

    iv_data = np.array([bias_voltages, measured_currents])
    print(iv_data.shape)

    set_out('OFF')

btn_iv.clicked.connect(get_iv_curve)

def save_iv():
    global iv_data
    filename = QtGui.QFileDialog.getSaveFileName(caption='Save File', filter='csv(*.csv)')

    with open(filename[0], 'w', newline='') as csvfile:
        # csvwriter = csv.writer(csvfile, delimiter=' ',
        #                         quotechar=',', quoting=csv.QUOTE_MINIMAL)
        csvwriter = csv.writer(csvfile, dialect='excel')
        csvwriter.writerow(['Voltage V', 'Current A'])

        bias_voltages = np.linspace(start=iv_params[0], stop=iv_params[1], num=iv_params[2])

        for i in range(iv_data.shape[1]):
            csvwriter.writerow([str(iv_data[0,i]), str(iv_data[1,i])])
btn_save.clicked.connect(save_iv)


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
