#----------------------------------------------------------------------------
# Name:         GPIB_manager.py
# Purpose:      Controller for all the instruments to do characterization
#               of optical and electrical devices
#
# Author:       Marc de Cea, lightly based on Jason Orcutt's code
#
# Created:      28 June 2019
# Copyright:    (c) 2019 by Jason Orcutt
# Licence:      MIT license
#----------------------------------------------------------------------------

# The main improvement of this version compared to Jason's old version
# is that now we have much more flexibility to change instruments. For
# instance, before the only way to take an IV curve was using the parameter
# analyzer. Now, any instrument that can take an IV curve can be used.

# To do so, we will require any instrument to implement Interfaces.
# For instance, if an instrument has the ability to take an IV curve, it
# will implement the interface SourceMeter, and will have to implement
# the method take_IV(), which is called by GPIBManager.
# Same with a laser, it will implement the interface LightSource and will
# have methods TurnOn and TurnOff.

# ATTENTION: CURRENTLY, WE HAVE TO SPECIFY MANUALLY THE INSTRUMENTS THAT ARE
# CONNECTED TO THE COMPUTER, AND WHICH DEVICE WILL FUNCTION AS A LIGHT SOURCE,
# WHICH AS A SOURCE METER, WHICH AS A WAVELENGTH METER...
# THIS IS DONE IN THE INITIALIZE_INSTRUMENTS() METHOD, SO IF THE SETUP
# CHANGES THAT METHOD WILL HAVE TO BE MODIFIED ACCORDINGLY.


############################################################################
############################################################################
######                                                                ######
######                       Import Dependencies                      ######
######                                                                ######
############################################################################
############################################################################

import wx
import os
import pickle
import time
import sys
import threading
import numpy as np
import scipy.io as io
import winsound
import matplotlib.pyplot as plt
import csv

# Instrument handlers
from instruments.Light_sources.MockLaser import MockLaser
from instruments.Light_sources.HPLightWave import HPLightWave
from instruments.Light_sources.SantecTSL210F import SantecTSL210F
from instruments.Light_sources.SantecTSL550 import SantecTSL550
from instruments.Power_meters.MockPowerMeter import MockPowerMeter
from instruments.Power_meters.SantecMPM200 import SantecMPM200
from instruments.Source_meters.MockSourceMeter import MockSourceMeter
from instruments.Source_meters.KeysightB2902A import KeysightB2902A
from instruments.Source_meters.Keithley2635A import Keithley2635A
from instruments.Wavelength_meters.MockWlMeter import MockWlMeter
from instruments.Wavelength_meters.BrsitolWlMeter import BristolWlMeter
from instruments.Vector_network_analyzers.HP8722D import HP8722D
from instruments.Vector_network_analyzers.MockVNA import MockVNA
from instruments.Electrical_attenuators.HP11713A import HP11713A
from instruments.Electrical_attenuators.MockElAtt import MockElAtt
from instruments.Tunable_filters.MockTunableFilter import MockTunableFilter
from instruments.Tunable_filters.AgiltronTunableFilter import AgiltronTunableFilter
from instruments.DAQ.NI_DAQ import NiDAQ


EVT_MEASURED_POWERS = 123456789  # Some random ID for the event indicating that
# powers have been measured
EVT_DONE = 123456788  # Some random ID for the event indicating that
# the window has to be closed
NUM_AVS = 4  # Number of averages for the VNA

# POWER METER CHANNELS
TAP_CHANNEL = 1  # Power meter channel connected to the tap
REC_CHANNEL = 3  # Power meter channel connected to the transmitted power

MPM200_REC_PORT = 1  # Port of the MPM200 where the output power is monitored
MPM200_TAP_PORT = 2  # Port of the MPM200 where the tap power is monitored (none if there isn't)

# NI DAQ INPUTS
AIN_RECEIVED = "Dev1/ai0"  # Analog signal corresponding to the received power
AIN_TAP = "Dev1/ai1"  # Analog signal corresponding to the tap power
PFI_CLK = "/Dev1/pfi0"  # Trigger coming from the laser

PM_AUTO_RANGE = 1000  # A number for when the power meter range is AUTO


# Helper class to handle the update of power values in the GUI
class LWMainEvent(wx.PyEvent):

    def __init__(self, _through_loss, _input_power,
                 _rec_power, _tap_power, _photocurrent,
                 _photocurrent_2, _responsivity,
                 _qe, _wavelength):
        wx.PyEvent.__init__(self)

        self.SetEventType(EVT_MEASURED_POWERS)

        self.through_loss = _through_loss
        self.wavelength = _wavelength
        self.input_power = _input_power
        self.rec_power = _rec_power
        self.tap_power = _tap_power
        self.photocurrent = _photocurrent
        self.photocurrent_2 = _photocurrent_2
        self.responsivity = _responsivity
        self.qe = _qe


# Helper class for triggering a close window event
class DoneEvent(wx.PyEvent):

    def __init__(self, done):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_DONE)

        self.done = done

############################################################################
############################################################################
######                                                                ######
######     Threaded GPIBManager Class to Handle all Communication     ######
######                                                                ######
############################################################################
############################################################################


class GPIBManager(threading.Thread):

    def __init__(self, parent, through_loss_control):

        # invoke constructor of parent class
        threading.Thread.__init__(self)

        # Add links to the GUI frame/window
        self.parent = parent  # GUI window
        self.through_loss_control = through_loss_control
                              # Control showing transmission

        # State reporting variables initialized to 0
        self.error = 0
        self.done = 0
        self.running = 0
        self.loopActive = True

        # Wavelength specific calibration factor

        self.start_cal_wav = 1520.0
        self.stop_cal_wav = 1580.0
        self.num_cal_wavs = 70

        self.new_wavelength = -10.0
        self.new_tf_wavelength = -10.0
        self.new_power = -10.0
        self.new_pm_range = -10.0
        self.active_module = -1

        # Control loop state variables. When any of this is 1, it means that
        # the specific operation has to be performed. It is done this way so as
        # to avoid threads clashing with each other.
        self.set_new_wav = 0
        self.set_new_tf_wav = 0
        self.set_new_power = 0
        self.set_el_att = 0
        self.turn_on_laser = 0
        self.turn_off_laser = 0
        self.set_bias = 0
        self.set_bias_2 = 0
        self.tx_scan = 0
        self.tx_bias_scan = 0
        self.tx_power_scan = 0
        self.tx_time_scan = 0
        self.take_IV = 0
        self.take_RLV = 0
        self.take_RLP = 0
        self.take_bw_vs_v = 0
        self.take_vna_trace = 0
        self.start_vna_trace = 0
        self.take_trans_output_curve = 0
        self.take_pv_mod_outp = 0
        self.calibration = 0
        self.ds_current = 0
        self.set_new_pm_range = 0
        self.no_calibration = 0
        self.user_file_path = None

        self.using_HP = False
        self.tf_with_laser = False  # Tracks if the user wants the tunable filter to track the laser wavelength
        self.sweep_daq_acq = True  # Use the DAQ board to take wavelength sweeps?
        self.store_current = False  # Measure current when taking wavelength sweeps?

        # How many loops do we wait to ask again for power and photocurrent data?
        self.power_meter_poll_delay = 1  # Ask for power values every cycle
        self.sm_poll_delay = 40  # Ask for currents every 5 cycles

        # Control loop delay variable
        self.loop_delay_time = 100e-4 # 1e-4

        # Connect to the instruments that we care about
        self.source_meter = None
        self.light_source = None
        self.wavelength_meter = None
        self.power_meter = None
        self.tunable_filter = None
        self.vna = None
        self.el_att = None
        self.ni_daq = None
        self.source_meter_2 = None  # Source meter to take transistor output curves
        self.connect_instruments()

    def connect_instruments(self):
        """
        Connects to the relevant instruments that are currently connected in the
        setup.

        EVERY TIME THE SETUP CHANGES, THIS METHOD HAS TO BE MODIFIED!!!

        At the time this was written, 4 main functionalities are sought:
        - Light Source (self.light_source)
        - Power Meter (self.power_meter)
        - Wavelength Meter (self.wl_meter)
        - Source Meter (self.source_meter)

        If there is no instrument with this functionality,
        set it to XXXMock (which is an implementation that does not do anything)

        :return: None
        """

        print('Starting connection')
        # Power meter
        # self.power_meter = HPLightWave(tap_channel=TAP_CHANNEL, rec_channel=REC_CHANNEL)
        self.power_meter = SantecMPM200(rec_port=MPM200_REC_PORT, tap_port=MPM200_TAP_PORT)

        # This is necessary because the wavelength sweeps will be different depending on if we use
        # the MPM200, the DAQ or the HP lightwave
        if isinstance(self.power_meter, SantecMPM200):
            self.using_MPM200 = True
        else:
            self.using_MPM200 = False

        # self.power_meter = MockPowerMeter()

        # Light sources
        # self.light_source = self.power_meter  # The HP lightwave is both a
                                                # laser and a power meter

        # self.light_source = MockLaser()
        # self.light_source = SantecTSL210F()
        self.light_source = SantecTSL550()

        if self.light_source == self.power_meter:
            self.using_HP = True  # To avoid initializing a resource twice when using the HP

        # Wavelength meter
        self.wavelength_meter = MockWlMeter()
        # self.wavelength_meter = BristolWlMeter()

        # Source meter
        self.source_meter = Keithley2635A()
        # self.source_meter = ParameterAnalyzer()
        # self.source_meter = MockSourceMeter()

        # Source meter 2 (if connected, to take transistor output curves)
        # self.source_meter_2 = Keithley2635A()
        # self.source_meter_2 = ParameterAnalyzer()
        # self.source_meter_2 = KeysightB2902A()
        self.source_meter_2 = MockSourceMeter()

        # VNA
        self.vna = HP8722D()
        # self.vna = MockVNA()

        # Electrical attenuator
        self.el_att = HP11713A()
        # self.el_att = MockElAtt()

        # Tunable filter
        # self.tunable_filter = AgiltronTunableFilter()
        self.tunable_filter = MockTunableFilter()

        # DAQ
        self.ni_daq = NiDAQ()

    def run(self):
        """
        This is the main code that gets called in a loop. It checks if there is
        any operation that needs to be done, and if so it does it. If not,
        it just gets power information and updates the GUI.

        When you call the start method, threading makes
        sure run gets called to start polling

        :return: None
        """
        # If there was some sort of error, don't start.
        if self.error == 0:

            # state that you are running.
            self.running = 1

            self.initialize_instruments()

            # Initialize Loop Variables
            # Counters for the number of cycles since the last polling of powers
            # and currents
            power_meter_wait_counter = 1
            sm_wait_counter = 10

            # Initialize variables
            measured_input_power = 0
            measured_wavelength = 0
            through_loss = 0
            measured_received_power = 0
            tap_power = 0
            responsivity = 0
            qe = 0
            photocurrent = 0
            photocurrent_2 = 0

            # As long as the thread thinks it's supposed to be running, it will.
            while self.running != 0:

                sys.stdout.flush()  # Fix for printing in MINGW

                try:

                    if self.loopActive:
                        update = 0

                        # Get power values if it is time for it
                        if power_meter_wait_counter >= self.power_meter_poll_delay:
                            update = 1
                            power_meter_wait_counter = 0

                            through_loss, measured_input_power, measured_received_power, tap_power \
                                = self.analyze_powers(calibration=True)

                            measured_wavelength = self.wavelength_meter.get_wavelength()

                        # Get current values if it is time for it
                        if sm_wait_counter >= self.sm_poll_delay:
                            update = 1
                            sm_wait_counter = 0

                            photocurrent = self.source_meter.measure_current()
                            photocurrent_2 = self.source_meter_2.measure_current()

                            responsivity = photocurrent / (measured_input_power + 1.0e-15)
                            if measured_wavelength != 0:
                                qe = responsivity * 1.24 / measured_wavelength * 100.0
                            else:
                                qe = responsivity * 1.24 / self.new_wavelength * 100.0

                        # If there is sth to be updated, do it
                        if update:

                            wx.PostEvent(self.through_loss_control,
                                         LWMainEvent(through_loss,
                                                     measured_input_power, measured_received_power,
                                                     tap_power, photocurrent, photocurrent_2, responsivity, qe,
                                                     measured_wavelength))

                        # Go through each possible operation and perform it if
                        # user requested so

                        if self.set_new_wav == 1:
                            print("Setting Wavelength...")
                            self.set_new_wav = 0
                            self.light_source.set_wavelength(self.new_wavelength)
                            self.power_meter.set_wavelength(self.new_wavelength)
                            # Set unable filter wavelength if necessary
                            if self.tf_with_laser:
                                self.tunable_filter.set_wavelength(self.new_wavelength)

                        if self.set_new_pm_range == 1:
                            print("Setting power Meter Range...")
                            self.set_new_pm_range = 0

                            if self.new_pm_range == PM_AUTO_RANGE:
                                self.power_meter.set_range(3, 'AUTO')
                            else:
                                self.power_meter.set_range(3, self.new_pm_range)

                        if self.set_new_tf_wav == 1:
                            print("Setting Tunable Filter Wavelength...")
                            self.set_new_tf_wav = 0
                            self.tunable_filter.set_wavelength(self.new_tf_wavelength)

                        if self.set_new_power == 1:
                            print("Setting Output Power...")
                            self.set_new_power = 0
                            self.light_source.set_power(self.new_power)

                        if self.turn_on_laser == 1:
                            print("Laser Turn On...")
                            self.turn_on_laser = 0
                            self.light_source.turn_on()

                        if self.set_bias == 1:
                            print("Setting Bias...")
                            self.set_bias = 0
                            self.source_meter.set_voltage(self.parent.pd_bias)
                            time.sleep(0.5)

                        if self.set_bias_2 == 1:
                            print("Setting Bias...")
                            self.set_bias_2 = 0
                            self.source_meter_2.set_voltage(self.parent.pd_bias_2)
                            time.sleep(0.5)

                        if self.turn_off_laser == 1:
                            print("Laser Turn Off...")
                            self.turn_off_laser = 0
                            self.light_source.turn_off()

                        if self.set_el_att == 1:
                            print("Setting electrical attenuation...")
                            self.set_el_att = 0
                            self.el_att.set_attenuation(self.parent.el_att)

                        if self.calibration == 1:
                            self.calibration = 0
                            self.perform_calibration()

                        if self.no_calibration == 1:
                            self.no_calibration = 0
                            self.perform_no_calibration()

                        if self.tx_scan == 1:
                            self.tx_scan = 0
                            self.perform_tx_measurement()

                        if self.tx_bias_scan == 1:
                            self.tx_bias_scan = 0
                            self.perform_tx_bias_measurement()

                        if self.tx_power_scan == 1:
                            self.tx_power_scan = 0
                            self.perform_tx_power_scan()

                        if self.tx_time_scan == 1:
                            self.tx_time_scan = 0
                            self.perform_tx_time_measurement()

                        if self.take_IV == 1:
                            self.take_IV = 0
                            self.perform_iv_measurement()

                        if self.take_RLV == 1:
                            self.take_RLV = 0
                            self.perform_rlv_measurement()

                        if self.take_RLP == 1:
                            self.take_RLP = 0
                            self.perform_rlp_measurement()

                        if self.take_bw_vs_v == 1:
                            self.take_bw_vs_v = 0
                            self.perform_bw_vs_v()

                        if self.take_vna_trace == 1:
                            self.take_vna_trace = 0
                            self.retrieve_vna_trace()

                        if self.start_vna_trace == 1:
                            self.start_vna_trace = 0
                            self.start_vna_trace_trigger()

                        if self.take_trans_output_curve == 1:
                            self.take_trans_output_curve = 0
                            self.perform_transistor_output_curve()

                        if self.take_pv_mod_outp == 1:
                            self.take_pv_mod_outp = 0
                            self.perform_pv_mod_output_curve()

                    # Increase cycle counter
                    power_meter_wait_counter = power_meter_wait_counter + 1
                    sm_wait_counter = sm_wait_counter + 1

                    # Wait time until next cycle
                    time.sleep(self.loop_delay_time)

                except Exception as ex:
                    print("I had an error: %s" % ex)
                    self.running = 0
                    self.error = 1

        # If we get here, either an error occurred or it was told to stop running.

        # Start turn off routine by closing instruments.
        self.close_instruments()
        self.done = 1
        # Close window
        wx.PostEvent(self.through_loss_control, DoneEvent(1))

    def initialize_instruments(self):
        """
        Initializes the connected instruments.

        :return: None
        """
        if self.light_source:
            print("Intializing Laser...")
            self.light_source.initialize()

        if self.power_meter and not self.using_HP:
            print("Intializing Power Meter...")
            self.power_meter.initialize()

        if self.wavelength_meter:
            print("Intializing Wavelength Meter...")
            self.wavelength_meter.initialize()

        if self.source_meter:
            print("Intializing Source Meter...")
            self.source_meter.initialize()

        if self.source_meter_2:
            print("Intializing Source Meter 2...")
            self.source_meter_2.initialize()

        if self.vna:
            print("Intializing VNA...")
            self.vna.initialize()

        if self.el_att:
            print("Intializing Electrical Attenuator...")
            self.el_att.initialize()

        if self.tunable_filter:
            print("Intializing Tunable Filter...")
            self.tunable_filter.initialize()

        if self.ni_daq:
            print("Intializing DAQ...")
            self.ni_daq.initialize()

    def close_instruments(self):
        """
        Closes the connected instruments.

        :return: None
        """
        if self.light_source:
            print("Closing Laser...")
            self.light_source.close()

        if self.power_meter and not self.using_HP:
            print("Closing Power Meter...")
            self.power_meter.close()

        if self.wavelength_meter:
            print("Closing Wavelength Meter...")
            self.wavelength_meter.close()

        if self.source_meter:
            print("Closing Source Meter...")
            self.source_meter.close()

        if self.vna:
            print("Closing VNA...")
            self.vna.close()

        if self.el_att:
            print("Closing Electrical Attenuator...")
            self.el_att.close()

        if self.tunable_filter:
            print("Closing Tunable Filter...")
            self.tunable_filter.close()

        if self.ni_daq:
            print("Closing DAQ...")
            self.ni_daq.close()

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # These are simple setters for the variables that control which
    # oepration to perform. These are called from the photonmover_frontend.

    def close(self):
        self.running = 0

    def turn_on_laser_f(self):
        self.turn_on_laser = 1

    def turn_off_laser_f(self):
        self.turn_off_laser = 1

    def set_bias_f(self):
        self.set_bias = 1

    def set_bias_2_f(self):
        self.set_bias_2 = 1

    def set_electrical_att(self):
        self.set_el_att = 1

    def set_wavelength(self, wavelength):
        self.new_wavelength = wavelength
        self.set_new_wav = 1

    def set_tf_wavelength(self, tf_wavelength):
        self.new_tf_wavelength = tf_wavelength
        self.set_new_tf_wav = 1

    def set_tf_w_laser(self, tf_w_laser):
        self.tf_with_laser = tf_w_laser

    def set_DAQ_acq(self, daq_acq):
        self.sweep_daq_acq = daq_acq

    def set_store_current(self, store_current):
        self.store_current = store_current

    def set_power(self, power):
        self.new_power = power
        self.set_new_power = 1

    def set_pm_range(self, range):
        self.new_pm_range = range
        self.set_new_pm_range = 1

    def calibration_f(self):
        self.calibration = 1

    def no_calibration_f(self):
        self.no_calibration = 1

    def tx_scan_f(self, user_file_path, power_range):
        self.user_file_path = user_file_path
        self.tx_scan = 1
        self.power_range = power_range

    def tx_bias_scan_f(self, user_file_path, power_range):
        self.user_file_path = user_file_path
        self.tx_bias_scan = 1
        self.power_range = power_range

    def tx_power_scan_f(self, user_file_path, power_range):
        self.user_file_path = user_file_path
        self.tx_power_scan = 1
        self.power_range = power_range

    def tx_time_scan_f(self, user_file_path, power_range):
        self.user_file_path = user_file_path
        self.tx_time_scan = 1
        self.power_range = power_range

    def take_IV_f(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_IV = 1

    def take_RLV_f(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_RLV = 1

    def take_RLP_f(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_RLP = 1

    def get_VNA_trace(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_vna_trace = 1

    def trigger_VNA_trace(self, user_file_path):
        self.user_file_path = user_file_path
        self.start_vna_trace = 1

    def take_output_curve(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_trans_output_curve = 1

    def meas_pv_mod_outp(self, i_ds, user_file_path):
        self.ds_current = i_ds
        self.user_file_path = user_file_path
        self.take_pv_mod_outp = 1

    def VNA_bias_wl_scan(self, user_file_path):
        self.user_file_path = user_file_path
        self.take_bw_vs_v = 1

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------

    def get_state(self):
        """
        Records the current state of the setup (wavelength, power, laser on,
        source meter voltage)
        :return: A list with the different parameters:
            [prev_wl, prev_power, laser_active, source_meter_voltage]
        """
        if self.new_wavelength > 0:
            wl = self.new_wavelength
        else:
            wl = 1550.00

        if self.new_power > 0:
            power = self.parent.power
        else:
            power = 1.00

        if self.active_module == -1:
            laser_active = True
        else:
            laser_active = False

        voltage = self.parent.pd_bias

        return [wl, power, laser_active, voltage]

    def perform_calibration(self):

        new_calibration = list()

        # SAve current state so that we can get back to it after the calibration
        [prev_wl, prev_power, laser_active, spam] = self.get_state()

        laser_power = 1.00  # mW (switchable)
        measurement_count = 10 # NUmber of times the same measurement is repeated

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        self.light_source.set_power(laser_power)

        for self.new_wavelength in np.linspace(self.start_cal_wav, self.stop_cal_wav, self.num_cal_wavs):

            self.light_source.set_wavelength(self.new_wavelength)
            self.power_meter.set_wavelength(self.new_wavelength)

            meas_list = list()

            for i in range(measurement_count):
                through_loss, measured_input_power, measured_received_power, tap_power \
                    = self.analyze_powers(calibration=False)
                ratio = 10.0 ** ((0.0 - through_loss) / 10.0)  # analyze_powers gives it in dB
                meas_list.append(ratio)

            meas_array = np.array(meas_list)
            ave_ratio = meas_array.mean()
            new_calibration.append(ave_ratio)

            print("Mean ratio for %.2fnm = %.2f" % (self.new_wavelength, ave_ratio))

        self.parent.optical_calibration = new_calibration
        self.parent.cal_set == "PATH_CALIBRATION"

        # Save the calibration into the pickle file
        pickle_file_object = open(self.parent.optical_calibration_file, 'wb')
        pickle.dump(self.parent.optical_calibration, pickle_file_object)
        pickle_file_object.close()

        # Go back to previous state
        self.light_source.set_wavelength(prev_wl)
        if not laser_active:
            self.light_source.turn_off()
        else:
            self.light_source.set_power(prev_power)

        # Plot the data
        # plt.ion()
        plt.plot(np.linspace(self.start_cal_wav, self.stop_cal_wav, self.num_cal_wavs),
                 new_calibration)
        plt.show()
        # plt.draw()
        # plt.pause(0.001)

    def perform_no_calibration(self):

        new_calibration = list()

        for self.new_wavelength in np.linspace(self.start_cal_wav, self.stop_cal_wav, self.num_cal_wavs):
            new_calibration.append(1)

        self.parent.optical_calibration = new_calibration

        pickle_file_object = open(self.parent.optical_calibration_file_None, 'wb')
        pickle.dump(self.parent.optical_calibration, pickle_file_object)
        pickle_file_object.close()
        self.parent.cal_set == "NONE"

    def retrieve_vna_trace(self, save_data=True, plot=False):
        """
        Gets the trace from the VNA
        :param save_data:
        :param plot:
        :return:
        """

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "VNA-%s--%d#%d#%d_%d#%d#%d.csv" % (meas_description,
                                                          time_tuple[0],
                                                          time_tuple[1],
                                                          time_tuple[2],
                                                          time_tuple[3],
                                                          time_tuple[4],
                                                          time_tuple[5])

            data_file = os.path.join(save_directory, filename)
        else:
            data_file = None

        meas = self.vna.read_data(file=data_file, plot_data=plot)

        print('VNA acquisition finished')

        return meas

    def start_vna_trace_trigger(self, save_data=True, plot=False):
        """
        Performs a VNA sweep and gets the trace
        :param save_data:
        :param plot:
        :return:
        """

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "VNA-%s--%d#%d#%d_%d#%d#%d.csv" % (meas_description,
                                                          time_tuple[0],
                                                          time_tuple[1],
                                                          time_tuple[2],
                                                          time_tuple[3],
                                                          time_tuple[4],
                                                          time_tuple[5])

            data_file = os.path.join(save_directory, filename)
        else:
            data_file = None

        self.vna.take_data(NUM_AVS)
        meas = self.vna.read_data(file=data_file, plot_data=plot)

        print('VNA acquisition finished')

        return meas

    def perform_bw_vs_v(self, save_data=True, plot=False):
        """
        Gets VNA traces at the voltages and wavelengths specified by the user
        in the GUI.
        """

        # Save current state so that we can get back to it after the measurement
        [prev_wl, prev_power, laser_active, prev_bias] = self.get_state()

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        start_voltage = self.parent.start_meas_v
        end_voltage = self.parent.stop_meas_v
        num_voltage = self.parent.num_meas_v

        for v_set in np.linspace(start_voltage, end_voltage, num_voltage):

            # Set the voltage
            self.source_meter.set_voltage(v_set)

            for self.new_wavelength in np.linspace(self.parent.start_meas_wl, self.parent.stop_meas_wl,
                                                  self.parent.num_meas_wl):
                # Set the wavelength
                self.light_source.set_wavelength(self.new_wavelength)
                if self.tf_with_laser:
                    self.tunable_filter.set_wavelength(self.new_wavelength)
                self.power_meter.set_wavelength(self.new_wavelength)
                time.sleep(0.4)

                # Get the VNA trace
                measurement = self.start_vna_trace_trigger(save_data=False, plot=plot)

                if save_data:

                    # Create the csv file
                    save_directory = os.path.dirname(self.user_file_path)
                    meas_description = os.path.basename(self.user_file_path)

                    time_tuple = time.localtime()
                    filename = "VNAvsV-%s--V=%dmV-wav=%.2fnm-" \
                               "%d#%d#%d_%d#%d#%d.csv" % (meas_description,
                                                          v_set*1000,
                                                          self.new_wavelength,
                                                          time_tuple[0],
                                                          time_tuple[1],
                                                          time_tuple[2],
                                                          time_tuple[3],
                                                          time_tuple[4],
                                                          time_tuple[5])

                    data_file = os.path.join(save_directory, filename)

                    with open(data_file, 'w+') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(measurement[0])
                        writer.writerow(measurement[1])

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)
        self.power_meter.set_wavelength(prev_wl)
        self.source_meter.set_voltage(prev_bias)
        if self.tf_with_laser:
            self.tunable_filter.set_wavelength(prev_wl)

        if not laser_active:
            self.light_source.turn_off()

        print('BW vs V acquisition finished')

    def perform_tx_measurement(self, save_data=True, plot=False):
        """
        Performs a wavelength sweep with the power and bias already set,
        and generates a csv file in the file specified in the GUI.
        :return: The matrix with the measurement data
        """

        # We act differently depending on the sweep type (NI DAQ or Using the Laser mainframe itself)
        if self.sweep_daq_acq:
            meas = self.perform_tx_measurement_daq(save_data, plot)
        else:
            # See if we use the HP lightwave or the MPM200
            if self.using_MPM200:
                meas = self.perform_tx_measurement_MPM200(save_data, plot)
            else:
                meas = self.perform_tx_measurement_mainframe(save_data, plot)

        return meas

    def perform_tx_measurement_MPM200(self, save_data = True, plot = True):
        """
        Performs a wavelength sweep using the MPM200 to interrogate the power
        :param save_data:
        :param plot:
        :return:
        """

        [prev_wl, prev_power, laser_active, spam] = self.get_state()

        init_wav = self.parent.start_meas_wl
        end_wav = self.parent.stop_meas_wl
        num_wav = self.parent.num_meas_wl + 1

        if (end_wav-init_wav) > 20:
            wav_speed = 15
        #elif (end_wav-init_wav)/num_wav < 0.005:
        #    wav_speed = 0.5
        else:
            wav_speed = 1
        #wav_speed = np.min([15, np.max([num_wav*0.1e-3, (end_wav-init_wav)/15])])  # speed in nm/s

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        self.light_source.set_wavelength(init_wav)

        # Configure laser for sweep (mode and trigger)
        self.light_source.cfg_out_trig(2)  # Trigger signal when sweep starts
        self.light_source.cfg_cont_sweep(init_wav, end_wav, wav_speed)

        # Configure power meter for sweep
        self.power_meter.cfg_cont_sweep(init_wav, end_wav, wav_speed, num_wav)

        # Start the measurement
        self.power_meter.start_meas()
        self.light_source.start_sweep()

        # Wait until measurement is done
        self.power_meter.wait_meas(print_status=False)
        self.power_meter.stop_meas()

        # Obtain the logged data
        rec_powers = self.power_meter.get_logged_data(port=MPM200_REC_PORT)

        # In the continuous sweep it is necessary to calibrate the power data
        po = self.power_meter.get_power_offsets(port=MPM200_REC_PORT,
                                                wavelengths=np.linspace(init_wav, end_wav, num_wav), wave_ref=init_wav)
        rec_cal_powers = list(map(lambda x, y: x + y, rec_powers, po))

        if MPM200_TAP_PORT is not None:
            ref_powers = self.power_meter.get_logged_data(port=MPM200_TAP_PORT)
            po = self.power_meter.get_power_offsets(port=MPM200_REC_PORT,
                                                    wavelengths=np.linspace(init_wav, end_wav, num_wav),
                                                    wave_ref=init_wav)
            ref_cal_powers = list(map(lambda x, y: x + y, ref_powers, po))
        else:
            ref_cal_powers = None

        # Now we have the data. Save it.

        # Matrix to save the data
        measurements = np.zeros((self.parent.num_meas_wl + 1, 7), float)

        wavs = np.linspace(init_wav, end_wav, num_wav)

        for i in range(len(wavs)):

            through_cal_factor = self.get_calibration_factor(wavs[i])

            rec_power = np.power(10, rec_cal_powers[i]/10)*1e-3
            tap_power = 0
            if MPM200_TAP_PORT is not None:
                tap_power = np.power(10, ref_cal_powers[i]/10)*1e-3

                through_loss = 10 * np.log10((rec_power + 1.0e-15) /
                                             (tap_power / through_cal_factor + 1.0e-15))
                measured_input_power = tap_power / through_cal_factor + 1.0e-15
            else:
                through_loss = 0
                measured_input_power = 0

            measurements[i, 0] = 1550.0  # We don't measure the wavelength
            measurements[i, 1] = through_loss
            measurements[i, 2] = measured_input_power
            measurements[i, 3] = wavs[i]
            measurements[i, 4] = rec_power
            measurements[i, 5] = tap_power
            measurements[i, 6] = 0  # We don't measure the current

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "scattering-%s-%d-%d-%d--%d#%d#%d_%d#%d#%d.mat" % (meas_description,
                                                                          self.parent.start_meas_wl,
                                                                          self.parent.num_meas_wl,
                                                                          self.parent.stop_meas_wl,
                                                                          time_tuple[0],
                                                                          time_tuple[1],
                                                                          time_tuple[2],
                                                                          time_tuple[3],
                                                                          time_tuple[4],
                                                                          time_tuple[5])

            out_file_path = os.path.join(save_directory, filename)
            print("Saving data to ", out_file_path)
            io.savemat(out_file_path, {'scattering': measurements})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)

        if not laser_active:
            self.light_source.turn_off()

        # Plot the data
        if plot:
            # plt.ion()
            if MPM200_TAP_PORT is not None:
                plt.plot(measurements[:, 3], measurements[:, 1])
            else:
                plt.plot(measurements[:, 3], measurements[:, 4])
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

        return measurements

    def perform_tx_measurement_daq(self, save_data=True, plot=True):
        """
        Performs a wavelength sweep using the NI DAQ to interrogate the received power
        :param save_data:
        :param plot:
        :return:
        """

        [prev_wl, prev_power, laser_active, spam] = self.get_state()

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        self.light_source.configure_sweep(self.parent.start_meas_wl, self.parent.stop_meas_wl,
                                          self.parent.num_meas_wl)  # Configure the laser wavelength sweep

        self.power_meter.set_range(REC_CHANNEL, self.power_range)
        self.power_meter.set_range(TAP_CHANNEL, 0)  # 0 dBm power range will work for the tap channel

        self.ni_daq.configure_nsampl_acq([AIN_RECEIVED, AIN_TAP], PFI_CLK, self.parent.num_meas_wl+1)

        self.ni_daq.start_task()
        self.light_source.start_sweep()
        self.ni_daq.wait_task()
        daq_data = self.ni_daq.read_data(self.parent.num_meas_wl+1)
        print(daq_data[0])
        print(daq_data[1])
        # Matrix to save the data
        measurements = np.zeros((self.parent.num_meas_wl+1, 7), float)

        wavs = np.linspace(self.parent.start_meas_wl, self.parent.stop_meas_wl, self.parent.num_meas_wl+1)

        for i in range(len(wavs)):

            # Need to convert voltage to power, based on the range

            measured_received_power = daq_data[0][i]*np.power(10, (self.power_range/10))*1e-3  # power in W
            tap_power = daq_data[1][i]*np.power(10, (0/10))*1e-3

            through_cal_factor = self.get_calibration_factor(wavs[i])
            through_loss = 10 * np.log10((measured_received_power + 1.0e-15) /
                                         (tap_power / through_cal_factor + 1.0e-15))
            measured_input_power = tap_power / through_cal_factor + 1.0e-15

            measurements[i, 0] = 1550.0   # We don't measure the wavelength
            measurements[i, 1] = through_loss
            measurements[i, 2] = measured_input_power
            measurements[i, 3] = wavs[i]
            measurements[i, 4] = measured_received_power
            measurements[i, 5] = tap_power
            measurements[i, 6] = 0  # We don't measure the current

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "scattering-%s-%d-%d-%d--%d#%d#%d_%d#%d#%d.mat" % (meas_description,
                                                                          self.parent.start_meas_wl,
                                                                          self.parent.num_meas_wl,
                                                                          self.parent.stop_meas_wl,
                                                                          time_tuple[0],
                                                                          time_tuple[1],
                                                                          time_tuple[2],
                                                                          time_tuple[3],
                                                                          time_tuple[4],
                                                                          time_tuple[5])

            out_file_path = os.path.join(save_directory, filename)
            print("Saving data to ", out_file_path)
            io.savemat(out_file_path, {'scattering': measurements})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)

        if not laser_active:
            self.light_source.turn_off()

        # Set power meter ranges back to auto
        self.power_meter.set_range(REC_CHANNEL, -10)
        self.power_meter.set_range(TAP_CHANNEL, -10)
        self.power_meter.set_range(REC_CHANNEL, 'AUTO')
        self.power_meter.set_range(TAP_CHANNEL, 'AUTO')

        # Plot the data
        if plot:
            # plt.ion()
            plt.plot(measurements[:, 3], measurements[:, 1])
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

        return measurements

    def perform_tx_measurement_mainframe(self, save_data=True, plot=False):
        """
        Performs a wavelength sweep using the mainframe to interrogate the received power
        :param save_data:
        :param plot:
        :return:
        """

        # Initialize the matrix to save the data
        measurements = np.zeros((self.parent.num_meas_wl, 7), float)

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "scattering-%s-%d-%d-%d--%d#%d#%d_%d#%d#%d.mat" % (meas_description,
                                                                          self.parent.start_meas_wl,
                                                                          self.parent.num_meas_wl,
                                                                          self.parent.stop_meas_wl,
                                                                          time_tuple[0],
                                                                          time_tuple[1],
                                                                          time_tuple[2],
                                                                          time_tuple[3],
                                                                          time_tuple[4],
                                                                          time_tuple[5])

            out_file_path = os.path.join(save_directory, filename)
            print("Saving data to ", out_file_path)

        # Save current state so that we can get back to it after the measurement
        [prev_wl, prev_power, laser_active, spam] = self.get_state()

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        row = 0

        for self.new_wavelength in np.linspace(self.parent.start_meas_wl, self.parent.stop_meas_wl,
                                              self.parent.num_meas_wl):

            self.light_source.set_wavelength(self.new_wavelength)
            self.power_meter.set_wavelength(self.new_wavelength)
            time.sleep(0.4)

            through_loss, measured_input_power, measured_received_power, tap_power \
                = self.analyze_powers(calibration=True)
            meas_wavelength = self.wavelength_meter.get_wavelength()

            if self.store_current:
                current = self.source_meter.measure_current()
            else:
                current = 0

            measurements[row, 0] = meas_wavelength
            measurements[row, 1] = through_loss
            measurements[row, 2] = measured_input_power
            measurements[row, 3] = self.new_wavelength
            measurements[row, 4] = measured_received_power
            measurements[row, 5] = tap_power
            measurements[row, 6] = current

            print("Set Wavelength = %.3f nm" % self.new_wavelength)
            print("Meas Wavelength = %.5f nm" % meas_wavelength)
            print("Rec Power = %.3e mW" % measured_received_power)
            print("Transmission Loss = %.2f dB" % through_loss)
            sys.stdout.flush()

            row = row + 1

        if save_data:
            io.savemat(out_file_path, {'scattering': measurements})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)

        if not laser_active:
            self.light_source.turn_off()

        # Plot the data
        if plot:
            # plt.ion()
            plt.plot(measurements[:, 3], measurements[:, 1])
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

        return measurements

    def perform_tx_bias_measurement(self, save_data=True, plot=False):
        """
        Get transmission vs wavelength at the different bias voltages specified
        by the user.

        :param save_data: If we want to save the data in a csv file
        :return: None
        """

        # Save current state so that we can get back to it after the measurement
        [prev_wl, prev_power, laser_active, prev_bias] = self.get_state()

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        start_voltage = self.parent.start_meas_v
        end_voltage = self.parent.stop_meas_v
        num_voltage = self.parent.num_meas_v

        # if plot:
        #     # plt.ion()
        #     plt.show()

        for v_set in np.linspace(start_voltage, end_voltage, num_voltage):

            # We just have to set the voltage and do a TxMeasurement.
            self.source_meter.set_voltage(v_set)
            measurement = self.perform_tx_measurement(save_data=False, plot=False)

            if save_data:
                save_directory = os.path.dirname(self.user_file_path)
                meas_description = os.path.basename(self.user_file_path)
                time_tuple = time.localtime()
                filename = "TvsV-%s-%d%s-%dnm-%dnm-%dnm--%d#%d#%d--%d#%d#%d.mat" % (meas_description,
                                                                                    1000 * v_set,
                                                                                    "mV",
                                                                                    self.parent.start_meas_wl,
                                                                                    self.parent.num_meas_wl,
                                                                                    self.parent.stop_meas_wl,
                                                                                    time_tuple[0],
                                                                                    time_tuple[1],
                                                                                    time_tuple[2],
                                                                                    time_tuple[3],
                                                                                    time_tuple[4],
                                                                                    time_tuple[5])

                out_file_path = os.path.join(save_directory, filename)
                print("Saving data to ", out_file_path)
                io.savemat(out_file_path, {'scattering': measurement})

            if plot:
                plt.plot(measurement[:, 3], measurement[:, 1])

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)
        self.power_meter.set_wavelength(prev_wl)
        self.source_meter.set_voltage(prev_bias)

        if not laser_active:
            self.light_source.turn_off()

        if plot:
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

    def perform_tx_power_scan(self, save_data=True, plot=False):
        """
        Get transmission vs wavelength at the different optical powers specified
        by the user.

        :param save_data: If we want to save the data in a csv file
        :return: None
        """

        # Save current state so that we can get back to it after the measurement
        [prev_wl, prev_power, laser_active, prev_bias] = self.get_state()

        # Turn laser on if necessary
        if not laser_active:
            self.light_source.turn_on()

        start_power = self.parent.start_meas_power
        end_power = self.parent.stop_meas_power
        num_power = self.parent.num_meas_power

        # if plot:
        #     # plt.ion()
        #     plt.show()

        for power in np.linspace(start_power, end_power, num_power):

            # We just have to set the voltage and do a TxMeasurement.
            self.light_source.set_power(power)

            measurement = self.perform_tx_measurement(save_data=False, plot=False)

            if save_data:
                save_directory = os.path.dirname(self.user_file_path)
                meas_description = os.path.basename(self.user_file_path)
                time_tuple = time.localtime()
                filename = "TvsP-%s-%d%s-%dnm-%dnm-%dnm--%d#%d#%d--%d#%d#%d.mat" % (meas_description,
                                                                                    power,
                                                                                    "mW",
                                                                                    self.parent.start_meas_wl,
                                                                                    self.parent.num_meas_wl,
                                                                                    self.parent.stop_meas_wl,
                                                                                    time_tuple[0],
                                                                                    time_tuple[1],
                                                                                    time_tuple[2],
                                                                                    time_tuple[3],
                                                                                    time_tuple[4],
                                                                                    time_tuple[5])

                out_file_path = os.path.join(save_directory, filename)
                print("Saving data to ", out_file_path)
                io.savemat(out_file_path, {'scattering': measurement})

            if plot:
                plt.plot(measurement[:, 3], measurement[:, 1])

        # Return to previous state
        self.light_source.set_wavelength(prev_wl)
        self.power_meter.set_wavelength(prev_wl)
        self.light_source.set_power(prev_power)

        if not laser_active:
            self.light_source.turn_off()

        if plot:
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

    def perform_tx_time_measurement(self):
        pass

    def perform_iv_measurement(self, save_data=True, plot=False):
        """
        Performs an IV curve using the source meter
        :return: The IV data
        """

        start_bias = self.parent.start_meas_v
        stop_bias = self.parent.stop_meas_v
        num_bias = self.parent.num_meas_v

        # Save current state so that we can get back to it after the measurement
        [prev_wl, prev_power, laser_active, prev_bias] = self.get_state()

        iv_data = self.source_meter.take_IV(start_bias, stop_bias, num_bias)

        if save_data:
            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "iv--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (meas_description,
                                                                     start_bias,
                                                                     num_bias,
                                                                     stop_bias,
                                                                     time_tuple[0],
                                                                     time_tuple[1],
                                                                     time_tuple[2],
                                                                     time_tuple[3],
                                                                     time_tuple[4],
                                                                     time_tuple[5])

            out_file_path = os.path.join(save_directory, filename)
            print("Saving data to ", out_file_path)
            io.savemat(out_file_path, {'iv': iv_data})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.source_meter.set_voltage(prev_bias)

        if plot:
            # plt.ion()
            plt.plot(iv_data[:, 0], iv_data[:, 1])
            plt.show()
            # plt.draw()
            # plt.pause(0.001)

        return iv_data

    def perform_transistor_output_curve(self, save_data=True, plot=False):

        """
        Takes the output characteristics of a transistor. Forces a Vgs, measures Ids vs Vds.
        """

        start_gate_bias = self.parent.start_gate_v
        stop_gate_bias = self.parent.stop_gate_v
        num_gate_bias = self.parent.num_gate_v

        # Save current state so that we can get back to it after the measurement
        prev_bias = self.parent.pd_bias_2

        # Force a Vgs, take IV curve of the DS.
        for gate_v in np.linspace(start_gate_bias, stop_gate_bias, num_gate_bias):

            self.source_meter_2.set_voltage(gate_v)
            iv_data = self.perform_iv_measurement(save_data=False, plot=False)

            if save_data:

                save_directory = os.path.dirname(self.user_file_path)
                meas_description = os.path.basename(self.user_file_path)

                time_tuple = time.localtime()
                filename = "transistor_output--%s--Vgs=%.4eV--%d#%d#%d--%d#%d#%d.mat" % (meas_description,
                                                                                       gate_v,
                                                                                       time_tuple[0],
                                                                                       time_tuple[1],
                                                                                       time_tuple[2],
                                                                                       time_tuple[3],
                                                                                       time_tuple[4],
                                                                                       time_tuple[5])

                out_file_path = os.path.join(save_directory, filename)
                print("Saving data to ", out_file_path)
                io.savemat(out_file_path, {'iv': iv_data})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.source_meter_2.set_voltage(prev_bias)

    def perform_pv_mod_output_curve(self, save_data=True):

        """
        Takes the output characteristics of a pv modulator. Forces a current, forces a Vgs and
        measures Vds.
        """

        start_gate_bias = self.parent.start_gate_v
        stop_gate_bias = self.parent.stop_gate_v
        num_gate_bias = self.parent.num_gate_v

        prev_bias = self.parent.pd_bias_2
        measurements = np.zeros((num_gate_bias, 2), float)

        # First, force current
        self.source_meter.set_current(self.ds_current)

        # Force a Vgs, measure Vds.
        for i, gate_v in enumerate(np.linspace(start_gate_bias, stop_gate_bias, num_gate_bias)):
            self.source_meter_2.set_voltage(gate_v)
            vds = self.source_meter.measure_voltage()

            measurements[i, 0] = gate_v
            measurements[i, 1] = vds

        if save_data:

            save_directory = os.path.dirname(self.user_file_path)
            meas_description = os.path.basename(self.user_file_path)

            time_tuple = time.localtime()
            filename = "pv_mod_output--%s--Ids=%.4e-Vgs=%.4eV-%.4eV%dnum--%d#%d#%d--%d#%d#%d.mat" % (meas_description,
                                                                                               self.ds_current,
                                                                                               start_gate_bias,
                                                                                               stop_gate_bias,
                                                                                               num_gate_bias,
                                                                                               time_tuple[0],
                                                                                               time_tuple[1],
                                                                                               time_tuple[2],
                                                                                               time_tuple[3],
                                                                                               time_tuple[4],
                                                                                               time_tuple[5])

            out_file_path = os.path.join(save_directory, filename)
            print("Saving data to ", out_file_path)
            io.savemat(out_file_path, {'vgs_vds': measurements})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # Return to previous state
        self.source_meter.set_current(0)
        self.source_meter_2.set_voltage(prev_bias)

    def perform_rlv_measurement(self):
        pass

    def perform_rlp_measurement(self):
        pass

    def analyze_powers(self, calibration):
        """
        Gets the measured powers from the power meter and
        applies calibration if indicated
        :param calibration: Boolean indicating if calibration has to be applied
        :return: A list containing through_loss, measured_input_power, measured_received_power, tap_power
        """

        tap_power, measured_received_power = self.power_meter.get_powers()

        if calibration:

            through_cal_factor = self.get_calibration_factor(self.new_wavelength)
            through_loss = 10 * np.log10((measured_received_power + 1.0e-15) /
                                         (tap_power / through_cal_factor + 1.0e-15))

            measured_input_power = tap_power / through_cal_factor + 1.0e-15
        else:
            through_loss = 10 * np.log10((measured_received_power + 1.0e-15)
                                         / (tap_power + 1.0e-15))
            measured_input_power = tap_power + 1.0e-15

        return through_loss, measured_input_power, measured_received_power, tap_power

    def get_calibration_factor(self, wav):
        """
        Returns the calibration factor for the current wavelength based on the
        pickle calibration file. This calibration factor is the real splitting
        in the splitter used for the tap.

        :return: The calibration factor
        """

        if self.parent.cal_set == "NONE":
            return 1

        # Find the measured calibration wavelength that is closer to the
        # current wavelength and return this number.
        wave_delta = wav - self.start_cal_wav
        wave_index = int(
            round(wave_delta / (self.stop_cal_wav - self.start_cal_wav) * (self.num_cal_wavs - 1)))

        if wave_index > self.num_cal_wavs - 1:
            wave_index = self.num_cal_wavs - 1
        elif wave_index < 0:
            wave_index = 0
        # print(wave_index)
        # print(self.parent.optical_calibration)
        return self.parent.optical_calibration[wave_index]
