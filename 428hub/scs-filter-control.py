#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
YSL Supercontinuum Source Filter controller
Required Instruments:
1. Ocean Optics HR4000 spectrometer
2. Klinger Scientific CC1.1 Motor controller
3. Power meter (ILX Lightwave OMM-6810B)
4. Source meter (HP 4156C)

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
from instrumental import Q_


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



# # Functions from client script
# def get_val():
#     val = get_sp()
#     return val

# GUI
class Window(QtGui.QMainWindow):
    # Initialize class variables
    timer_factor = 1.2e-3

    def __init__(self):

        # Initialize instance variables
        self.spectra_data = np.array([])
        self.current_wl = Q_(0.0, 'nm')
        self.data_dir = path.normpath('./')

        self.target_wl = Q_(550.0, 'nm')
        self.hr4000_params={'IntegrationTime_micros':100000}
        self.smu_channel = 1
        self.smu_bias = Q_(0.0, 'V')

        self.initialize_gui()

        self.initialize_instruments()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_live_spectra)
        self.timer.start(Window.timer_factor*self.hr4000_params['IntegrationTime_micros']) # in msec

    def initialize_gui(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 600)
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

        self.edit_intTime = QtGui.QLineEdit('{:d}'.format(self.hr4000_params['IntegrationTime_micros']))
        self.edit_intTime.editingFinished.connect(self.set_spec_params)
        self.btn_setparam = QtGui.QPushButton('Set Spectrometer Params')
        self.btn_setparam.clicked.connect(self.set_spec_params)

        self.edit_deviceName = QtGui.QLineEdit('TC0')
        self.btn_setdirec = QtGui.QPushButton('Set Data Directory')
        self.btn_setdirec.clicked.connect(self.set_directory)

        self.edit_wavelength = QtGui.QLineEdit('{0.magnitude}'.format(self.target_wl))
        self.btn_wavelength = QtGui.QPushButton('Set Wavelength')
        self.edit_wavelength.editingFinished.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))
        self.btn_wavelength.clicked.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))

        self.label_wavelength = QtGui.QLabel('Peak Wavelength: nm')
        self.label_wavelength.setStyleSheet("font: bold 14pt Arial")

        # SMU UI elements
        self.edit_channel = QtGui.QLineEdit('{}'.format(self.smu_channel))
        self.edit_channel.editingFinished.connect(self.set_smu_params)
        self.edit_bias = QtGui.QLineEdit('{:.4g}'.format(self.smu_bias.magnitude))
        self.edit_bias.editingFinished.connect(self.set_smu_params)

        self.label_photocurrent = QtGui.QLabel('Photocurrent: A')
        self.label_photocurrent.setStyleSheet("font: bold 14pt Arial")

        self.label_illumpower = QtGui.QLabel('Illumination Power: ')
        self.label_illumpower.setStyleSheet("font: bold 14pt Arial")


        # Plot of spectra
        self.p = pg.PlotWidget()
        self.xlabel = self.p.setLabel('bottom',text='Wavelength',units='nm')
        self.ylabel = self.p.setLabel('left',text='Counts',units='Arb. Unit')

        ## Create a grid layout to manage the widgets size and position
        # print('Setting grid layout')
        self.layout = QtGui.QGridLayout()
        self.w.setLayout(self.layout)

        ## Add widgets to the layout in their proper positions
        self.layout.addWidget(QtGui.QLabel('Device Name'), 0, 0, 1,1)
        self.layout.addWidget(self.edit_deviceName, 0, 1, 1,1)
        self.layout.addWidget(self.btn_setdirec, 0, 2, 1,1) # Set directory button
        self.layout.addWidget(self.btn_save, 0, 3, 1,1) # save spectra button

        self.layout.addWidget(QtGui.QLabel('Integration Time [usec]'), 1,0, 1,1)
        self.layout.addWidget(self.edit_intTime, 1, 1,  1,1)
        self.layout.addWidget(self.btn_setparam, 1, 2,  1,1) # Set parameters button

        self.layout.addWidget(QtGui.QLabel('Target Wavelength [nm]'), 2,0, 1,1)
        self.layout.addWidget(self.edit_wavelength, 2, 1,  1,1)
        self.layout.addWidget(self.btn_wavelength, 2, 2,  1,1) # Set wavelength button
        self.layout.addWidget(self.label_wavelength, 3, 0,  1,3)

        self.layout.addWidget(QtGui.QLabel('SMU channel [1~4]'), 4,0,  1,1)
        self.layout.addWidget(self.edit_channel, 4, 1,  1,1)
        self.layout.addWidget(QtGui.QLabel('SMU voltage [V]'), 4,2,  1,1)
        self.layout.addWidget(self.edit_bias, 4, 3,  1,1)
        self.layout.addWidget(self.label_photocurrent, 5, 0, 1, 3)
        self.layout.addWidget(self.label_illumpower, 6, 0, 1, 3)

        self.layout.addWidget(self.p, 0, 4, 6, 10) # Plot on right spans 8x8

        # Equalizes column stretch factor
        for i in range(3):
            self.layout.setColumnStretch(i, 1)
        self.layout.setColumnStretch(4, 10)
        self.show()

    def initialize_instruments(self):

        # Initialize HR4000 Spectrometer
        import seabreeze.spectrometers as sb
        self.hr4000_params={'IntegrationTime_micros':200000}

        try:
            devices = sb.list_devices()
            self.spec = sb.Spectrometer(devices[0])
        except:
            print('HR4000 Spectrometer not connected')
            self.spec = None
        else:
            self.spec.integration_time_micros(self.hr4000_params['IntegrationTime_micros'])

        # Initialize Motor controller
        try:
            from instrumental.drivers.motion.klinger import KlingerMotorController

            self.mc = KlingerMotorController(visa_address='GPIB0::8::INSTR')
        except:
            print('Klinger Motor controller not connected')
            self.mc = None
        else:
            # Set motor at high speed
            self.mc.set_steprate(R=254, S=1, F=29)

        # Initialize Power meter
        try:
            from instrumental.drivers.powermeters.ilx_lightwave import OMM_6810B

            self.pm = OMM_6810B(visa_address='GPIB0::2::INSTR')
        except:
            print('OMM-6810B Power meter not connected')
            self.pm = None
        else:
            self.pm.wavelength = self.target_wl
            self.pm.set_no_filter()

        # Initialize Source meter
        try:
            from instrumental.drivers.sourcemeasureunit.hp import HP_4156C

            self.smu = HP_4156C(visa_address='GPIB0::17::INSTR')
        except:
            print('HP 4156C Parameter Analyzer not connected')
            self.smu = None
        else:
            self.smu.set_integration_time('short')


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
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def set_spec_params(self):
        self.timer.stop()

        self.hr4000_params['IntegrationTime_micros'] = float(self.edit_intTime.text())
        # spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set spectrometer parameters', 5000)

    def set_smu_params(self):
        try:
            self.smu_channel = int(self.edit_channel.text())
        except:
            self.statusBar().showMessage('Invalid input for SMU channel', 3000)
            self.smu_channel = 1
            self.edit_channel.setText('1')

        try:
            self.smu_bias = Q_(float(self.edit_bias.text()), 'V')
        except:
            self.statusBar().showMessage('Invalid input for SMU voltage', 3000)
            self.smu_bias = Q_(0.0, 'V')
            self.edit_channel.setText('0.0')

        if self.smu is not None:
            self.smu.set_channel(channel=self.smu_channel)
            self.smu.set_voltage(voltage=self.smu_bias)
            self.statusBar().showMessage('Setting SMU channel {} to {:.4g~}'.format(self.smu_channel, self.smu_bias), 3000)

    def set_directory(self):
        self.timer.stop()
        self.data_dir = QtGui.QFileDialog.getExistingDirectory()

        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set data directory to {}'.format(self.data_dir), 5000)

    def set_wavelength(self, wavelength):
        if self.pm is not None:
            self.pm.wavelength = wavelength

        self.statusBar().showMessage('Setting wavelength to {:.4~P}'.format(wavelength), 5000)

    def refresh_live_spectra(self):
        if self.spec is not None:
            # print('Refreshing plot')
            self.spectra_data = np.transpose( self.spec.spectrum() )
            self.p.plot(self.spectra_data, clear=True)

            # refresh peak wavelength
            # print(self.spectra_data.shape)
            self.current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
            self.label_wavelength.setText("Peak wavelength {:.4g~}".format(self.current_wl))

        if self.smu is not None:
            self.label_photocurrent.setText('Photocurrent: {:.4e~}'.format(self.smu.measure_current()))

        if self.pm is not None:
            self.label_illumpower.setText('Illumination Power: {:.4e~}'.format(self.pm.power()))

    def close_application(self):
        sys.exit()

def run():
    app = QtGui.QApplication(sys.argv)
    GUI = Window()
    sys.exit(app.exec_())

# run application
run()
