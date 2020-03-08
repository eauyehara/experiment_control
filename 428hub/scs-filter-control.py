#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
YSL Supercontinuum Source Filter controller
Required Instruments:
1. Ocean Optics HR4000 spectrometer
2. Klinger Scientific CC1.1 Motor controller
3. Source meter (Todo)
4. Power meter (Todo)
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


Npts = 500
wait_sec = 2
sample_time_sec = 0.45 # estimate of time taken by server to return value
rescale = True

# ### set up TCP communication ################
# HOST, PORT = "localhost", 9997
# data = " ".join(sys.argv[1:])
#
# width_pix = 1280
# height_pix = 960
# ##############################################

# Initialize instruments
import seabreeze.spectrometers as sb

# Global variables


# # Functions from client script
# def get_val():
#     val = get_sp()
#     return val

# GUI
class Window(QtGui.QMainWindow):

    def __init__(self):
        global timer_factor

        # Initialize class variables
        timer_factor = 1.2e-3
        # Initialize instance variables
        self.spectra_data = np.array([])
        self.data_dir = path.normpath('./')
        self.hr4000_params={'IntegrationTime_micros':100000}

        self.initialize_gui()

        self.initialize_instruments()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_live_spectra)
        self.timer.start(timer_factor*self.hr4000_params['IntegrationTime_micros']) # in msec

    def initialize_gui(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1280, 960)
        self.setWindowTitle("POE Super Continuum Source Filter Control!")
        # self.setWindowIcon(QtGui.QIcon('pythonlogo.png'))

        extractAction = QtGui.QAction("&Quit Application", self)
        extractAction.setShortcut("Ctrl+Q")
        extractAction.setStatusTip('Leave The App')
        extractAction.triggered.connect(self.close_application)

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(extractAction)

        # print('Basic window generated')
        self.w = QtGui.QWidget()
        self.setCentralWidget(self.w)

        ## Create some widgets to be placed inside
        # print('Adding buttons')
        self.btn_save = QtGui.QPushButton('Save Spectra')
        self.btn_save.clicked.connect(self.save_spectra)

        self.edit_intTime = QtGui.QLineEdit('{:f}'.format(self.hr4000_params['IntegrationTime_micros']))
        self.btn_setparam = QtGui.QPushButton('Set Spectrometer Params')
        self.btn_setparam.clicked.connect(self.set_measurement_params)

        self.edit_deviceName = QtGui.QLineEdit('TC0')
        self.btn_setdirec = QtGui.QPushButton('Set Data Directory')
        self.btn_setdirec.clicked.connect(self.set_directory)

        self.edit_wavelength = QtGui.QLineEdit('550')
        self.btn_wavelength = QtGui.QPushButton('Set Wavelength')
        self.btn_wavelength.clicked.connect(lambda : self.set_wavelength(wavelength=float(self.edit_wavelength.text())))

        self.p = pg.PlotWidget()
        self.xlabel = self.p.setLabel('bottom',text='Wavelength',units='nm')
        self.ylabel = self.p.setLabel('left',text='Counts',units='Arb. Unit')

        ## Create a grid layout to manage the widgets size and position
        # print('Setting grid layout')
        self.layout = QtGui.QGridLayout()
        self.w.setLayout(self.layout)

        ## Add widgets to the layout in their proper positions
        self.layout.addWidget(QtGui.QLabel('Device Name'), 0, 0)
        self.layout.addWidget(self.edit_deviceName, 0, 1) # save spectra button
        self.layout.addWidget(self.btn_save, 1, 0) # save spectra button

        self.layout.addWidget(QtGui.QLabel('Integration Time [usec]'), 2,0)
        self.layout.addWidget(self.edit_intTime, 2, 1)
        self.layout.addWidget(self.btn_setparam, 3, 0) # Set parameters button
        self.layout.addWidget(self.btn_setdirec, 4, 0) # Set directory button

        self.layout.addWidget(QtGui.QLabel('Target Wavelength [nm]'), 5,0)
        self.layout.addWidget(self.edit_wavelength, 5, 1)
        self.layout.addWidget(self.btn_wavelength, 6, 0) # Set wavelength button

        self.layout.addWidget(self.p, 0, 2, 8, 8) # Plot on right spans 8x8

        # self.layout.addWidget(statusbar, 8,0, 1,10)

        self.show()

    def initialize_instruments(self):
        # Initialize HR4000 Spectrometer
        # HR4000 parameters
        self.hr4000_params={'IntegrationTime_micros':200000}

        devices = sb.list_devices()
        if len(devices)>0:
            self.spec = sb.Spectrometer(devices[0])
            self.spec.integration_time_micros(self.hr4000_params['IntegrationTime_micros'])
        else:
            print('HR4000 Spectrometer not connected')
            self.spec = None

    # Event handlers
    def save_spectra(self):
        self.timer.stop()
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

        # Save csv
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.csv'
        fpath = path.normpath(path.join(self.data_dir,fname))

        with open(fpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Wavelength nm', 'Count', 'Integration time', str(self.hr4000_params['IntegrationTime_micros'])])

            for i in range(self.spectra_data.shape[0]):
                csvwriter.writerow([str(self.spectra_data[i,0]), str(self.spectra_data[i,1])])

        # Save png
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.png'
        fpath = path.normpath(path.join(self.data_dir,fname))

        # QtGui.QApplication.processEvents()
        # create an exporter instance, as an argument give it
        # the item you wish to export
        exporter = pg.exporters.ImageExporter(self.p.scene())
        exporter.export(fpath)

        self.statusBar().showMessage('Saved spectra to {}'.format(fpath), 5000)
        # restart timer
        self.timer.start(max([timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def set_measurement_params(self):
        self.timer.stop()

        self.hr4000_params['IntegrationTime_micros'] = float(self.edit_intTime.text())
        # spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])
        self.timer.start(max([timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set spectrometer parameters', 5000)


    def set_directory(self):
        self.timer.stop()
        self.data_dir = QtGui.QFileDialog.getExistingDirectory()

        self.timer.start(max([timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set data directory to {}'.format(self.data_dir), 5000)

    def set_wavelength(self, wavelength):
        # self.timer.stop()
        # data_dir = QtGui.QFileDialog.getExistingDirectory()
        #
        # self.timer.start(max([timer_factor*hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Setting wavelength to {}'.format(wavelength), 5000)

    def refresh_live_spectra(self):
        if self.spec != None:
            # print('Refreshing plot')
            self.spectra_data = np.transpose( self.spec.spectrum() )

        self.p.plot(self.spectra_data, clear=True)

    def close_application(self):
        sys.exit()

def run():
    app = QtGui.QApplication(sys.argv)
    GUI = Window()
    sys.exit(app.exec_())

# run application
run()
