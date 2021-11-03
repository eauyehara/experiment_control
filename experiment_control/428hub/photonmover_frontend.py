#----------------------------------------------------------------------------
# Name:         photonmover_frontend.py
# Purpose:      Graphical Frontend for data acquisition.
#
# Author:       Marc de Cea, based on Jason Orcutt's code
#
# Created:      29 Sept 2008
# Copyright:    (c) 2008 by Jason Orcutt
# Licence:      MIT license
#----------------------------------------------------------------------------

# NOTE: this program requires wxPython 2.6 or newer
# Compared to Jason's code, this gets rid of all the code regarding the
# motorized control of the fiber position, which is no longer available


############################################################################
############################################################################
######                                                                ######
######                       Import Dependencies                      ######
######                                                                ######
############################################################################
############################################################################


import wx
import pickle
from GPIBManager import *
import time

############################################################################
############################################################################
######                                                                ######
######                     Define Global Constants                    ######
######                                                                ######
############################################################################
############################################################################


##-----------------------------------------------------
## GUI Object ID Definitions
##-----------------------------------------------------


# Menu Item Contants
ID_ABOUT = 101
ID_HW_INFO = 102
ID_EXIT = 110
ID_SAVE = 120
ID_LOAD = 130
ID_TAKE_INITIAL_POWER_TAP_CALIBRATION = 151
ID_TAKE_TRANSMISSION = 152
ID_TAKE_TRANSMISSION_FAST = 158
ID_TAKE_TRANSMISSION_TWO_PORT = 157
ID_TAKE_TRANSMISSION_BIAS = 159
ID_WATCH_TRANSMISSION = 160
ID_TAKE_ATTENPOWSCAN = 161
ID_TAKE_SANTECPOWSCAN = 165
ID_TAKE_SANTECPOWSWEEP = 166
ID_TAKE_IV = 153
ID_TAKE_IV2 = 169
ID_TAKE_RL = 154
ID_TAKE_RV = 155
ID_TAKE_RLV = 156

ID_TAKE_RLP = 168
ID_NAIVE_INIT = 167


# Optics Control Constants
ID_LASER_WAVELENGTH_PARAM = 800
ID_THROUGH_LOSS_PARAM = 801
ID_RETURN_LOSS_PARAM = 802
ID_LASER_SOURCE_PARAM = 803
ID_LASER_POWER_PARAM = 804
ID_MEAS_WAVELENGTH_PARAM = 805
ID_MEAS_OUT_POWER_PARAM = 806
ID_MEAS_REC_POWER_PARAM = 807
ID_MEAS_TAP_POWER_PARAM = 821
ID_PHOTOCURRENT_CHANNEL_PARAM = 808
ID_MEAS_PHOTOCURRENT_PARAM = 809
ID_POWER_CALIBRATION_PARAM = 810
ID_CAL_FACTOR_PARAM = 811
ID_CALC_RESPONSIVITY_PARAM = 812
ID_CALC_QE_PARAM = 813
ID_PD_BIAS_VOLTAGE_PARAM = 814
ID_SWITCH_DIRECTION_BUTTON = 815
ID_DATA_FOLDER_PARAM = 816
ID_START_MEAS_WAVELENGTH_PARAM = 817
ID_STOP_MEAS_WAVELENGTH_PARAM = 818
ID_NUM_MEAS_WAVELENGTH_PARAM = 819
ID_MEAS_POWER_PARAM = 820
ID_START_MEAS_POWER_PARAM = 821
ID_STOP_MEAS_POWER_PARAM = 822
ID_NUM_MEAS_POWER_PARAM = 823
ID_START_MEAS_V_PARAM = 824
ID_STOP_MEAS_V_PARAM = 825
ID_NUM_MEAS_V_PARAM = 826


############################################################################
############################################################################
######                                                                ######
######                 Laser Button Class Definition                  ######
######                                                                ######
############################################################################
############################################################################


# Create a button class to handle the laser commands
class LaserButton(wx.ToggleButton):


    def __init__(self, parent):

        wx.ToggleButton.__init__(self, parent, -1, 'Laser Power', size=(75,20))

        self.parent = parent

        self.active = 0

        self.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggle)


    def OnToggle(self, event):

        if self.active == 0:
            self.parent.parent.parent.gpibManager.TurnOnLaser()
            self.active = 1
            self.parent.parent.sb.SetStatusText('Turning on the Source laser')
        else:
            self.parent.parent.parent.gpibManager.TurnOffLaser()
            self.active = 0
            self.parent.parent.sb.SetStatusText('Turning off the Source laser')


############################################################################
############################################################################
######                                                                ######
######              Controller Frame Class Definition                 ######
######                                                                ######
############################################################################
############################################################################

            
# Create a new frame class, derived from the wxPython Frame.
class ControllerFrame(wx.Frame):


    def __init__(self, parent, id, title):
        
        # First, call the base class' __init__ method to create the frame
        wx.Frame.__init__(self, None, id, title)

        # Save our variables
        self.parent = parent
        self.id = id
        self.title = title

        #iconFile = "./LabJackIcon.ico"
        #icon1 = wx.Icon(iconFile, wx.BITMAP_TYPE_ICO)
        #self.SetIcon(icon1)

        # Bind the close event to the function OnExit
        # (This assures that even if you hit the x button the
        # device gets properly closed.)
        self.Bind(wx.EVT_CLOSE, self.OnExit)

##-----------------------------------------------------
## Create the Menu and Status Bar
##-----------------------------------------------------

        # Add a status bar
        self.sb = self.CreateStatusBar()

        # Set up a File Menu
        filemenu = wx.Menu()
        filemenu.Append(ID_ABOUT, "&About"," Information about PhotonMover")
        filemenu.AppendSeparator()
        filemenu.Append(ID_EXIT,"E&xit"," Terminate PhotonMover")

        # Set up a Defaults Menu
        defaultsmenu = wx.Menu()
        defaultsmenu.Append(ID_SAVE, "&Save"," Save Current Parameters as Defaults")
        defaultsmenu.Append(ID_LOAD, "&Load"," Load Default Parameters")

        # Set up an Experiments Menu
        experimentsmenu = wx.Menu()
        experimentsmenu.Append(ID_TAKE_TRANSMISSION, "Transmission", " Measure transmission over preset wavelength set, constant bias")
        experimentsmenu.Append(ID_TAKE_TRANSMISSION_BIAS, "Transmission vs. bias", " Measure transmission over preset wavelength set and bias, constant power")
        experimentsmenu.Append(ID_TAKE_SANTECPOWSWEEP, "Transmission vs. power", "Perform wavelength sweeps at different power levels")
        experimentsmenu.Append(ID_TAKE_IV, "I-V", "IV curve at a specific power using the parameter analyzer with preset V steps")
        experimentsmenu.Append(ID_TAKE_IV2, "I-V 2 TIMES", "Two IV curves using parameter analyzer one dark one with newport laser driver on")
        experimentsmenu.Append(ID_TAKE_SANTECPOWSCAN, "Laser power scan fixed lambda", "Scan power at current wavelength")
        
        experimentsmenu.Append(ID_TAKE_RLV, "Responsivity-Lambda-V", " Measure responsivity over preset wavelength and bias set")
        experimentsmenu.Append(ID_TAKE_TRANSMISSION_FAST, "Transmission (Fast)?", " Measure transmission over preset wavelength set")
        experimentsmenu.Append(ID_TAKE_TRANSMISSION_TWO_PORT, "Transmission Two Port?", " Measure transmission over preset wavelength set")
        #experimentsmenu.Append(ID_TAKE_RL, "Responsivity-Lambda", " Measure responsivity over preset wavelength set")
        #experimentsmenu.Append(ID_TAKE_RV, "Responsivity-V", " Measure responsivity over preset bias set")
        experimentsmenu.Append(ID_WATCH_TRANSMISSION, "Transmission-Time", "Measure transmission over time")
        experimentsmenu.Append(ID_TAKE_RLP, "Responsivity-Lambda-P", "Measure responsivity over preset wavelength and power set")
       
        experimentsmenu.Append(ID_TAKE_ATTENPOWSCAN, "Attenuator power scan?", "Scan power at current wavelength")
        experimentsmenu.AppendSeparator()
        experimentsmenu.Append(ID_TAKE_INITIAL_POWER_TAP_CALIBRATION, "Calibration", " Routine to calibrate the setup's transmission vs. wavelength")
        experimentsmenu.AppendSeparator()
        experimentsmenu.Append(ID_NAIVE_INIT, "Naive Initialization Transmission vs Power", "Gets the transmission turning off the laser every time wavelength is changed.")
        #experimentsmenu.Append(ID_NULL_SPARAM, "Zero Parameter Analyzer", " Rezero the parameter analyzer channels")

        # Create the Menubar
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File")
        menuBar.Append(defaultsmenu,"&Defaults")
        menuBar.Append(experimentsmenu,"&Experiments")
        self.SetMenuBar(menuBar)

        # Add bindings for the menu items
        wx.EVT_MENU(self, ID_ABOUT, self.OnAbout)
        wx.EVT_MENU(self, ID_EXIT, self.OnExit)
        wx.EVT_MENU(self, ID_SAVE, self.OnSave)
        wx.EVT_MENU(self, ID_LOAD, self.OnLoad)
        wx.EVT_MENU(self, ID_TAKE_INITIAL_POWER_TAP_CALIBRATION, self.OnInitialCalibration)
        wx.EVT_MENU(self, ID_TAKE_TRANSMISSION, self.OnTransmission)
        wx.EVT_MENU(self, ID_WATCH_TRANSMISSION, self.OnWatchTransmission)
        wx.EVT_MENU(self, ID_TAKE_TRANSMISSION_BIAS, self.OnTransmissionBias)
        wx.EVT_MENU(self, ID_TAKE_TRANSMISSION_FAST, self.OnTransmissionFast)
        wx.EVT_MENU(self, ID_TAKE_TRANSMISSION_TWO_PORT, self.OnTransmissionTwoPort)
        wx.EVT_MENU(self, ID_TAKE_SANTECPOWSCAN, self.OnSantecPowScan)
        wx.EVT_MENU(self, ID_TAKE_SANTECPOWSWEEP, self.OnSantecPowSweep)
        wx.EVT_MENU(self, ID_TAKE_ATTENPOWSCAN, self.OnAttenPowScan)
        wx.EVT_MENU(self, ID_TAKE_IV, self.OnIV)
        wx.EVT_MENU(self, ID_TAKE_IV2, self.OnIV2)
        wx.EVT_MENU(self, ID_TAKE_RLV, self.OnRLV)
        wx.EVT_MENU(self, ID_NAIVE_INIT, self.OnNaiveInit)
        wx.EVT_MENU(self, ID_TAKE_RLP, self.OnRLP)

##-----------------------------------------------------
## Initialize the panel
##-----------------------------------------------------

        # Initialize panel
        panel = wx.Panel(self, -1)

        # Add panel to frame
        panel.parent = self
        self.panel = panel

##-----------------------------------------------------
## Define the GUI controls to populate the panel
##-----------------------------------------------------

        # Create a font for headings
        headingFont = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        
        opticsControlHeading = wx.StaticText(panel,-1, 'Optics Status and Controls')
        opticsControlHeading.SetFont(headingFont)
        
        # Optics controls
        switchDirectionButton = wx.Button(panel, ID_SWITCH_DIRECTION_BUTTON, "Toggle Direction", size=(100,20))
        laserSourceLabel = wx.StaticText(panel,-1, 'Choose Laser Source:')
        self.laserSourceMenu =  wx.ComboBox(panel, ID_LASER_SOURCE_PARAM, value = "HP", choices = ["Santec", "HP", "IsgSantec", "IsgSantecFINE"], style = wx.CB_READONLY)
        laserPowerButton = LaserButton(panel)
        laserWavelengthLabel = wx.StaticText(panel,-1, 'Set Wave:')
        self.laserWavelengthParam = wx.TextCtrl(panel, ID_LASER_WAVELENGTH_PARAM, "%.2f" % self.parent.wavelength , size=(60,20), style=wx.TE_PROCESS_ENTER)
        laserPowerLabel = wx.StaticText(panel,-1, 'Set Power:')
        self.laserPowerParam = wx.TextCtrl(panel, ID_LASER_POWER_PARAM, "%.2f" % self.parent.power , size=(40,20), style=wx.TE_PROCESS_ENTER)
        measPowerLabel = wx.StaticText(panel,-1, 'Meas. Power:')
        self.measPowerParam = wx.TextCtrl(panel, ID_MEAS_POWER_PARAM, "????", size=(80,20), style=wx.TE_READONLY)
        measWavelengthLabel = wx.StaticText(panel,-1, 'Meas. Wave:')
        self.measWavelengthParam = wx.TextCtrl(panel, ID_MEAS_WAVELENGTH_PARAM, "????", size=(70,20), style=wx.TE_READONLY)
        powerCalibrationLabel = wx.StaticText(panel,-1, 'Power Calib.:')
        self.powerCalibrationMenu =  wx.ComboBox(panel, ID_POWER_CALIBRATION_PARAM, value = "L-R 90:10 splitter", choices = ["L-R 90:10 splitter", "R-L 90:10 splitter", "None"], style = wx.CB_READONLY)
        #calFactorLabel = wx.StaticText(panel, -1, 'Cal Factor:')
        #self.calFactorParam = wx.TextCtrl(panel,ID_CAL_FACTOR_PARAM,"--.---",size=(50,20), style=wx.TE_READONLY)
        #measOutPowerLabel = wx.StaticText(panel, -1, 'Output Power:')
        #self.measOutPowerParam = wx.TextCtrl(panel,ID_MEAS_OUT_POWER_PARAM,"--.---",size=(80,20), style=wx.TE_READONLY)
        measRecPowerLabel = wx.StaticText(panel, -1, 'Received Power:')
        self.measRecPowerParam = wx.TextCtrl(panel,ID_MEAS_REC_POWER_PARAM,"--.---",size=(80,20), style=wx.TE_READONLY)
        tapPowerLabel = wx.StaticText(panel, -1, 'Tap power:')
        self.measTapPowerParam = wx.TextCtrl(panel,ID_MEAS_TAP_POWER_PARAM,"--.---",size=(80,20), style=wx.TE_READONLY)
        throughLossLabel = wx.StaticText(panel, -1, 'Loss:')
        self.throughLossParam = wx.TextCtrl(panel,ID_THROUGH_LOSS_PARAM,"--.---",size=(60,20), style=wx.TE_READONLY)
        returnLossLabel = wx.StaticText(panel, -1, 'Refl:')
        self.returnLossParam = wx.TextCtrl(panel,ID_RETURN_LOSS_PARAM,"--.---",size=(50,20), style=wx.TE_READONLY)
        photocurrentChannelLabel = wx.StaticText(panel,-1, 'PD Ch.:')
        self.photocurrentChannelParam =  wx.TextCtrl(panel, ID_PHOTOCURRENT_CHANNEL_PARAM, "%d" % self.parent.sparamChannel , size=(20,20), style=wx.TE_PROCESS_ENTER)
        pdBiasVoltageLabel = wx.StaticText(panel,-1, 'PD Bias:')
        self.pdBiasVoltageParam =  wx.TextCtrl(panel, ID_PD_BIAS_VOLTAGE_PARAM, "%d" % self.parent.pdBias, size=(20,20), style=wx.TE_PROCESS_ENTER)
        measPhotocurrentLabel = wx.StaticText(panel,-1, 'Photocurrent:')
        self.measPhotocurrentParam =  wx.TextCtrl(panel, ID_MEAS_PHOTOCURRENT_PARAM, "????" , size=(100,20), style=wx.TE_READONLY)
        calcResponsivityLabel = wx.StaticText(panel,-1, 'Calc. Resp.:')
        self.calcResponsivityParam =  wx.TextCtrl(panel, ID_CALC_RESPONSIVITY_PARAM, "????" , size=(50,20), style=wx.TE_READONLY)
        calcQELabel = wx.StaticText(panel,-1, 'Calc. QE:')
        self.calcQEParam =  wx.TextCtrl(panel, ID_CALC_QE_PARAM, "????" , size=(50,20), style=wx.TE_READONLY)

        # Optics measurement controls
        dataFolderLabel = wx.StaticText(panel, -1, 'Data Folder: ')
        self.dataFolderParam = wx.TextCtrl(panel, ID_DATA_FOLDER_PARAM, self.parent.dataFolder, size=(200,20), style=wx.TE_PROCESS_ENTER)
            # Wavelength range
        startMeasWavelengthLabel = wx.StaticText(panel, -1, 'Start Lambda: ')
        self.startMeasWavelengthParam = wx.TextCtrl(panel, ID_START_MEAS_WAVELENGTH_PARAM, str(self.parent.startMeasWavelength), size=(100,20), style=wx.TE_PROCESS_ENTER)
        stopMeasWavelengthLabel = wx.StaticText(panel, -1, 'Stop Lambda: ')
        self.stopMeasWavelengthParam = wx.TextCtrl(panel, ID_STOP_MEAS_WAVELENGTH_PARAM, str(self.parent.stopMeasWavelength), size=(100,20), style=wx.TE_PROCESS_ENTER)
        numMeasWavelengthLabel = wx.StaticText(panel, -1, 'Num Lambda: ')
        self.numMeasWavelengthParam = wx.TextCtrl(panel, ID_NUM_MEAS_WAVELENGTH_PARAM, str(self.parent.numMeasWavelength), size=(60,20), style=wx.TE_PROCESS_ENTER)
            # Power range
        startMeasPowerLabel = wx.StaticText(panel, -1, 'Start Power: ')
        self.startMeasPowerParam = wx.TextCtrl(panel, ID_START_MEAS_POWER_PARAM, str(self.parent.startMeasPower), size=(100,20), style=wx.TE_PROCESS_ENTER)
        stopMeasPowerLabel = wx.StaticText(panel, -1, 'Stop Power: ')
        self.stopMeasPowerParam = wx.TextCtrl(panel, ID_STOP_MEAS_POWER_PARAM, str(self.parent.stopMeasPower), size=(100,20), style=wx.TE_PROCESS_ENTER)
        numMeasPowerLabel = wx.StaticText(panel, -1, 'Num Power: ')
        self.numMeasPowerParam = wx.TextCtrl(panel, ID_NUM_MEAS_POWER_PARAM, str(self.parent.numMeasPower), size=(60,20), style=wx.TE_PROCESS_ENTER)
            # Bias range
        startMeasVLabel = wx.StaticText(panel, -1, 'Start Bias: ')
        self.startMeasVParam = wx.TextCtrl(panel, ID_START_MEAS_V_PARAM, str(self.parent.startMeasV), size=(100,20), style=wx.TE_PROCESS_ENTER)
        stopMeasVLabel = wx.StaticText(panel, -1, 'Stop Bias: ')
        self.stopMeasVParam = wx.TextCtrl(panel, ID_STOP_MEAS_V_PARAM, str(self.parent.stopMeasV), size=(100,20), style=wx.TE_PROCESS_ENTER)
        numMeasVLabel = wx.StaticText(panel, -1, 'Num Bias: ')
        self.numMeasVParam = wx.TextCtrl(panel, ID_NUM_MEAS_V_PARAM, str(self.parent.numMeasV), size=(60,20), style=wx.TE_PROCESS_ENTER)
        
        # Add connections for update events
        self.throughLossParam.Connect(-1,-1,EVT_LWMAIN, self.OnLWMain)
        self.returnLossParam.Connect(-1,-1,EVT_LWDONE, self.OnDone)

        # Add bindings for the optics controls
        self.Bind(wx.EVT_BUTTON, self.ToggleDirection, id = ID_SWITCH_DIRECTION_BUTTON)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnWavelengthChange, id=ID_LASER_WAVELENGTH_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnPowerChange, id=ID_LASER_POWER_PARAM)
        self.Bind(wx.EVT_COMBOBOX, self.OnLaserChange, id=ID_LASER_SOURCE_PARAM)
        self.Bind(wx.EVT_COMBOBOX, self.OnCalibrationChange, id=ID_POWER_CALIBRATION_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnSParamChannelChange, id=ID_PHOTOCURRENT_CHANNEL_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnBiasChange, id=ID_PD_BIAS_VOLTAGE_PARAM)

        # Add binding for measurement controlls
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_DATA_FOLDER_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_START_MEAS_WAVELENGTH_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_STOP_MEAS_WAVELENGTH_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_NUM_MEAS_WAVELENGTH_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_START_MEAS_POWER_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_STOP_MEAS_POWER_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_NUM_MEAS_POWER_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_START_MEAS_V_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_STOP_MEAS_V_PARAM)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnMeasurementParamChange, id = ID_NUM_MEAS_V_PARAM)

##-----------------------------------------------------
## Create the sizers and populate with defined controls
##-----------------------------------------------------

        # Create and populate optics control sizer
        opticsControlSizer0 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer0.Add(switchDirectionButton)

        opticsControlSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer1.Add(laserSourceLabel)
        opticsControlSizer1.AddSpacer((3,3))
        opticsControlSizer1.Add(self.laserSourceMenu)
        opticsControlSizer1.AddSpacer((8,8))
        opticsControlSizer1.Add(laserPowerButton)

        opticsControlSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer2.Add(laserWavelengthLabel)
        opticsControlSizer2.AddSpacer((3,3))
        opticsControlSizer2.Add(self.laserWavelengthParam)
        opticsControlSizer2.AddSpacer((8,8))
        opticsControlSizer2.Add(measWavelengthLabel)
        opticsControlSizer2.AddSpacer((3,3))
        opticsControlSizer2.Add(self.measWavelengthParam)

        opticsControlSizer2a = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer2a.Add(laserPowerLabel)
        opticsControlSizer2a.AddSpacer((3,3))
        opticsControlSizer2a.Add(self.laserPowerParam)
        opticsControlSizer2a.AddSpacer((8,8))
        opticsControlSizer2a.Add(measPowerLabel)
        opticsControlSizer2a.AddSpacer((3,3))
        opticsControlSizer2a.Add(self.measPowerParam)

        opticsControlSizer3 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer3.Add(powerCalibrationLabel)
        opticsControlSizer3.AddSpacer((3,3))
        opticsControlSizer3.Add(self.powerCalibrationMenu)
        #opticsControlSizer3.AddSpacer((8,8))
        #opticsControlSizer3.Add(calFactorLabel)
        #opticsControlSizer3.AddSpacer((3,3))
        #opticsControlSizer3.Add(self.calFactorParam)

        opticsControlSizer4 = wx.BoxSizer(wx.HORIZONTAL)
        #opticsControlSizer4.Add(measOutPowerLabel)
        #opticsControlSizer4.AddSpacer((3,3))
        #opticsControlSizer4.Add(self.measOutPowerParam)
        #opticsControlSizer4.AddSpacer((8,8))
        opticsControlSizer4.Add(measRecPowerLabel)
        opticsControlSizer4.AddSpacer((3,3))
        opticsControlSizer4.Add(self.measRecPowerParam)

        opticsControlSizer4a = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer4a.Add(tapPowerLabel)
        opticsControlSizer4a.AddSpacer((3,3))
        opticsControlSizer4a.Add(self.measTapPowerParam)

        opticsControlSizer5 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer5.Add(throughLossLabel) 
        opticsControlSizer5.AddSpacer((3,3))
        opticsControlSizer5.Add(self.throughLossParam) 
        opticsControlSizer5.AddSpacer((8,8))
        opticsControlSizer5.Add(returnLossLabel) 
        opticsControlSizer5.AddSpacer((3,3))
        opticsControlSizer5.Add(self.returnLossParam) 

        opticsControlSizer6 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer6.Add(photocurrentChannelLabel) 
        opticsControlSizer6.AddSpacer((3,3))
        opticsControlSizer6.Add(self.photocurrentChannelParam) 
        opticsControlSizer6.AddSpacer((8,8))
        opticsControlSizer6.Add(pdBiasVoltageLabel) 
        opticsControlSizer6.AddSpacer((3,3))
        opticsControlSizer6.Add(self.pdBiasVoltageParam) 
        opticsControlSizer6.AddSpacer((8,8))
        opticsControlSizer6.Add(measPhotocurrentLabel) 
        opticsControlSizer6.AddSpacer((3,3))
        opticsControlSizer6.Add(self.measPhotocurrentParam) 

        opticsControlSizer7 = wx.BoxSizer(wx.HORIZONTAL)
        opticsControlSizer7.Add(calcResponsivityLabel) 
        opticsControlSizer7.AddSpacer((3,3))
        opticsControlSizer7.Add(self.calcResponsivityParam) 
        opticsControlSizer7.AddSpacer((8,8))
        opticsControlSizer7.Add(calcQELabel) 
        opticsControlSizer7.AddSpacer((3,3))
        opticsControlSizer7.Add(self.calcQEParam) 

        measurementParameterSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer1.Add(dataFolderLabel)
        measurementParameterSizer1.Add(self.dataFolderParam)

        measurementParameterSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer2.Add(startMeasWavelengthLabel)
        measurementParameterSizer2.AddSpacer((3,3))
        measurementParameterSizer2.Add(self.startMeasWavelengthParam)

        measurementParameterSizer2a = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer2a.Add(stopMeasWavelengthLabel)
        measurementParameterSizer2a.AddSpacer((3,3))
        measurementParameterSizer2a.Add(self.stopMeasWavelengthParam)

        measurementParameterSizer3 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer3.Add(numMeasWavelengthLabel)
        measurementParameterSizer3.Add(self.numMeasWavelengthParam)
        measurementParameterSizer3.AddSpacer((3,3))

        measurementParameterSizer4 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer4.Add(startMeasPowerLabel)
        measurementParameterSizer4.AddSpacer((3,3))
        measurementParameterSizer4.Add(self.startMeasPowerParam)

        measurementParameterSizer4a = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer4a.Add(stopMeasPowerLabel)
        measurementParameterSizer4a.AddSpacer((3,3))
        measurementParameterSizer4a.Add(self.stopMeasPowerParam)

        measurementParameterSizer5 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer5.Add(numMeasPowerLabel)
        measurementParameterSizer5.Add(self.numMeasPowerParam)
        
        measurementParameterSizer6 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer6.Add(startMeasVLabel)
        measurementParameterSizer6.AddSpacer((3,3))
        measurementParameterSizer6.Add(self.startMeasVParam)

        measurementParameterSizer6a = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer6a.Add(stopMeasVLabel)
        measurementParameterSizer6a.AddSpacer((3,3))
        measurementParameterSizer6a.Add(self.stopMeasVParam)

        measurementParameterSizer7 = wx.BoxSizer(wx.HORIZONTAL)
        measurementParameterSizer7.Add(numMeasVLabel)
        measurementParameterSizer7.Add(self.numMeasVParam)

        
##-----------------------------------------------------
## Top Level Sizer Creation and Population
##-----------------------------------------------------
        
        # Create and populate the top level sizer
        rightHighLevelSizer = wx.BoxSizer(wx.VERTICAL)
        rightHighLevelSizer.Add(opticsControlHeading,0,wx.BOTTOM,10)
        rightHighLevelSizer.Add(opticsControlSizer0,0,wx.ALIGN_LEFT | wx.BOTTOM,20)
        rightHighLevelSizer.Add(opticsControlSizer1,0,wx.ALIGN_LEFT | wx.BOTTOM,20)
        rightHighLevelSizer.Add(opticsControlSizer2,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(opticsControlSizer2a,0,wx.ALIGN_LEFT | wx.BOTTOM,20)
        rightHighLevelSizer.Add(opticsControlSizer3,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(opticsControlSizer4,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(opticsControlSizer4a,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(opticsControlSizer5,0,wx.ALIGN_LEFT | wx.BOTTOM,20)
        rightHighLevelSizer.Add(opticsControlSizer6,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(opticsControlSizer7,0,wx.ALIGN_LEFT | wx.BOTTOM,20)
        rightHighLevelSizer.Add(measurementParameterSizer1,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer2,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer2a,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer3,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer4,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer4a,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer5,0,wx.ALIGN_LEFT)
        rightHighLevelSizer.Add(measurementParameterSizer6,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer6a,0,wx.ALIGN_LEFT | wx.BOTTOM,5)
        rightHighLevelSizer.Add(measurementParameterSizer7,0,wx.ALIGN_LEFT)

        topLevelSizer = wx.BoxSizer(wx.HORIZONTAL)
        topLevelSizer.Add(rightHighLevelSizer)
        
        # Create the outer box and fit it all
        border = wx.BoxSizer()
        border.Add(topLevelSizer, 0, wx.ALL | wx.EXPAND, 10)
        self.panel.SetSizerAndFit(border)
        self.Fit()

        
##-----------------------------------------------------
## GUI Parameter Bindings
##-----------------------------------------------------

    def ToggleDirection(self,event):
        self.parent.ljManager.ToggleSwitchState()
    
    # Binding for wavelength parameter change
    def OnWavelengthChange(self, event):
        self.parent.wavelength = float(self.laserWavelengthParam.GetValue())
        self.parent.gpibManager.SetWavelength(self.parent.wavelength)
        self.sb.SetStatusText('Adjusting the Laser Wavelength to %.2f' % self.parent.wavelength)


    # Binding for power parameter change
    def OnPowerChange(self, event):
        self.parent.power = float(self.laserPowerParam.GetValue())
        self.parent.gpibManager.SetPower(self.parent.power)
        self.sb.SetStatusText('Adjusting the Laser Power to %.2f' % self.parent.power)


    # Binding for laser source change
    def OnLaserChange(self, event):
        self.parent.laserSource = self.laserSourceMenu.GetValue()


    # Binding for calibration set change
    def OnCalibrationChange(self, event):
        self.parent.calSet = self.powerCalibrationMenu.GetValue()
        self.sb.SetStatusText('Changing the Calibration to %s' % self.parent.calSet)
        self.parent.LoadCalibration()


    # Binding for parameter analyzer photocurrent channel change
    def OnSParamChannelChange(self, event):    
        self.parent.sparamChannel = int(self.photocurrentChannelParam.GetValue())
        self.parent.gpibManager.SetBias()


    # Binding for parameter analyzer bias voltage change
    def OnBiasChange(self, event):
        try:
            self.parent.pdBias = float(self.pdBiasVoltageParam.GetValue())
        except:
            self.parent.pdBias = 0.0
        self.parent.gpibManager.SetBias()

    # Binding for measurement parameter change
    def OnMeasurementParamChange(self, event):
        if event.GetId() == ID_DATA_FOLDER_PARAM:
            self.parent.dataFolder = self.dataFolderParam.GetValue()
            self.sb.SetStatusText('Setting the Default Data Folder')
        elif event.GetId() == ID_START_MEAS_WAVELENGTH_PARAM:
            self.parent.startMeasWavelength = float(self.startMeasWavelengthParam.GetValue())
            self.sb.SetStatusText('Setting the Start Wavelength for Transmission Scan')
        elif event.GetId() == ID_STOP_MEAS_WAVELENGTH_PARAM:
            self.parent.stopMeasWavelength = float(self.stopMeasWavelengthParam.GetValue())
            self.sb.SetStatusText('Setting the Stop Wavelength for Transmission Scan')
        elif event.GetId() == ID_NUM_MEAS_WAVELENGTH_PARAM:
            self.parent.numMeasWavelength = int(self.numMeasWavelengthParam.GetValue())
            self.sb.SetStatusText('Setting Number of Wavelengths for Transmission Scan')
        elif event.GetId() == ID_START_MEAS_POWER_PARAM:
            self.parent.startMeasPower = float(self.startMeasPowerParam.GetValue())
            self.sb.SetStatusText('Setting the Start Power for Transmission Scan')
        elif event.GetId() == ID_STOP_MEAS_POWER_PARAM:
            self.parent.stopMeasPower = float(self.stopMeasPowerParam.GetValue())
            self.sb.SetStatusText('Setting the Stop Power for Transmission Scan')
        elif event.GetId() == ID_NUM_MEAS_POWER_PARAM:
            self.parent.numMeasPower = int(self.numMeasPowerParam.GetValue())
            self.sb.SetStatusText('Setting Number of Powers for Transmission Scan')
        elif event.GetId() == ID_START_MEAS_V_PARAM:
            self.parent.startMeasV = float(self.startMeasVParam.GetValue())
            self.sb.SetStatusText('Setting the Start V for Transmission Scan')
        elif event.GetId() == ID_STOP_MEAS_V_PARAM:
            self.parent.stopMeasV = float(self.stopMeasVParam.GetValue())
            self.sb.SetStatusText('Setting the Stop V for Transmission Scan')
        elif event.GetId() == ID_NUM_MEAS_V_PARAM:
            self.parent.numMeasV = int(self.numMeasVParam.GetValue())
            self.sb.SetStatusText('Setting Number of V for Transmission Scan')

        else:
            print('ERROR: Uncaught ID in OnMeasurementParamChange')

##-----------------------------------------------------
## Menu item Bindings
##-----------------------------------------------------
            
        
    # Binding for File Menu item About
    def OnAbout(self,e):
        d = wx.MessageDialog(self, " A GUI front-end for the PhotonMover test setup \n"
                            " to enable two-port optical testing \n"
                            "\n By Jason Orcutt, 2008", "About PhotonMover", wx.OK)
        d.ShowModal()
        d.Destroy()


    # Binding for Defaults Menu item Save
    def OnSave(self,e):
        pickleFileObject = open(self.parent.pickleFile, 'w')
        pickle.dump(self.parent.data, pickleFileObject)
        pickleFileObject.close()
        

    # Binding for Defaults Menu item Load
    def OnLoad(self,e):
        self.parent.LoadDefaultData()
        

    # Binding for File Menu item Exit and interupt for close events.
    def OnExit(self,e):
        
        self.parent.done = 1
#        Ebrahim
#        self.parent.ipicoManager.close()
        
        #Changed by Marc (no LJ manager used)
        # if self.parent.ljManager.running == 0 and self.parent.gpibManager.running == 0:
        if self.parent.gpibManager.running == 0:

                self.Destroy()

        else:
            # Changed by Marc (no LJ manager used)
            # self.parent.ljManager.close()
            self.parent.gpibManager.close()


    # Menu binding for transmission experiment
    def OnTransmission(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.TransmissionScan(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()

    # Menu binding for transmission experiment
    def OnWatchTransmission(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Transmission Watching Routine'
           self.parent.gpibManager.WatchTransmissionFunction(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
 
    # Menu binding for transmission experiment
    def OnTransmissionBias(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.TransmissionBiasScan(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
        
    def OnSantecPowScan(self,e):
        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.SantecPowerScan(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()

    def OnSantecPowSweep(self,e):
        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.SantecPowerSweep(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
        
    def OnNaiveInit(self,e):
        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Naive Initialization Transmission measurement'
           self.parent.gpibManager.NaiveInitPowSweep(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
        

    def OnAttenPowScan(self,e):
        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.AttenPowerScan(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
        

    
    # Menu binding for transmission experiment
    def OnTransmissionFast(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.TransmissionScanFast(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()

    # Menu binding for transmission experiment
    def OnTransmissionTwoPort(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = self.parent.dataFolder, style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Scattering Measurement Routine'
           self.parent.gpibManager.TransmissionScanTwoPort(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()


    # Menu binding for transmission experiment
    def OnIV(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = 'C:\\Users\\POE\\Documents', style = wx.SAVE)
        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting IV Measurement Routine'
           self.parent.gpibManager.TakeIV(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()

	# Menu binding for transmission experiment
    def OnIV2(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = 'C:\\Users\\POE\\Documents', style = wx.SAVE)
        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting Dark and Laser IV Measurement Routine'
           self.parent.gpibManager.TakeIV2(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()


    # Menu binding for transmission experiment
    def OnRLV(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = 'C:\\Users\\POE\\Documents', style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting RLV Measurement Routine'
           self.parent.gpibManager.TakeRLV(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()
        
    # Menu binding for RLV experiment
    def OnRLP(self,e):

        dialog = wx.FileDialog(None, message = 'Enter only the measurement reference in the correct directory',
                                    defaultDir = 'C:\\Users\\POE\\Documents', style = wx.SAVE)

        if dialog.ShowModal() == wx.ID_OK:
           print 'Starting RLP Measurement Routine'
           self.parent.gpibManager.TakeRLP(dialog.GetPath())
        else:
           print 'Nothing was selected.'

        dialog.Destroy()


    # Menu binding for calibration routine
    def OnInitialCalibration(self,e):

        choices = ['L-R 90:10 splitter', 'R-L 90:10 spplitter', 'None']

        dialog = wx.SingleChoiceDialog( None, 'Ensure fibers are connected correctly!', 'Photonmover Calibrations', choices )
 
        # The user pressed the "OK" button in the dialog
        if dialog.ShowModal() == wx.ID_OK:

           choiceResult = dialog.GetSelection()
           if choiceResult == 0:
               print 'Starting L-R 90:10 Calibration Routine'
               self.parent.gpibManager.L2RBypassCalibration()
           elif choiceResult == 1:
               print 'Starting R-L 90:10 Calibration Routine'
               self.parent.gpibManager.R2LBypassCalibration()
           elif choiceResult == 2:
               print 'Starting No Calibration Routine'
               self.parent.gpibManager.NoCalibration()

        # The user exited the dialog without pressing the "OK" button
        else:

           print 'You did not select anything. No calibration will be performed'

        dialog.Destroy()


##-----------------------------------------------------
## SubThread Related Bindings
##-----------------------------------------------------


    # When a subthread finishes, it creates a done event. If the 
    # program is ready to be closed, the program will quit.
    def OnDone(self,event):
        if self.parent.done == 1 and self.parent.gpibManager.done == 1 and self.parent.ljManager.done == 1:
            self.Destroy()


    # What to do when the optics update readings have changed
    def OnLWMain(self,event):
        self.throughLossParam.SetValue("%.3f" % event.through_loss)
        self.returnLossParam.SetValue("%.3f" % event.return_loss)
        self.measPowerParam.SetValue("%.3e" % event.out_power)
        self.measWavelengthParam.SetValue("%.5f" % event.wavelength)
        #self.calFactorParam.SetValue("%.1f" % event.cal_factor)
        #self.measOutPowerParam.SetValue("%.3e" % event.out_power)
        self.measRecPowerParam.SetValue("%.3e" % event.rec_power)
        self.measTapPowerParam.SetValue("%.3e" % event.rec_power2)
        self.measPhotocurrentParam.SetValue("%.3e" % event.photocurrent)
        self.calcResponsivityParam.SetValue("%.3f" % event.responsivity)
        self.calcQEParam.SetValue("%d%%" % event.qe)



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
        self.wavelength = 1550.00 # nm

        # Initialize to generic wavelength
        self.power = 1.00 # dBm

        # Laser Source
        self.laserSource = "Santec"

        # Calibration
        self.calSet = "L-R 90:10 splitter"
        self.direction = "LEFT_TO_RIGHT"

        # Responsivity Channel
        self.sparamChannel = 1

        # Photodiode Bias Voltage
        self.pdBias = 0.0

        # Measurement Parameters
        self.dataFolder = 'C:\\Users\\POE\\Documents'
        self.startMeasWavelength = 1520.0
        self.stopMeasWavelength = 1580.0
        self.numMeasWavelength = 120

        self.startMeasPower = -10
        self.stopMeasPower = 0
        self.numMeasPower = 5
        
        self.startMeasV = 0
        self.stopMeasV = -3
        self.numMeasV = 5

        # Program state indicator
        self.done = 0

        # File for persistent data storage and dict class
        self.data = dict()
        self.pickleFile = 'C:\\Users\\POE\\Desktop\\photonmover_MARC\\persistent_parameter_data.pickle'

        # Persistent calibration pickle
        self.opticalCalibration = list()
        self.opticalCalibrationFile_1 = 'C:\\Users\\POE\\Desktop\\photonmover_MARC\\cal_l-r_bypass_patchcord.pickle'
        self.opticalCalibrationFile_2 = 'C:\\Users\\POE\\Desktop\\photonmover_MARC\\cal_r-l_bypass_patchcord.pickle'
        self.opticalCalibrationFile_None = 'C:\\Users\\POE\\Desktop\\photonmover_MARC\\no_cal.pickle'

        # Create an instance of our customized Frame class
        self.appFrame = ControllerFrame(self, -1, "PhotonMover Fiber Control Front-End")
        
        # Create an instance of the GPIB Manager Class
        self.gpibManager = GPIBManager(self, self.appFrame.throughLossParam, self.appFrame.returnLossParam)
        
        # Show the application
        self.appFrame.Show(True)

        # Tell wxWindows that this is our main window
        self.SetTopWindow(self.appFrame)
        
        # Initialize our variables
        self.LoadDefaultData()

        # Spawn the main loop to manage gpib connections and begin polling power sensors.
        self.gpibManager.start()
        time.sleep(0.001)

        # Set the wavelength to the default wavelength
        self.gpibManager.SetWavelength(self.wavelength) 

        # Return a success flag
        return True


    # Load default variable values
    def LoadDefaultData(self):

        # Load data from the pickle files
        pickleFileObject = open(self.pickleFile, 'r')
        self.data = pickle.load(pickleFileObject)
        pickleFileObject.close()

        self.LoadCalibration()        

    # Load default variable values
    def LoadCalibration(self):
        print self.calSet
        if self.calSet == "L-R 90:10 splitter":
            pickleFileObject = open(self.opticalCalibrationFile_1, 'r')
            self.direction = "LEFT_TO_RIGHT"
            
        elif self.calSet ==  "R-L 90:10 splitter":
            pickleFileObject = open(self.opticalCalibrationFile_2, 'r')
            self.direction = "RIGHT_TO_LEFT"
            
        elif self.calSet == "None":
            pickleFileObject = open(self.opticalCalibrationFile_None, 'r')
            self.direction = "NO_CAL"
            
            
        self.opticalCalibration = pickle.load(pickleFileObject)
        pickleFileObject.close()

        self.gpibManager.UpdateCalibration()



############################################################################
############################################################################
######                                                                ######
######                Code to run when main application               ######
######                                                                ######
############################################################################
############################################################################


if __name__ == "__main__":
    
    app = ControllerApp(0)     # Create an instance of the application class
    app.MainLoop()              # Tell it to start processing events

