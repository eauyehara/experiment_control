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
        self.feedback_state = 0
        self.Kp =-20

        self.target_wl = Q_(550.0, 'nm')
        self.hr4000_params={'IntegrationTime_micros':100000}
        self.smu_channel = 1
        self.smu_bias = Q_(0.0, 'V')
        self.motor_steps = 0

        self.initialize_instruments()

        self.initialize_gui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_live_spectra)
        self.timer.start(Window.timer_factor*self.hr4000_params['IntegrationTime_micros']) # in msec

    def initialize_gui(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowTitle("POE Super Continuum Source Filter Control!")
        # self.setWindowIcon(QtGui.QIcon('pythonlogo.png'))

        # Menu definition
        mainMenu = self.menuBar()

        ## File menu
        fileMenu = mainMenu.addMenu('&File')

        extractAction = QtGui.QAction("&Quit Application", self)
        extractAction.setShortcut("Ctrl+Q")
        extractAction.setStatusTip('Leave The App')
        extractAction.triggered.connect(self.close_application)
        fileMenu.addAction(extractAction)

        ## Experiments menu
        experimentMenu = mainMenu.addMenu('&Experiments')

        measIllumAction = QtGui.QAction("Measure &Illumination", self)
        measIllumAction.setShortcut("Ctrl+I")
        measIllumAction.setStatusTip('Place over power meter to measure illumination')
        measIllumAction.triggered.connect(self.exp_illum)
        experimentMenu.addAction(measIllumAction)

        measPhotocurrentAction = QtGui.QAction("Measure &Photocurrent", self)
        measPhotocurrentAction.setShortcut("Ctrl+P")
        measPhotocurrentAction.setStatusTip('Place over device to measure Photocurrent')
        measPhotocurrentAction.triggered.connect(self.exp_photocurrent)
        experimentMenu.addAction(measPhotocurrentAction)

        # Generate status bar
        self.statusBar()

        # Set Window as central widget
        self.w = QtGui.QWidget()
        self.setCentralWidget(self.w)

        ## Create a grid layout to manage the widgets size and position
        self.layout = QtGui.QGridLayout()
        self.w.setLayout(self.layout)

        ## Add widgets to the layout in their proper positions
        self.layout.addWidget(QtGui.QLabel('Device Name'), 0, 0, 1,1)

        self.edit_deviceName = QtGui.QLineEdit('TC0')
        self.layout.addWidget(self.edit_deviceName, 0, 1, 1,1)

        self.btn_setdirec = QtGui.QPushButton('Set Data Directory')
        self.btn_setdirec.clicked.connect(self.set_directory)
        self.layout.addWidget(self.btn_setdirec, 0, 2, 1,1) # Set directory button

        self.btn_save = QtGui.QPushButton('Save Spectra')
        self.btn_save.clicked.connect(self.save_spectra)
        self.layout.addWidget(self.btn_save, 0, 3, 1,1) # save spectra button

        row = 1
        if self.spec is not None:
            self.layout.addWidget(QtGui.QLabel('Integration Time [usec]'), row,0, 1,1)

            self.edit_intTime = QtGui.QLineEdit('{:d}'.format(self.hr4000_params['IntegrationTime_micros']))
            self.edit_intTime.editingFinished.connect(self.set_spec_params)
            self.layout.addWidget(self.edit_intTime, row, 1,  1,1)

            self.btn_setparam = QtGui.QPushButton('Set Spectrometer Params')
            self.btn_setparam.clicked.connect(self.set_spec_params)
            self.layout.addWidget(self.btn_setparam, row, 2,  1,1) # Set parameters button

            row = row+1

        self.layout.addWidget(QtGui.QLabel('Target Wavelength [nm]'), row,0, 1,1)

        self.edit_wavelength = QtGui.QLineEdit('{0.magnitude}'.format(self.target_wl))
        self.edit_wavelength.editingFinished.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))
        self.layout.addWidget(self.edit_wavelength, row, 1,  1,1)

        self.btn_wavelength = QtGui.QPushButton('Set Wavelength')
        self.btn_wavelength.clicked.connect(lambda : self.set_wavelength(wavelength=Q_(float(self.edit_wavelength.text()), 'nm')))
        self.layout.addWidget(self.btn_wavelength, row, 2,  1,1) # Set wavelength button

        row = row+1

        # Motor UI elements
        if self.mc is not None:
            self.layout.addWidget(QtGui.QLabel('Kp [<0]'), row,0,  1,1)

            self.edit_kp = QtGui.QLineEdit('{}'.format(self.Kp))
            self.edit_kp.editingFinished.connect(lambda: self.set_feedback_params(Kp=float(self.edit_kp.text())))
            self.layout.addWidget(self.edit_kp, row, 1, 1,1)

            self.check_feedback = QtGui.QCheckBox('Feedback')
            self.check_feedback.stateChanged.connect(self.toggle_feedback)
            self.layout.addWidget(self.check_feedback, row, 2, 1,1)

            row = row+1

            self.layout.addWidget(QtGui.QLabel('Motor steps [-60,000~60,000]'), row,0,  1,1)

            self.edit_motor = QtGui.QLineEdit('0')
            # self.edit_motor.editingFinished.connect(lambda: self.mc.go_steps(N=int(self.edit_motor.text())))
            self.layout.addWidget(self.edit_motor, row, 1, 1,1)

            self.btn_motor = QtGui.QPushButton('Move motor')
            self.btn_motor.clicked.connect(lambda: self.mc.go_steps(N=int(self.edit_motor.text())))
            self.layout.addWidget(self.btn_motor, row, 2, 1,1)

            row = row+1


        self.label_wavelength = QtGui.QLabel('Peak Wavelength:')
        self.label_wavelength.setStyleSheet("font: bold 14pt Arial")
        self.layout.addWidget(self.label_wavelength, row, 0,  1,3)

        row = row+1

        # Power meter related UI elements
        if self.pm is not None:
            self.label_illumpower = QtGui.QLabel('Illumination Power: ')
            self.label_illumpower.setStyleSheet("font: bold 14pt Arial")
            self.layout.addWidget(self.label_illumpower, row, 0, 1, 3)

            row = row+1

        # SMU UI elements
        if self.smu is not None:
            self.layout.addWidget(QtGui.QLabel('SMU channel [1~4]'), row,0,  1,1)

            self.edit_channel = QtGui.QLineEdit('{}'.format(self.smu_channel))
            self.edit_channel.editingFinished.connect(self.set_smu_params)
            self.layout.addWidget(self.edit_channel, row, 1,  1,1)

            self.layout.addWidget(QtGui.QLabel('SMU voltage [V]'), row,2,  1,1)

            self.edit_bias = QtGui.QLineEdit('{:.4g}'.format(self.smu_bias.magnitude))
            self.edit_bias.editingFinished.connect(self.set_smu_params)
            self.layout.addWidget(self.edit_bias, row, 3,  1,1)

            row = row+1

            self.label_photocurrent = QtGui.QLabel('Photocurrent:')
            self.label_photocurrent.setStyleSheet("font: bold 14pt Arial")
            self.layout.addWidget(self.label_photocurrent, row, 0, 1, 3)

            row = row+1

        # Plot of spectra
        self.p = pg.PlotWidget()
        self.xlabel = self.p.setLabel('bottom',text='Wavelength',units='nm')
        self.ylabel = self.p.setLabel('left',text='Counts',units='Arb. Unit')
        self.layout.addWidget(self.p, 0, 4, row, row+2)

        # Equalizes column stretch factor
        for i in range(self.layout.columnCount()):
            self.layout.setColumnStretch(i, 1)
        # self.layout.setColumnStretch(4, 10)

        self.show()

    def initialize_instruments(self):
        # Initialize HR4000 Spectrometer
        try:
            import seabreeze.spectrometers as sb

            self.hr4000_params={'IntegrationTime_micros':200000}

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
            self.mc.set_steprate(R=245, S=1, F=20)

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


    # UI Event handlers
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

        self.statusBar().showMessage('Setting wavelength to {:.4g~}'.format(wavelength.to_compact()), 5000)

    def toggle_feedback(self, state):
        self.feedback_state = int(state)
        if state >0:
            self.statusBar().showMessage('Feedback On', 1000)
        else:
            self.statusBar().showMessage('Feedback Off', 1000)

    def set_feedback_params(self, Kp):
        self.Kp=Kp

        self.statusBar().showMessage('Set feedback gains', 1000)

    # Timer event handler
    def refresh_live_spectra(self):
        if self.spec is not None:
            # print('Refreshing plot')
            self.spectra_data = np.transpose( self.spec.spectrum() )
            self.p.plot(self.spectra_data, clear=True)

            # refresh peak wavelength
            # print(self.spectra_data.shape)
            self.current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
            self.label_wavelength.setText("Peak wavelength {:.4g~}".format(self.current_wl.to_compact()))

        if self.smu is not None:
            self.label_photocurrent.setText('Photocurrent: {:.4g~}'.format(self.smu.measure_current().to_compact()))

        if self.pm is not None:
            self.label_illumpower.setText('Illumination Power: {:.4g~}'.format(self.pm.power().to_compact()))

        if self.mc is not None:
            if self.feedback_state > 0:
                # Kp = -20
                error = self.target_wl-self.current_wl
                drive = np.clip(int(self.Kp*error.magnitude), -5000, 5000)

                print("adusting feedback drive steps: {}".format(drive))
                if drive != 0:
                    self.mc.go_steps(N=drive)
                    sleep(abs(drive)/1000)

    # Menu handlers
    def exp_illum(self):
        print('Measuring Illumination')
        pass

    def exp_photocurrent(self):
        print('Measuring photocurrent')
        pass

    def close_application(self):
        sys.exit()

def run():
    app = QtGui.QApplication(sys.argv)
    GUI = Window()
    sys.exit(app.exec_())

# run application
run()
