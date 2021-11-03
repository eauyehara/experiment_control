#----------------------------------------------------------------------------
# Name:         photonmover_frontend.py
# Purpose:      Graphical Frontend for data acquisition.
#
# Author:       Marc de Cea, based on Jason Orcutt's code
#
# Created:      27 June 2019
# Copyright:    (c) 2019 by Marc de Cea
# Licence:      MIT license
#----------------------------------------------------------------------------

# This is a completely rewritten version of photonomover.
# The main purpose is to allow for a much higher flexibility of instruments
# and tests. It is also written in python 3!

# Instead of just adding manually instruments, we will have the code that
# talks to each instrument in separate files. If a specific instrument can
# do a specific measurement (such as an IV curve), it will implement
# the specific interface with the method that allows for an IV curve to
# be taken.

# The GUI won't change much in principle, since doing GUIs sucks.

############################################################################
############################################################################
######                                                                ######
######                       Import Dependencies                      ######
######                                                                ######
############################################################################
############################################################################

import wx
import pickle
from new_GPIB_manager import *
import time
import numpy as np

############################################################################
############################################################################
######                                                                ######
######                          Parameters to specify                 ######
######                                                                ######
############################################################################
############################################################################

source_list = ['HP', 'Santec']  # List of the laser sources currently connected

default_data_folder = 'C:/Users/Marc'  # Base folder to store the data
path_loss_cal_file = 'cal_l-r_bypass_patchcord.pickle'  # Path to the pickle calibration file
persistent_pickle_file = 'persistent_parameter_data.pickle'

############################################################################
############################################################################
######                                                                ######
######              Controller Frame Class Definition                 ######
######                                                                ######
############################################################################
############################################################################


# Create a button class to handle the laser commands (helper function)
class LaserButton(wx.ToggleButton):

    def __init__(self, parent):

        wx.ToggleButton.__init__(self, parent, -1, 'Laser Power', size=(75, 20))
        self.parent = parent
        self.active = 0  # Start assuming laser is off
        self.SetBackgroundColour(wx.RED)
        self.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)

    def on_toggle(self, event):

        if self.active == 0:
            # If laser is off, turn it on
            self.parent.parent.parent.gpib_manager.turn_on_laser_f()
            self.active = 1
            self.SetBackgroundColour(wx.GREEN)
            self.parent.parent.sb.SetStatusText('Turning on the Source laser')
        else:
            # If laser is on, turn it off
            self.parent.parent.parent.gpib_manager.turn_off_laser_f()
            self.active = 0
            self.SetBackgroundColour(wx.RED)
            self.parent.parent.sb.SetStatusText('Turning off the Source laser')


# Create a new frame class, derived from the wxPython Frame.
class ControllerFrame(wx.Frame):

    def __init__(self, parent, id, title):

        # First, call the base class' __init__ method to create the frame
        wx.Frame.__init__(self, None, id, title)

        # Save our variables
        self.parent = parent
        self.id = id
        self.title = title

        # Bind the close event to the function on_exit
        # (This assures that even if you hit the x button the
        # device gets properly closed.)
        self.Bind(wx.EVT_CLOSE, self.on_exit)

        # Create a status bar to show some messages in the bottom of the GUI
        self.sb = self.CreateStatusBar()

        # Create the Menu. This is a private method.
        self.__create_menu__()

        # Initialize panel
        panel = wx.Panel(self, -1)

        # Add panel to frame
        panel.parent = self
        self.panel = panel

        sizer_list = self.__create_GUI_controls__()

        self.__create_top_level_sizers__(sizer_list)

        # Default: take wavelength sweeps with the NI DAQ
        self.daq_sweep.SetValue(True)

    def __create_menu__(self):
        # For each dropdown menu, the process is always the same: generate an element
        # and give it an ID number so that we can afterwards relate it to a function
        # that will be called when the element is clicked.

        # Set up a File Menu.
        file_menu_ids = [0, 1]
        file_menu_captions = ["&About", "E&xit"]
        file_menu_infos = [" Information about PhotonMover",
                           " Terminate PhotonMover"]
        file_menu_methods = [self.on_about, self.on_exit]
        file_menu = self.__create_dropdown__(file_menu_ids, file_menu_captions,
                                             file_menu_infos, file_menu_methods)

        # Set up a Defaults Menu
        defaults_menu_ids = [10, 11]
        defaults_menu_captions = ["&Save", "&Load"]
        defaults_menu_infos = [" Save Current Parameters as Defaults",
                               " Load Default Parameters"]
        defaults_menu_methods = [self.on_save, self.on_load]
        defaults_menu = self.__create_dropdown__(defaults_menu_ids, defaults_menu_captions,
                                                 defaults_menu_infos, defaults_menu_methods)

        # Set up an Experiments Menu
        exp_menu_ids = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]
        exp_menu_captions = ["Transmission",
                             "Transmission vs. bias",
                             "Transmission vs. power",
                             "I-V",
                             "Responsivity-Lambda-V",
                             "Transmission-Time",
                             "Responsivity-Lambda-P",
                             "Calibration",
                             "Retrieve Bandwidth measurement",
                             "Bandwidth vs bias vs wl measurement",
                             "Measure and get bandwidth data",
                             "Measure transistor output curve",
                             "Measure pv mod output curve"]
        exp_menu_infos = [" Measure transmission over preset wavelength set, constant bias",
                          " Measure transmission over preset wavelength set and bias, constant power",
                          " Perform wavelength sweeps at different power levels",
                          " IV curve at a specific power using the parameter analyzer with preset V steps",
                          " Measure responsivity over preset wavelength and bias set",
                          " Measure transmission over time",
                          " Measure responsivity over preset wavelength and power set",
                          " Routine to calibrate the setup's back to back transmission vs. wavelength",
                          " Acquires a bandwidth trace from the VNA",
                          " Gets bandwidth data at different bias voltages and wavelengths using the vNA",
                          " Triggers a VNA measurement and saves the data",
                          " Measure Ids vs Vds for varying Vgs",
                          " Meaure Vds vs Vgs for a fixed Ids"
                          ]
        exp_menu_methods = [self.on_tx, self.on_tx_vs_V, self.on_tx_vs_P, self.on_IV,
                            self.on_RLV, self.on_tx_vs_time, self.on_RLP, self.on_calibration,
                            self.on_BW, self.on_BW_vs_V, self.on_BW_trigger, self.on_trans_output_curve,
                            self.on_pv_mod_outp]
        experiments_menu = self.__create_dropdown__(exp_menu_ids, exp_menu_captions,
                                                    exp_menu_infos, exp_menu_methods)
        # Create the Menubar
        menu_bar = wx.MenuBar()
        menu_bar.Append(file_menu, "&File")
        menu_bar.Append(defaults_menu, "&Defaults")
        menu_bar.Append(experiments_menu, "&Experiments")
        self.SetMenuBar(menu_bar)

    def __create_dropdown__(self, id_list, caption_list, info_list, method_list):
        """
        Creates a dropdown with the elements specified in the parameters
        :param id_list: list of IDs for each menu element
        :param caption_list: list of captions for each menu element
        :param info_list:  list of description for each menu element
        :param method_list: list of methods to bind each menu element to
        :return: The menu handler
        """

        # Create the menu
        menu = wx.Menu()

        # Generate the elements and bind them to a method
        for i in range(len(id_list)):
            menu.Append(id_list[i], caption_list[i], info_list[i])
            wx.EVT_MENU(self, id_list[i], method_list[i])

        return menu

    def __create_GUI_controls__(self):
        """
        Creates the different GUI elements (buttons, texts...). It sucks because it is very manual.
        :return: A list with the sizers containing the different elements
        """
        
        # Create a font for headings
        # heading_font = wx.Font(15, wx.DEFAULT, wx.NORMAL, wx.BOLD)

        # self.optics_control_heading = wx.StaticText(self.panel, -1, 'Optics Status and Controls')
        # self.optics_control_heading.SetFont(heading_font)

        # Create the controls and bind them to the correct handling functions if necessary

        # I don't think we need this anymore
        #laser_source_label, self.laser_source_menu = \
        #    self.create_label_and_dropdown('Choose Laser Source:', 1000, source_list)
        #self.Bind(wx.EVT_COMBOBOX, self.on_laser_change, id=1000)

        laser_wl_label, self.laser_wl_param = \
            self.create_label_and_textbox('Set wl:', 1001, "%.2f" % self.parent.wavelength, (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_wavelength_change, id=1001)

        tf_wl_label, self.tf_wl_param = \
            self.create_label_and_textbox('Set tun. filter wl:', 1023, "%.2f" % self.parent.tf_wavelength, (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_tf_wavelength_change, id=1023)

        tf_w_laser_label, self.tf_w_laser = \
            self.create_label_and_checkbox('Tunable filter track laser?', 1024)
        self.Bind(wx.EVT_CHECKBOX, self.on_tf_w_laser_change, id=1024)

        sweep_ni_daq_label, self.daq_sweep = \
            self.create_label_and_checkbox('Take wavelength sweeps with DAQ?', 1025)
        self.Bind(wx.EVT_CHECKBOX, self.on_daq_acq_change, id=1025)

        store_current_label, self.store_current = \
            self.create_label_and_checkbox('Store the current when lam sweep? (applies only if not using DAQ)', 1026)
        self.Bind(wx.EVT_CHECKBOX, self.on_store_current_change, id=1026)

        pm_range_label, self.pm_range_param = \
            self.create_label_and_textbox('Power Meter Range:', 1027, "%.2f" % self.parent.pm_range, (80, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_range_change, id=1027)

        laser_power_label, self.laser_power_param = \
            self.create_label_and_textbox('Set Power:', 1002, "%.2f" % self.parent.power, (40, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_power_change, id=1002)

        meas_power_label, self.meas_power_param = \
            self.create_label_and_textbox('Meas. In Power:', 1003, "????", (80, 20))

        meas_wl_label, self.meas_wl_param = \
            self.create_label_and_textbox('Meas. wl:', 1004, "????", (70, 20))

        meas_rec_power_label, self.meas_rec_power_param = \
            self.create_label_and_textbox('Received Power:', 1005, "--.---", (80, 20))

        tap_power_label, self.tap_power_param = \
            self.create_label_and_textbox('Tap Power:', 1006, "--.---", (80, 20))

        through_loss_label, self.through_loss_param = \
            self.create_label_and_textbox('Loss:', 1007, "--.---", (60, 20))

        pc_channel_label, self.pc_channel_param = \
            self.create_label_and_textbox('SM Ch.:', 1008, "%d" % self.parent.smu_channel, (25, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_sm_channel_change, id=1008)

        pd_bias_voltage_label, self.pd_bias_voltage_param = \
            self.create_label_and_textbox('SM voltage (V):', 1009, "%d" % self.parent.pd_bias, (30, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_bias_change, id=1009)

        meas_photocurrent_label, self.meas_photocurrent_param = \
            self.create_label_and_textbox('SM current (A):', 1010, "????", (70, 20))

        gate_bias_voltage_label, self.gate_bias_voltage_param = \
            self.create_label_and_textbox('SM2 voltage (V):', 1031, "%d" % self.parent.pd_bias_2, (30, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_bias_2_change, id=1031)

        meas_gate_current_label, self.meas_gate_current_param = \
            self.create_label_and_textbox('SM2 current (A):', 1032, "????", (70, 20))

        el_attenuation_label, self.el_attenuation_param = \
            self.create_label_and_textbox('Electrical Att (dB):', 1022, "%d" % self.parent.el_att, (30, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_el_att_change, id=1022)



        responsivity_label, self.responsivity_param = \
            self.create_label_and_textbox('Calc. Resp:', 1011, "????", (50, 20))

        qe_label, self.qe_param = \
            self.create_label_and_textbox('Calc. QE:', 1012, "????", (50, 20))

        self.ID_START_MEAS_WAVELENGTH_PARAM = 1013
        start_wl_label, self.start_wl_param = \
            self.create_label_and_textbox('Start Lambda (nm):', self.ID_START_MEAS_WAVELENGTH_PARAM, str(self.parent.start_meas_wl), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_START_MEAS_WAVELENGTH_PARAM)

        self.ID_STOP_MEAS_WAVELENGTH_PARAM = 1014
        stop_wl_label, self.stop_wl_param = \
            self.create_label_and_textbox('Stop Lambda (nm):', self.ID_STOP_MEAS_WAVELENGTH_PARAM, str(self.parent.stop_meas_wl), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_STOP_MEAS_WAVELENGTH_PARAM)

        self.ID_NUM_MEAS_WAVELENGTH_PARAM = 1015
        num_wl_label, self.num_wl_param = \
            self.create_label_and_textbox('Num. Lambda (nm):', self.ID_NUM_MEAS_WAVELENGTH_PARAM, str(self.parent.num_meas_wl), (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_NUM_MEAS_WAVELENGTH_PARAM)

        self.ID_START_MEAS_POWER_PARAM = 1016
        start_power_label, self.start_power_param = \
            self.create_label_and_textbox('Start Power (mW):', self.ID_START_MEAS_POWER_PARAM, str(self.parent.start_meas_power), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_START_MEAS_POWER_PARAM)

        self.ID_STOP_MEAS_POWER_PARAM = 1017
        stop_power_label, self.stop_power_param = \
            self.create_label_and_textbox('Stop Power (mW):', self.ID_STOP_MEAS_POWER_PARAM, str(self.parent.stop_meas_power), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_STOP_MEAS_POWER_PARAM)

        self.ID_NUM_MEAS_POWER_PARAM = 1018
        num_power_label, self.num_power_param = \
            self.create_label_and_textbox('Num. Power (mW):', self.ID_NUM_MEAS_POWER_PARAM, str(self.parent.num_meas_power), (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_NUM_MEAS_POWER_PARAM)

        self.ID_START_MEAS_V_PARAM = 1019
        start_v_label, self.start_v_param = \
            self.create_label_and_textbox('Start Bias (V):', self.ID_START_MEAS_V_PARAM, str(self.parent.start_meas_v), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_START_MEAS_V_PARAM)

        self.ID_STOP_MEAS_V_PARAM = 1020
        stop_v_label, self.stop_v_param = \
            self.create_label_and_textbox('Stop Bias (V):', self.ID_STOP_MEAS_V_PARAM, str(self.parent.stop_meas_v), (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_STOP_MEAS_V_PARAM)

        self.ID_NUM_MEAS_V_PARAM = 1021
        num_v_label, self.num_v_param = \
            self.create_label_and_textbox('Num. Bias (V):', self.ID_NUM_MEAS_V_PARAM, str(self.parent.num_meas_v), (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_NUM_MEAS_V_PARAM)

        self.ID_START_GATE_V_PARAM = 1028
        start_gate_v_label, self.start_gate_v_param = \
            self.create_label_and_textbox('Start Gate Bias (V):', self.ID_START_GATE_V_PARAM, str(self.parent.start_gate_v),
                                          (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_START_GATE_V_PARAM)

        self.ID_STOP_GATE_V_PARAM = 1029
        stop_gate_v_label, self.stop_gate_v_param = \
            self.create_label_and_textbox('Stop Gate Bias (V):', self.ID_STOP_GATE_V_PARAM, str(self.parent.stop_gate_v),
                                          (100, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_STOP_GATE_V_PARAM)

        self.ID_NUM_GATE_V_PARAM = 1030
        num_gate_v_label, self.num_gate_v_param = \
            self.create_label_and_textbox('Num. Gate Bias (V):', self.ID_NUM_GATE_V_PARAM, str(self.parent.num_gate_v),
                                          (60, 20))
        self.Bind(wx.EVT_TEXT_ENTER, self.on_measurement_param_change, id=self.ID_NUM_GATE_V_PARAM)

        # Add connections for updating info every time power is measured
        self.through_loss_param.Connect(-1, -1, EVT_MEASURED_POWERS, self.on_measured_powers)
        self.through_loss_param.Connect(-1, -1, EVT_DONE, self.on_done)

        # Laser button to turn it on and off
        laser_power_button = LaserButton(self.panel)

        # Now, let's create sizers grouping the different elements
        # Create and populate optics control sizer
        sizer_list = list()

        # Sweep type control
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [sweep_ni_daq_label, self.daq_sweep],
                                            [3, 8]))

        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [store_current_label, self.store_current],
                                            [3, 8]))

        # Laser source control sizer
        #sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                    [laser_source_label, self.laser_source_menu,
        #                                     laser_power_button],
        #                                    [3, 8]))
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [laser_power_button, pm_range_label, self.pm_range_param],
                                            [3, 3, 10]))

        # Laser wavelength sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [laser_wl_label, self.laser_wl_param, meas_wl_label,
                                             self.meas_wl_param],
                                            [3, 8, 3]))

        # Tunable filter wavelength sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [tf_wl_label, self.tf_wl_param, tf_w_laser_label, self.tf_w_laser],
                                            [3, 8, 3]))

        # Laser power sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [laser_power_label, self.laser_power_param,
                                             meas_power_label, self.meas_power_param],
                                            [3, 8, 3]))

        # Received power sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [meas_rec_power_label, self.meas_rec_power_param],
                                            [3]))

        # Measured tap power sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [tap_power_label, self.tap_power_param],
                                            [3]))

        # Transmission sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [through_loss_label, self.through_loss_param],
                                            [3]))

        # SM sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [pc_channel_label, self.pc_channel_param,
                                             pd_bias_voltage_label, self.pd_bias_voltage_param,
                                             meas_photocurrent_label, self.meas_photocurrent_param],
                                            [3, 8, 3, 8, 3]))

        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [gate_bias_voltage_label, self.gate_bias_voltage_param,
                                             meas_gate_current_label, self.meas_gate_current_param],
                                            [3, 8, 3]))

        # Attenuator
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [el_attenuation_label, self.el_attenuation_param],
                                            [3]))

        # Responsivity and QE sizer
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [responsivity_label, self.responsivity_param,
                                             qe_label, self.qe_param,],
                                            [3, 8, 3]))

        # Wavelength sweep sizers
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [start_wl_label, self.start_wl_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [stop_wl_label, self.stop_wl_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [num_wl_label, self.num_wl_param],
        #                                     [3]))
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [start_wl_label, self.start_wl_param, stop_wl_label, self.stop_wl_param,
                                             num_wl_label, self.num_wl_param],
                                            [3, 5, 3, 5, 3]))
        
        # Power sweep sizers
        #sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                    [start_power_label, self.start_power_param],
        #                                    [3]))
        #sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                    [stop_power_label, self.stop_power_param],
        #                                    [3]))
        #sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                    [num_power_label, self.num_power_param],
        #                                    [3]))
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [start_power_label, self.start_power_param, stop_power_label,
                                             self.stop_power_param, num_power_label, self.num_power_param],
                                            [3, 5, 3, 5, 3]))

        # Voltage sweep sizers
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [start_v_label, self.start_v_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [stop_v_label, self.stop_v_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [num_v_label, self.num_v_param],
        #                                     [3]))
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [start_v_label, self.start_v_param, stop_v_label, self.stop_v_param,
                                             num_v_label, self.num_v_param],
                                            [3, 5, 3, 5, 3]))

        # Gate Voltage sweep sizers
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [start_gate_v_label, self.start_gate_v_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [stop_gate_v_label, self.stop_gate_v_param],
        #                                     [3]))
        # sizer_list.append(self.create_sizer(wx.HORIZONTAL,
        #                                     [num_gate_v_label, self.num_gate_v_param],
        #                                     [3]))
        sizer_list.append(self.create_sizer(wx.HORIZONTAL,
                                            [start_gate_v_label, self.start_gate_v_param, stop_gate_v_label,
                                             self.stop_gate_v_param, num_gate_v_label, self.num_gate_v_param],
                                            [3, 5, 2, 5, 3]))

        return sizer_list

    def __create_top_level_sizers__(self, sizer_list):
        """
        Creates the top level sizer integrating all the subsizers with the different controls.
        :param sizer_list: List of lower level sizers to be integrated
        :return: None
        """

        top_level_sizer = wx.BoxSizer(wx.VERTICAL)
        #top_level_sizer.Add(self.optics_control_heading, 0, wx.BOTTOM, 10)

        for sizer in sizer_list:
            top_level_sizer.Add(sizer, 0, wx.ALIGN_LEFT | wx.BOTTOM, 20)

        # Create the outer box and fit it all
        border = wx.BoxSizer()
        border.Add(top_level_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.panel.SetSizerAndFit(border)
        self.Fit()

    def create_label_and_dropdown(self, label, id, dropdown_list):
        """
        Creates a pair of static label and dropdown with the specified parameters
        :param label: Label of the static text box
        :param id: id taht will be later used to bind a function
        :param dropdown_list: list with the different options that will appear in the dropdown
        :return: two elements, the first one is the static text, and the second is the dropdown
        """

        label = wx.StaticText(self.panel, -1, label)

        dropdown = wx.ComboBox(self.panel, id, value=dropdown_list[0],
                               choices=dropdown_list, style=wx.CB_READONLY)

        return label, dropdown

    def create_label_and_checkbox(self, label, id):
        """
        Creates a pair of static label and checkbox with the specified parameters
        :param label: Label of the static text box
        :param id: id taht will be later used to bind a function
        :return: two elements, the first one is the static text, and the second is the checkbox
        """

        label = wx.StaticText(self.panel, -1, label)

        checkbox = wx.CheckBox(self.panel, id)

        return label, checkbox

    def create_label_and_textbox(self, label, id, textbox_content, size):
        """
        Creates a pair of static label and text box taht you can write to
        :param label: Label of the static text box
        :param id: id that will be later used to bind a function
        :param size: size of the text box
        :param textbox_content: initial caption of the textbox
        :return: two elements, the first one is the static text, and the second is the textbox
        """

        label = wx.StaticText(self.panel, -1, label)

        text_box = wx.TextCtrl(self.panel, id, textbox_content, size=size,
                               style=wx.TE_PROCESS_ENTER)

        return label, text_box

    def create_sizer(self, sizer_direction, element_list, spacer_list):
        """
        Creates sizers containing the specified elements
        :param sizer_direction: Direction of the sizer, either wx.HORIZONTAL or wx.VERTICAL
        :param element_list: list containing the elements to be put in each sizer
        :param spacer_list: list of the spacer dimensions (x,y) to be put between each element
        :return: the sizer
        """

        sizer = wx.BoxSizer(sizer_direction)
        for ind in range(len(element_list)):
            sizer.Add(element_list[ind])
            if len(spacer_list) > ind:
                sizer.AddSpacer(spacer_list[ind])

        return sizer

    ############################################################################
    ############################################################################
    ######                                                                ######
    ######       Here starts the definition of the bidnings               ######
    ######                                                                ######
    ############################################################################
    ############################################################################

    # Binding for wavelength parameter change
    def on_wavelength_change(self, event):
        self.parent.wavelength = float(self.laser_wl_param.GetValue())
        if self.parent.gpib_manager.tf_with_laser:
            #  Change the tunable filter wavelength in the textbox
            self.tf_wl_param.SetValue(self.laser_wl_param.GetValue())
        self.parent.gpib_manager.set_wavelength(self.parent.wavelength)
        self.sb.SetStatusText('Adjusting the Laser Wavelength to %.2f' % self.parent.wavelength)

    # Binding for tunable filter wavelength parameter change
    def on_tf_wavelength_change(self, event):
        self.parent.tf_wavelength = float(self.tf_wl_param.GetValue())
        self.parent.gpib_manager.set_tf_wavelength(self.parent.tf_wavelength)
        self.sb.SetStatusText('Adjusting the Tun Filter Wavelength to %.2f' % self.parent.wavelength)

    # Binding for the tunable filter wavelength tracking the laser
    def on_tf_w_laser_change(self, event):

        self.parent.gpib_manager.set_tf_w_laser(self.tf_w_laser.IsChecked())
        if self.tf_w_laser.IsChecked():
            self.sb.SetStatusText('Tun Filter will track laser wl')
        else:
            self.sb.SetStatusText('Tun Filter will not track laser wl')

    # Binding for the checkbox indicating the use of the NI DAQ to take wavelength sweeps
    def on_daq_acq_change(self, event):
        self.parent.gpib_manager.set_DAQ_acq(self.daq_sweep.IsChecked())
        if self.daq_sweep.IsChecked():
            self.sb.SetStatusText('Wav sweeps will be taken wit the NI DAQ')
        else:
            self.sb.SetStatusText('Wav sweeps wii be taken using the HP Lightwave')

    # Binding for the checkbox indicating the use of the NI DAQ to take wavelength sweeps
    def on_store_current_change(self, event):
        self.parent.gpib_manager.set_store_current(self.store_current.IsChecked())
        if self.store_current.IsChecked():
            self.sb.SetStatusText('Current will be recorded when sweeping with HP Lightwave')
        else:
            self.sb.SetStatusText('Current will not be recorded when sweeping with HP Lightwave')

    # Binding for power meter range change
    def on_range_change(self, event):
        self.parent.pm_range = float(self.pm_range_param.GetValue())
        self.parent.gpib_manager.set_pm_range(self.parent.pm_range)
        self.sb.SetStatusText('Adjusting the Power Meter Range to %.2f' % self.parent.pm_range)

    # Binding for power parameter change
    def on_power_change(self, event):
        self.parent.power = float(self.laser_power_param.GetValue())
        self.parent.gpib_manager.set_power(self.parent.power)
        self.sb.SetStatusText('Adjusting the Laser Power to %.2f' % self.parent.power)

    # Binding for laser source change
    # def on_laser_change(self, event):
    #    self.parent.laser_source = self.laser_source_menu.GetValue()

    # Binding for parameter analyzer photocurrent channel change
    def on_sm_channel_change(self, event):
        self.parent.sm_channel = int(self.pc_channel_param.GetValue())
        self.parent.gpib_manager.set_bias_f()

    # Binding for parameter analyzer bias voltage change
    def on_bias_change(self, event):
        try:
            self.parent.pd_bias = float(self.pd_bias_voltage_param.GetValue())
        except:
            self.parent.pd_bias = 0.0
        self.parent.gpib_manager.set_bias_f()

    # Binding for parameter analyzer bias voltage change
    def on_bias_2_change(self, event):
        try:
            self.parent.pd_bias_2 = float(self.gate_bias_voltage_param.GetValue())
        except:
            self.parent.pd_bias_2 = 0.0
        self.parent.gpib_manager.set_bias_2_f()

    # Binding for electrical attenuation change
    def on_el_att_change(self, event):
        try:
            self.parent.el_att = float(self.el_attenuation_param.GetValue())
        except:
            self.parent.el_att = 0.0
        self.parent.gpib_manager.set_electrical_att()

    # Binding for measurement parameter change
    def on_measurement_param_change(self, event):
        if event.GetId() == self.ID_START_MEAS_WAVELENGTH_PARAM:
            self.parent.start_meas_wl = float(self.start_wl_param.GetValue())
            self.sb.SetStatusText('Setting the Start Wavelength for Transmission Scan')
        elif event.GetId() == self.ID_STOP_MEAS_WAVELENGTH_PARAM:
            self.parent.stop_meas_wl = float(self.stop_wl_param.GetValue())
            self.sb.SetStatusText('Setting the Stop Wavelength for Transmission Scan')
        elif event.GetId() == self.ID_NUM_MEAS_WAVELENGTH_PARAM:
            self.parent.num_meas_wl = int(self.num_wl_param.GetValue())
            self.sb.SetStatusText('Setting Number of Wavelengths for Transmission Scan')

        elif event.GetId() == self.ID_START_MEAS_POWER_PARAM:
            self.parent.start_meas_power = float(self.start_power_param.GetValue())
            self.sb.SetStatusText('Setting the Start Power for Transmission Scan')
        elif event.GetId() == self.ID_STOP_MEAS_POWER_PARAM:
            self.parent.stop_meas_power = float(self.stop_power_param.GetValue())
            self.sb.SetStatusText('Setting the Stop Power for Transmission Scan')
        elif event.GetId() == self.ID_NUM_MEAS_POWER_PARAM:
            self.parent.num_meas_power = int(self.num_power_param.GetValue())
            self.sb.SetStatusText('Setting Number of Powers for Transmission Scan')

        elif event.GetId() == self.ID_START_MEAS_V_PARAM:
            self.parent.start_meas_v = float(self.start_v_param.GetValue())
            self.sb.SetStatusText('Setting the Start V for Transmission Scan')
        elif event.GetId() == self.ID_STOP_MEAS_V_PARAM:
            self.parent.stop_meas_v = float(self.stop_v_param.GetValue())
            self.sb.SetStatusText('Setting the Stop V for Transmission Scan')
        elif event.GetId() == self.ID_NUM_MEAS_V_PARAM:
            self.parent.num_meas_v = int(self.num_v_param.GetValue())
            self.sb.SetStatusText('Setting Number of V for Transmission Scan')
        elif event.GetId() == self.ID_NUM_GATE_V_PARAM:
            self.parent.num_gate_v = int(self.num_gate_v_param.GetValue())
            self.sb.SetStatusText('Setting Number of gate V for Transmission Scan')
        elif event.GetId() == self.ID_STOP_GATE_V_PARAM:
            self.parent.stop_gate_v = float(self.stop_gate_v_param.GetValue())
            self.sb.SetStatusText('Setting the stop gate V for Transmission Scan')
        elif event.GetId() == self.ID_START_GATE_V_PARAM:
            self.parent.start_gate_v = float(self.start_gate_v_param.GetValue())
            self.sb.SetStatusText('Setting the start gate V for Transmission Scan')

        else:
            print('ERROR: Uncaught ID in on_measurement_param_change')

    def on_about(self, e):
        d = wx.MessageDialog(self, " A GUI front-end for the PhotonMover test setup \n"
                                   " to enable optical testing of our photonic and electronic devices \n"
                                   "\n By Marc de Cea, 2019", "About PhotonMover", wx.OK)
        d.ShowModal()
        d.Destroy()

    def on_save(self, e):
        pickle_file_object = open(self.parent.pickle_file, 'w')
        pickle.dump(self.parent.data, pickle_file_object)
        pickle_file_object.close()

    def on_load(self, e):
        self.parent.Load_default_data()

    def on_exit(self, e):
        self.parent.done = 1
        if self.parent.gpib_manager.running == 0:
            self.Destroy()
        else:
            self.parent.gpib_manager.close()

    def on_tx(self, e):

        power_range = None

        # We ask different things depending on the acquisition method
        if self.parent.gpib_manager.sweep_daq_acq:

            power_options = [-70.0, -60.0, -50.0, -40.0, -30.0, -20.0, -10.0, 0.0, 10.0]

            current_power = float(self.meas_rec_power_param.GetValue())
            current_power_dBm = 10*np.log10(current_power*1e3)
            mes = 'Choose the power range for the power meter measuring the tx. The current power is %.4f uW (%.4f dBm)' \
                  % (current_power*1e6, current_power_dBm)

            dialog1 = wx.MultiChoiceDialog(None, message= mes,
                                           caption='Range for power meter',
                                           choices=['-70 dBm', '-60dBm', '-50dBm', '-40dBm', '-30dBm', '-20dBm',
                                                    '-10dBm', '0 dBm', '10 dBm'])
            dialog1.ShowModal()
            index = dialog1.GetSelections()
            power_range = power_options[index[0]]

        dialog2 = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                                defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog2.ShowModal() == wx.ID_OK:
            print('Starting Transmission vs Wavelength Measurement Routine')
            self.parent.gpib_manager.tx_scan_f(dialog2.GetPath(), power_range)
        else:
            print('Nothing was selected.')

        dialog2.Destroy()

    def on_tx_vs_time(self, e):

        power_range = None

        # We ask different things depending on the acquisition method
        if self.parent.gpib_manager.sweep_daq_acq:
            power_options = [-70, -60, -50, -40, -30, -20, -10, 0, 10]

            current_power = float(self.meas_rec_power_param.GetValue())
            current_power_dBm = 10 * np.log10(current_power * 1e3)
            mes = 'Choose the power range for the power meter measuring the tx. The current power is %.4f uW (%.4f dBm)' \
                  % (current_power * 1e3, current_power_dBm)

            dialog1 = wx.MultiChoiceDialog(None, message=mes,
                                           caption='Range for power meter', n=9,
                                           choices=['-70 dBm', '-60dBm', '-50dBm', '-40dBm', '-30dBm', '-20dBm',
                                                    '-10dBm', '0 dBm', '10 dBm'])
            dialog1.ShowModal()
            index = dialog1.GetSelections()
            power_range = power_options[index[0]]

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting Transmission vs Time Routine')
            self.parent.gpib_manager.tx_time_scan_f(dialog.GetPath(), power_range)
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_tx_vs_V(self, e):

        power_range = None

        # We ask different things depending on the acquisition method
        if self.parent.gpib_manager.sweep_daq_acq:
            power_options = [-70, -60, -50, -40, -30, -20, -10, 0, 10]

            current_power = float(self.meas_rec_power_param.GetValue())
            current_power_dBm = 10 * np.log10(current_power * 1e3)
            mes = 'Choose the power range for the power meter measuring the tx. The current power is %.4f uW (%.4f dBm)' \
                  % (current_power * 1e3, current_power_dBm)

            dialog1 = wx.MultiChoiceDialog(None, message=mes,
                                           caption='Range for power meter', n=9,
                                           choices=['-70 dBm', '-60dBm', '-50dBm', '-40dBm', '-30dBm', '-20dBm',
                                                    '-10dBm', '0 dBm', '10 dBm'])
            dialog1.ShowModal()
            index = dialog1.GetSelections()
            power_range = power_options[index[0]]

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting Transmission vs Wavelength vs Voltage Routine')
            self.parent.gpib_manager.tx_bias_scan_f(dialog.GetPath(), power_range)
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_tx_vs_P(self, e):

        power_range = None

        # We ask different things depending on the acquisition method
        if self.parent.gpib_manager.sweep_daq_acq:
            power_options = [-70, -60, -50, -40, -30, -20, -10, 0, 10]

            current_power = float(self.meas_rec_power_param.GetValue())
            current_power_dBm = 10 * np.log10(current_power * 1e3)
            mes = 'Choose the power range for the power meter measuring the tx. The current power is %.4f uW (%.4f dBm)' \
                  % (current_power * 1e3, current_power_dBm)

            dialog1 = wx.MultiChoiceDialog(None, message=mes,
                                           caption='Range for power meter', n=9,
                                           choices=['-70 dBm', '-60dBm', '-50dBm', '-40dBm', '-30dBm', '-20dBm',
                                                    '-10dBm', '0 dBm', '10 dBm'])
            dialog1.ShowModal()
            index = dialog1.GetSelections()
            power_range = power_options[index[0]]

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting Transmission vs Wavelength vs Power Routine')
            self.parent.gpib_manager.tx_power_scan_f(dialog.GetPath(), power_range)
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_pv_mod_outp(self, e):

        # Ask for the desired current
        mes = 'Choose the desired drain-source current (in uA)'

        dialog1 = wx.TextEntryDialog(None, message=mes,
                                       caption='Ids (uA)', value='1')
        dialog1.ShowModal()
        ds_current = float(dialog1.GetValue())*1e-6

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting PV mod output characteristics for the specified current')
            self.parent.gpib_manager.meas_pv_mod_outp(ds_current, dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_BW(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting acquisition from VNA')
            self.parent.gpib_manager.get_VNA_trace(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_BW_trigger(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting acquisition from VNA')
            self.parent.gpib_manager.trigger_VNA_trace(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_trans_output_curve(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting output curve acquisition')
            self.parent.gpib_manager.take_output_curve(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_BW_vs_V(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting bandwidth vs Wavelength vs Voltage Routine')
            self.parent.gpib_manager.VNA_bias_wl_scan(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_IV(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)
        if dialog.ShowModal() == wx.ID_OK:
            print('Starting IV Measurement Routine')
            self.parent.gpib_manager.take_IV_f(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_RLV(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting RLV Measurement Routine')
            self.parent.gpib_manager.take_RLV_f(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_RLP(self, e):

        dialog = wx.FileDialog(None, message='Enter only the measurement reference in the correct directory',
                               defaultDir=self.parent.data_folder, style=wx.FD_SAVE)

        if dialog.ShowModal() == wx.ID_OK:
            print('Starting RLP Measurement Routine')
            self.parent.gpib_manager.take_RLP_f(dialog.GetPath())
        else:
            print('Nothing was selected.')

        dialog.Destroy()

    def on_calibration(self, e):

        choices = ['Optical path calibration', 'No calibration']

        dialog = wx.SingleChoiceDialog(None, 'Ensure fibers are connected correctly (no DUT)!',
                                       'Photonmover Calibrations',
                                       choices)

        # The user pressed the "OK" button in the dialog
        if dialog.ShowModal() == wx.ID_OK:

            choice_result = dialog.GetSelection()
            if choice_result == 0:
                print('Starting Calibration Routine')
                self.parent.gpib_manager.calibration_f()
            elif choice_result == 1:
                print('Starting No Calibration Routine')
                self.parent.gpib_manager.no_calibration_f()

        # The user exited the dialog without pressing the "OK" button
        else:

            print('You did not select anything. No calibration will be performed')

        dialog.Destroy()

    def on_done(self, event):
        # When a subthread finishes, it creates a done event. If the
        # program is ready to be closed, the program will quit.
        if self.parent.done == 1 and self.parent.gpib_manager.done == 1:
            self.Destroy()

    def on_measured_powers(self, event):
        # What to do when the optics update readings have changed
        self.through_loss_param.SetValue("%.3f" % event.through_loss)
        self.meas_power_param.SetValue("%.3e" % event.input_power)
        self.meas_wl_param.SetValue("%.5f" % event.wavelength)
        self.meas_rec_power_param.SetValue("%.3e" % event.rec_power)
        self.tap_power_param.SetValue("%.3e" % event.tap_power)
        self.meas_photocurrent_param.SetValue("%.3e" % event.photocurrent)
        self.meas_gate_current_param.SetValue("%.3e" % event.photocurrent_2)
        self.responsivity_param.SetValue("%.3f" % event.responsivity)
        self.qe_param.SetValue("%d%%" % event.qe)


############################################################################
############################################################################
######                                                                ######
######            Controller Application Class Definition             ######
######                                                                ######
############################################################################
############################################################################


# Every wxWidgets application must have a class derived from wx.App
class ControllerApp(wx.App):

    # wxWindows calls this method to initialize the application
    def OnInit(self):

        # Initialize to generic wavelength
        self.wavelength = 1550.00  # nm
        self.tf_wavelength = 1550.00 # nm

        # Initialize to generic power
        self.power = 1.00  # dBm

        # Power meter range to AUTO.
        self.pm_range = PM_AUTO_RANGE

        # Laser Source
        self.laser_source = source_list[0]

        # Responsivity Channel
        self.smu_channel = 1

        # Photodiode Bias Voltage
        self.pd_bias = 0.0

        # GS voltage for transistor
        self.pd_bias_2 = 0.0

        # Electrical attenuation
        self.el_att = 0.0  # dB

        # Calibration parameters default to having the optical path loss calibrated
        self.cal_set = "PATH_CALIBRATION"

        # Measurement Parameters
        self.data_folder = default_data_folder
        self.start_meas_wl = 1520.0
        self.stop_meas_wl = 1580.0
        self.num_meas_wl = 120

        self.start_meas_power = -10
        self.stop_meas_power = 0
        self.num_meas_power = 5

        self.start_meas_v = 0
        self.stop_meas_v = -3
        self.num_meas_v = 5

        self.start_gate_v = 0
        self.stop_gate_v = 1
        self.num_gate_v = 5

        # Program state indicator
        self.done = 0

        # Persistent calibration pickle
        self.optical_calibration = list()
        self.optical_calibration_file = path_loss_cal_file

        # Create an instance of our customized Frame class
        self.app_frame = ControllerFrame(self, -1, "PhotonMover Fiber Control Front-End")

        # Create an instance of the GPIB Manager Class
        self.gpib_manager = GPIBManager(self, self.app_frame.through_loss_param)

        # Show the application
        self.app_frame.Show(True)

        # Tell wxWindows that this is our main window
        self.SetTopWindow(self.app_frame)

        # Initialize our variables
        self.load_calibration()

        # Spawn the main loop to manage gpib connections and begin polling power sensors.
        self.gpib_manager.start()
        time.sleep(0.001)

        # Set the wavelength to the default wavelength
        self.gpib_manager.set_wavelength(self.wavelength)
        self.gpib_manager.set_tf_wavelength(self.tf_wavelength)

        # Return a success flag
        return True

    def load_default_data(self):
        # Load data from the pickle files
        pickle_file_object = open(self.optical_calibration_file, 'r')
        self.data = pickle.load(pickle_file_object)
        pickle_file_object.close()

        self.load_calibration()

    def load_calibration(self):

        if self.cal_set == "PATH_CALIBRATION":
            pickle_file_object = open(self.optical_calibration_file, 'rb')
            self.optical_calibration = pickle.load(pickle_file_object)
            pickle_file_object.close()

        elif self.cal_set == "NONE":
            self.optical_calibration = None


############################################################################
############################################################################
######                                                                ######
######                Code to run when main application               ######
######                                                                ######
############################################################################
############################################################################

if __name__ == "__main__":
    app = ControllerApp()  # Create an instance of the application class
    app.MainLoop()  # Tell it to start processing events
