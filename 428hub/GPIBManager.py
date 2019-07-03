#----------------------------------------------------------------------------
# Name:         LJManager.py
# Purpose:      Threaded controller for the U3 LabJack with internal
#               scheduling loop and utility classes
#
# Author:       Jason Orcutt
#
# Created:      22 Oct 2008
# Copyright:    (c) 2008 by Jason Orcutt
# Licence:      MIT license
#----------------------------------------------------------------------------

# NOTE: this program requires wxPython 2.6 or newer


############################################################################
############################################################################
######                                                                ######
######                       Import Dependencies                      ######
######                                                                ######
############################################################################
############################################################################


import os
import wx
import time
import threading
import pickle
from math import *
from scipy import *
import scipy.io as io
from visa import *
from ctypes import *
import winsound
import matplotlib.pyplot as plt
import csv
import numpy as np


############################################################################
############################################################################
######                                                                ######
######                    Define Global Constants                     ######
######                                                                ######
############################################################################
############################################################################


##-----------------------------------------------------
## Custom Event ID Definitions
##-----------------------------------------------------


EVT_LWMAIN = 13131315
EVT_LWDONE = 13131316


##-----------------------------------------------------
## Lightwave Mainframe Channel Definitions
##-----------------------------------------------------

# Attention! We use left_to_right and right_to_left as a legacy (so we don't have to write the code
# from scratch again). TO avoid confusion, the easiest thing is to set both variables 
# LEFT_POWER_TAP_CHANNEL and RIGHT_POWER_TAP_CHANNEL to the same channel (the channel to which
# the tap is actually connected). To be sure, also do the calibration twice, one for the 
# "left_to_right" option and one for the "right_to_left" option.

LEFT_POWER_TAP_CHANNEL = 1
RIGHT_POWER_TAP_CHANNEL = 2
RECEIVED_POWER_CHANNEL = 3
RECEIVED_POWER_2_CHANNEL = 4 # Doesn't matter, as long as it is neither of the channels we really care about
SPARAM_CURRENT_COMPLIANCE = 0.001 # Current compliance for the SPAram analyzer (A)

############################################################################
############################################################################
######                                                                ######
######        Custom WX Event Classes to Handle Communication         ######
######                                                                ######
############################################################################
############################################################################


# Simple wx event to handle lightwave mainframe data update events
class LWMainEvent(wx.PyEvent):
    
    def __init__(self, _through_loss, _return_loss, _cal_factor, _out_power, _rec_power, _rec_power2, _photocurrent, _responsivity, _qe, _wavelength):

        wx.PyEvent.__init__(self)

        self.SetEventType(EVT_LWMAIN)

        self.through_loss = _through_loss
        self.return_loss = _return_loss
        self.wavelength = _wavelength
        self.cal_factor = _cal_factor
        self.out_power = _out_power
        self.rec_power = _rec_power
        self.rec_power2 = _rec_power2
        self.photocurrent = _photocurrent
        self.responsivity = _responsivity
        self.qe = _qe

class LWDoneEvent(wx.PyEvent):

  
    def __init__(self, done):

        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_LWDONE)

        self.done = done
        

############################################################################
############################################################################
######                                                                ######
######     Threaded GPIBManager Class to Handle all Communication     ######
######                                                                ######
############################################################################
############################################################################

        
class GPIBManager( threading.Thread ):


    # The constructor. It will connect to a device.
    def __init__(self, _parent, _throughLossControl, _returnLossControl):
        
        # invoke constructor of parent class
        threading.Thread.__init__(self)

        # Add links to the GUI frame/window
        self.parent = _parent
        self.returnLossControl = _throughLossControl
        self.throughLossControl = _throughLossControl
        
        # State reporting variables initialized to 0
        self.error = 0
        self.done = 0
        self.running = 0
        self.loopActive = True

        # Wavelength specific calibration factor
        self.throughCalibrationFactor = -1.0
        self.outputCalibrationFactor = -1.0

        self.startCalWavelength = 1520.0
        self.stopCalWavelength = 1580.0
        self.numCalWavelengths = 70

        self.newWavelength = -10.0
        self.newPower = -10.0
        self.activeModule = -1

        # Control loop state variables
        self.setNewWavelength = 0
        self.setNewPower = 0
        self.turnOnLaser = 0
        self.turnOffLaser = 0
        self.setBias = 0
        self.transmissionScan = 0
        self.transmissionBiasScan = 0
        self.santecPowerScan = 0
        self.santecPowerSweep = 0
        self.attenPowerScan = 0
        self.pumpProbeScan = 0
        self.WatchTransmission = 0
        self.transmissionScanFast = 0
        self.transmissionScanTwoPort = 0
        self.takeIV = 0
        self.takeIV2 = 0
        self.takePI = 0
        self.takeRLV = 0
        self.takeRLP = 0
        self.takeRLP = 0
        self.l2rBypassCalibration = 0
        self.noCalibration = 0
        self.leftOutputCalibration = 0
        self.r2lBypassCalibration = 0
        self.rightOutputCalibration = 0
        self.leftLensedFiberCalibration = 0
        self.rightLensedFiberCalibration = 0
        self.naiveInitPowSweep = 0

        # PowerMeter delay control
        self.powerMeterPollDelay = 1
        self.sparamPollDelay = 5

        # Control loop delay variable
        self.loopDelayTime = 1e-4
        
        # Initialize the instrument handles
        rm = ResourceManager()
        try:
            self.sparam = rm.open_resource("GPIB0::17::INSTR", timeout = 10000)
            print "Parameter analyzer connected"
            self.SParamSetShortIntegrationTime()
        except:
            print "Parameter analyzer unreachable"
            self.sparam = None # comment
        
        try:
            self.optometer = rm.open_resource("GPIB0::2::INSTR", timeout = 100)
            print "ILX Lightwave connected"
        except:
            print "ILX Lightwave unreachable"
            self.optometer = None
        
        try:           
            self.lwmain = rm.open_resource("GPIB0::20::INSTR", timeout = 20000)
            # used to be 16 but is now 20?
            # switched to 19 11/25/2014 (using other lwmainframe)
            print "HP Lightwave connected"
        except:
            print "Lightwave mainframe unreachable"
            self.lwmain = None

        try:           
            self.laserdrv = rm.open_resource("GPIB0::5::INSTR", timeout = 20000)
            print "Newport Laser driver connected"
        except:
            print "Newport Laser driver unreachable"
            self.laserdrv = None


        try:
            self.santec1 = rm.open_resource("GPIB0::7::INSTR", timeout = 1000) # changed from 20 to 7
            self.santec2 = rm.open_resource("GPIB0::8::INSTR", timeout = 1000) # changed from 29 to 8
            self.santec3 = rm.open_resource("GPIB0::9::INSTR", timeout = 1000) # changed from 22 to 9
            self.santec4 = rm.open_resource("GPIB0::10::INSTR", timeout = 1000)  # changed from 23 to 10
            print "Santec laser connected"
            #self.santec1 = None
            #self.santec2 = None
            #self.santec3 = None
            #self.santec4 = None

        except:
            print "Santec unreachable"
            self.santec1 = None
            self.santec2 = None
            self.santec3 = None
            self.santec4 = None

        try:    
            self.isgsantec = rm.open_resource("GPIB::30", timeout = 50)
            print "IsgSantec connected"
        except:
            print "IsgSantec unreachable"
            self.isgsantec = None

        try:
            self.keithley = instrument("GPIB:26", timeout = 5000)
        except:
            print "Keithley gone"
            self.keithley = None

        try:
            self.lockin = rm.open_resource("GPIB::8", timeout = 10)
            print "SR844 Lock-In Amplifier connected"
        except:
            print "SR844 Lock-In Amplifier Unreachable"
            self.lockin = None
            
        #Load the wavemeter DLL
        self.bristoldll = CDLL("C:\BristolWavelengthMeterV2_31b\CLDevIFace.dll")
        self.bristol_handle = self.bristoldll.CLOpenUSBSerialDevice(c_long(3)) # had been 4
        if self.bristol_handle == -1:
            print "ERROR OPENING WAVEMETER"
            self.bristol_get_wave = None
        else:
        #self.bristoldll.CLSetAutoSend(c_uint(1))
        #self.bristoldll.CLSetAcqFreq(c_uint(1))
            self.bristol_get_wave = self.bristoldll.CLGetLambdaReading
            self.bristol_get_wave.restype = c_double
        #print self.WMeterGetWavelength()


##-----------------------------------------------------
## Threaded Main Loop Commands
##-----------------------------------------------------
    
        
    # when you call the start method, threading makes sure run gets called to start polling
    def run ( self ):
        
        #If there was some sort of error, don't start.
        if self.error == 0:
            
            #state that you are running.
            self.running = 1

            if self.lwmain:
                print("Intializing LWMain...")
                self.LWMainInitializeSensors()
            
            if self.sparam:
                print("Intializing SParam...")
                self.SParamInitializeChannel()

            if self.keithley:
                self.KeithleyInitializeChannel()

            # Initialize Loop Variables 
            powerMeterWaitCounter = 1
            requestAdded = False

            sparamWaitCounter = 1
            photocurrent = 0.0
            responsivity = 0.0
            qe = 0.0

            # As long as the thread thinks it's supposed to be running, it will. 
            while self.running != 0:
                try:
                    if self.loopActive:


                        if powerMeterWaitCounter >= self.powerMeterPollDelay:
                            powerMeterWaitCounter = 0
                            #through_loss, return_loss, out_power, rec_power  = self.LWMainGetTransmissions()
                            through_loss, return_loss, wavelength, out_power, rec_power, rec_power2 = self.LWMainGetTransmissions(twoPort=True)
                            #through_loss, through_loss2, return_loss, out_power, rec_power, rec_power2  

                            #wavelength = self.WMeterGetWavelength()
                            
                            if sparamWaitCounter >= self.sparamPollDelay:
                                sparamWaitCounter = 0
                                photocurrent = self.SParamGetPhotocurrent()
                                responsivity = photocurrent/(out_power+1.0e-15)
                                qe = responsivity*1.24/self.newWavelength*100.0

                            sparamWaitCounter = sparamWaitCounter+1

                            #wx.PostEvent(self.returnLossControl, LWMainEvent(through_loss, return_loss, self.throughCalibrationFactor, out_power, rec_power, 0, photocurrent, responsivity, qe, wavelength))
                            wx.PostEvent(self.returnLossControl, LWMainEvent(through_loss, return_loss, self.throughCalibrationFactor, out_power, rec_power, rec_power2, photocurrent, responsivity, qe, wavelength))

                        if self.setNewWavelength == 1:
                            print("Setting Wavelength...")
                            self.setNewWavelength = 0
                            self.LWMainSetWavelength()
                            self.LaserSetWavelength()

                        if self.setNewPower == 1:
                            print("Setting Output Power...")
                            self.setNewPower = 0
                            self.LaserSetOutputPower(self.newPower)

                        if self.turnOnLaser == 1:
                            print("Laser Turn On...")
                            self.turnOnLaser = 0
                            self.LaserTurnOn()
                            #self.LaserSetOutputPower(10.0)

                        if self.setBias == 1:
                            print("Setting Bias...")
                            self.setBias = 0
                            self.SParamSetBias(self.parent.pdBias)
                            time.sleep(1.0)

                        if self.turnOffLaser == 1:
                            print("Laser Turn Off...")
                            self.turnOffLaser = 0
                            self.LaserTurnOff()

                        if self.l2rBypassCalibration == 1:
                            self.l2rBypassCalibration = 0
                            self.PerformL2RSplitterCalibration()
                            
                        if self.noCalibration == 1:
                            self.noCalibration = 0
                            self.PerformNoCalibration()


                        if self.leftOutputCalibration == 1:
                            self.leftOutputCalibration = 0
                            self.PerformLeftOutputCalibration()

                        if self.r2lBypassCalibration == 1:
                            self.r2lBypassCalibration = 0
                            self.PerformR2LSplitterCalibration()

                        if self.rightOutputCalibration == 1:
                            self.rightOutputCalibration = 0
                            self.PerformRightOutputCalibration()

                        if self.leftLensedFiberCalibration == 1:
                            self.leftLensedFiberCalibration = 0
                            self.PerformLeftLensedFiberCalibration()

                        if self.rightLensedFiberCalibration == 1:
                            self.rightLensedFiberCalibration = 0
                            self.PerformRightLensedFiberCalibration()

                        if self.transmissionScan == 1:
                            self.transmissionScan = 0
                            self.PerformScatteringMeasurement()
                            
                        if self.transmissionBiasScan == 1:
                            self.transmissionBiasScan = 0
                            self.PerformTransmissionBiasMeasurement()

                        if self.santecPowerScan == 1:
                            self.santecPowerScan = 0
                            self.PerformSantecPowerScan()

                        if self.santecPowerSweep == 1:
                            self.santecPowerSweep = 0
                            self.PerformSantecPowerSweep()

                        if self.attenPowerScan == 1:
                            self.attenPowerScan = 0
                            self.PerformAttenPowerScan()

                        if self.pumpProbeScan == 1:
                            self.pumpProbeScan = 0
                            self.PerformPumpProbeScan()


                        if self.WatchTransmission == 1:
                            self.WatchTransmission = 0
                            self.PerformWatchTransmission()

                        if self.transmissionScanFast == 1:
                            self.transmissionScanFast = 0
                            self.PerformScatteringMeasurementFast()

                        if self.transmissionScanTwoPort == 1:
                            self.transmissionScanTwoPort = 0
                            self.PerformScatteringMeasurementTwoPort()

                        if self.takeIV == 1:
                            self.takeIV = 0
                            self.PerformIVMeasurement()

                        if self.takeIV2 == 1:
                            self.takeIV2 = 0
                            self.PerformIV2Measurement()

                        if self.takePI == 1:
                            self.takePI = 0
                            self.PerformPIMeasurement()


                        if self.takeRLV == 1:
                            self.takeRLV = 0
                            self.PerformRLVMeasurement()

                        if self.takeRLP == 1:
                            self.takeRLP = 0
                            self.PerformRLPMeasurement()
                        
                        if self.naiveInitPowSweep == 1:
                            self.naiveInitPowSweep = 0
                            self.PerformNaiveInitMeasurement()


                    powerMeterWaitCounter = powerMeterWaitCounter + 1
                    time.sleep(self.loopDelayTime)                    
                        
                except (Exception), ex:
                    print "I had an error", ex
                    self.running = 0
                    self.error = 1
                    e = ex

        # If we get here, either an error occurred or it was told to stop running.

        self.LaserTurnOff()

        if self.lwmain:
            self.lwmain.write("INIT%d:CHAN1:CONT 1" % LEFT_POWER_TAP_CHANNEL)
            self.lwmain.write("INIT%d:CHAN1:CONT 1" % RIGHT_POWER_TAP_CHANNEL)
            self.lwmain.write("INIT%d:CHAN1:CONT 1" % RECEIVED_POWER_CHANNEL)
            self.lwmain.write("INIT%d:CHAN1:CONT 1" % RECEIVED_POWER_2_CHANNEL)

        if self.sparam:
            self.SParamClose()
            
        wmeter_close_success = self.bristoldll.CLCloseDevice(self.bristol_handle)

        if not wmeter_close_success == 0:
            print "ERROR CLOSING BRISTOL WAVELENGTH METER DEVICE"
            
        self.done = 1
        wx.PostEvent(self.returnLossControl, LWDoneEvent(1))


##-----------------------------------------------------
## Commands Callable by Front-End
##-----------------------------------------------------

        
    # When you need to disconnect your only option is to call this function 
    def close(self):
        self.running = 0


    def TurnOnLaser(self):
        self.turnOnLaser = 1


    def TurnOffLaser(self):
        self.turnOffLaser = 1


    def SetBias(self):
        self.setBias = 1


    def DisableLoop(self):
        self.loopActive = False

 
    def EnableLoop(self):
        self.loopActive = True

    def SetWavelength(self, wavelength):
        self.newWavelength = wavelength
        self.setNewWavelength = 1


    def SetPower(self, power):
        self.newPower = power
        self.setNewPower = 1


    def L2RBypassCalibration(self):
        self.l2rBypassCalibration = 1
        

    def LeftOutputCalibration(self):
        self.leftOutputCalibration = 1
        

    def R2LBypassCalibration(self):
        self.r2lBypassCalibration = 1
        
    def NoCalibration(self):
        self.noCalibration = 1
        

    def RightOutputCalibration(self):
        self.rightOutputCalibration = 1
        

    def LeftLensedFiberCalibration(self):
        self.leftLensedFiberCalibration = 1
        

    def RightLensedFiberCalibration(self):
        self.rightLensedFiberCalibration = 1
        

    def TransmissionScan(self, userFilePath):
        self.userFilePath = userFilePath
        self.transmissionScan = 1

    def TransmissionBiasScan(self, userFilePath):
        self.userFilePath = userFilePath
        self.transmissionBiasScan = 1

    def SantecPowerScan(self, userFilePath):
        self.userFilePath = userFilePath
        self.santecPowerScan = 1
    
    def NaiveInitPowSweep(self, userFilePath):
        self.userFilePath = userFilePath
        self.naiveInitPowSweep = 1

    def SantecPowerSweep(self, userFilePath):
        self.userFilePath = userFilePath
        self.santecPowerSweep = 1
        
    def AttenPowerScan(self, userFilePath):
        self.userFilePath = userFilePath
        self.attenPowerScan = 1

    def PumpProbeScan(self, userFilePath):
        self.userFilePath = userFilePath
        self.pumpProbeScan = 1


    def WatchTransmissionFunction(self, userFilePath):
        self.userFilePath = userFilePath
        self.WatchTransmission = 1
        

    def TransmissionScanFast(self, userFilePath):
        self.userFilePath = userFilePath
        self.transmissionScanFast = 1


    def TransmissionScanTwoPort(self, userFilePath):
        self.userFilePath = userFilePath
        self.transmissionScanTwoPort = 1


    def TakeIV(self, userFilePath):
        self.userFilePath = userFilePath
        self.takeIV = 1

    def TakeIV2(self, userFilePath):
        self.userFilePath = userFilePath
        self.takeIV2 = 1

    def TakePI(self, userFilePath):
        self.userFilePath = userFilePath
        self.takePI = 1


    def TakeRLV(self, userFilePath):
        self.userFilePath = userFilePath
        self.takeRLV = 1

    def TakeRLP(self, userFilePath):
        self.userFilePath = userFilePath
        self.takeRLP = 1



##-----------------------------------------------------
## Experiment Menu Run Commands
##-----------------------------------------------------
 

    def PerformIVMeasurement(self, plot = True):
        #Beep when start
        frequency = 2200  # Set Frequency To 2500 Hertz
        duration = 500  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # IV curve at a specific power using the parameter analyzer
        
        startBias = self.parent.startMeasV
        stopBias = self.parent.stopMeasV
        numBias = self.parent.numMeasV

        measurements = zeros((numBias,2),float)
        # column 0 = wavelength, column 1 = transmission loss, column 2 = return loss

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "iv--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             startBias,
                                                                             numBias,
                                                                             stopBias,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath

        previousBias = self.parent.pdBias;

        self.SParamSetLongIntegrationTime()

        row = 0
        
        #biasSet = [-0.8, -0.7877551 , -0.7755102 , -0.76326531, -0.75102041, -0.73877551, -0.72653061, -0.71428571, -0.70204082, -0.68979592, -0.67755102, -0.66530612, -0.65306122, -0.64081633, -0.62857143, -0.61632653, -0.60408163, -0.59183673, -0.57959184, -0.56734694, -0.55510204, -0.54285714, -0.53061224, -0.51836735, -0.50612245, -0.49387755, -0.48163265, -0.46938776, -0.45714286, -0.44489796, -0.43265306, -0.42040816, -0.40816327, -0.39591837, -0.38367347, -0.37142857, -0.35918367, -0.34693878, -0.33469388, -0.32244898, -0.31020408, -0.29795918, -0.28571429, -0.27346939, -0.26122449, -0.24897959, -0.23673469, -0.2244898 , -0.2122449 , -0.2, -0.15, -1.00000000e-01, -5.00000000e-02, 0,  0.05,  0.1,  0.15, 0.2,  0.25,  0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
        #measurements = zeros((len(biasSet),2),float)
        
        for bias_current in linspace(startBias,stopBias,numBias):
        #for bias_current in biasSet:

            measurements[row,0] = bias_current

            self.SParamSetBias(bias_current)
            #self.KeithleySetBias(bias_current)
            dummy = self.SParamGetPhotocurrent()

            time.sleep(0.0001)

            current_meas = self.SParamGetPhotocurrent()
            #current_meas = self.KeithleyGetPhotocurrent()
            measurements[row,1] = current_meas

            print("Measured current for %.2fV = %.2e" % (bias_current, current_meas))

            row = row + 1

        #Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)
        
        # Save as .mat file
        io.savemat(outfilePath, {'iv': measurements})

        # Save a csv file
        filename = "%s.csv" % (measDescription)

        print(measurements.shape[0])
        outfilePath = os.path.join(saveDirectory,filename)
        # with open(outfilePath, 'w', newline='') as csvfile:
        with open(outfilePath, 'w') as csvfile: # new line not supported in python 2.7
            # csvwriter = csv.writer(csvfile, delimiter=' ',
            #                         quotechar=',', quoting=csv.QUOTE_MINIMAL)
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Voltage V', 'Current A'])

            for i in range(measurements.shape[0]):
                csvwriter.writerow([str(measurements[i,0]), str(measurements[i,1])])

        self.SParamSetShortIntegrationTime()

        self.SParamSetBias(previousBias)
        #self.KeithleySetBias(previousBias)
        
        if plot:
            plt.figure()
            plt.subplot(211)
            plt.plot(measurements[:,0], measurements[:,1])
            plt.subplot(212)
            plt.semilogy(measurements[:,0], np.abs(measurements[:,1]))
            # plt.ion()
            plt.show()
            
    def PerformIV2Measurement(self, plot = True):
        #Beep when start
        frequency = 2200  # Set Frequency To 2500 Hertz
        duration = 500  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        # IV curve at a specific power using the parameter analyzer
        
        startBias = self.parent.startMeasV
        stopBias = self.parent.stopMeasV
        numBias = self.parent.numMeasV

        measurements = zeros((numBias,2),float)
        light_measurements = zeros((numBias,2),float)
        # column 0 = wavelength, column 1 = transmission loss, column 2 = return loss

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "iv--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             startBias,
                                                                             numBias,
                                                                             stopBias,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath

        previousBias = self.parent.pdBias;

        self.SParamSetLongIntegrationTime()
        
        #biasSet = [-0.8, -0.7877551 , -0.7755102 , -0.76326531, -0.75102041, -0.73877551, -0.72653061, -0.71428571, -0.70204082, -0.68979592, -0.67755102, -0.66530612, -0.65306122, -0.64081633, -0.62857143, -0.61632653, -0.60408163, -0.59183673, -0.57959184, -0.56734694, -0.55510204, -0.54285714, -0.53061224, -0.51836735, -0.50612245, -0.49387755, -0.48163265, -0.46938776, -0.45714286, -0.44489796, -0.43265306, -0.42040816, -0.40816327, -0.39591837, -0.38367347, -0.37142857, -0.35918367, -0.34693878, -0.33469388, -0.32244898, -0.31020408, -0.29795918, -0.28571429, -0.27346939, -0.26122449, -0.24897959, -0.23673469, -0.2244898 , -0.2122449 , -0.2, -0.15, -1.00000000e-01, -5.00000000e-02, 0,  0.05,  0.1,  0.15, 0.2,  0.25,  0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
        #measurements = zeros((len(biasSet),2),float)

        self.LaserDrvOutput(0)
        time.sleep(3.0)
        # Dark current measurements
        row = 0
        for bias_current in linspace(startBias,stopBias,numBias):
        #for bias_current in biasSet:

            measurements[row,0] = bias_current

            self.SParamSetBias(bias_current)
            #self.KeithleySetBias(bias_current)
            dummy = self.SParamGetPhotocurrent()

            time.sleep(0.0001)

            current_meas = self.SParamGetPhotocurrent()
            #current_meas = self.KeithleyGetPhotocurrent()
            measurements[row,1] = current_meas

            print("Measured current for %.2fV = %.2e" % (bias_current, current_meas))

            row = row + 1

        # Light measurments
        print("Turning on laser for light measurements")

        self.LaserDrvOutput(1)
        time.sleep(3.0)

        row = 0
        for bias_current in linspace(startBias,stopBias,numBias):
        
            light_measurements[row,0] = bias_current

            self.SParamSetBias(bias_current)
            #self.KeithleySetBias(bias_current)
            dummy = self.SParamGetPhotocurrent()

            time.sleep(0.0001)

            current_meas = self.SParamGetPhotocurrent()
            #current_meas = self.KeithleyGetPhotocurrent()
            light_measurements[row,1] = current_meas

            print("Measured current for %.2fV = %.2e" % (bias_current, current_meas))

            row = row + 1
        self.LaserDrvOutput(0)

        #Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)
        
        # # Save as .mat file
        # io.savemat(outfilePath, {'iv': measurements})

        # Save a csv file
        filename = "%s-dark.csv" % (measDescription)

        outfilePath = os.path.join(saveDirectory,filename)
        # with open(outfilePath, 'w', newline='') as csvfile:
        with open(outfilePath, 'w') as csvfile: # new line not supported in python 2.7
            # csvwriter = csv.writer(csvfile, delimiter=' ',
            #                         quotechar=',', quoting=csv.QUOTE_MINIMAL)
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Voltage V', 'Current A'])

            for i in range(measurements.shape[0]):
                csvwriter.writerow([str(measurements[i,0]), str(measurements[i,1])])

        filename = "%s-light.csv" % (measDescription)

        outfilePath = os.path.join(saveDirectory,filename)
        # with open(outfilePath, 'w', newline='') as csvfile:
        with open(outfilePath, 'w') as csvfile: # new line not supported in python 2.7
            # csvwriter = csv.writer(csvfile, delimiter=' ',
            #                         quotechar=',', quoting=csv.QUOTE_MINIMAL)
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Voltage V', 'Current A'])

            for i in range(measurements.shape[0]):
                csvwriter.writerow([str(light_measurements[i,0]), str(light_measurements[i,1])])
        self.SParamSetShortIntegrationTime()

        self.SParamSetBias(previousBias)
        
        #self.KeithleySetBias(previousBias)
        
        if plot:
            plt.figure()
            plt.subplot(211)
            plt.plot(measurements[:,0], measurements[:,1], light_measurements[:,0], light_measurements[:,1])
            plt.legend(['Dark', 'Light'])
            plt.subplot(212)
            plt.semilogy(measurements[:,0], np.abs(measurements[:,1]), light_measurements[:,0], np.abs(light_measurements[:,1]))
            plt.legend(['Dark', 'Light'])
            # plt.ion()
            plt.show()

    def PerformPIMeasurement(self):
        
        # Measures I as a function of laser power for a specific voltage
        
        startpower = self.parent.startMeasPower;
        endpower = self.parent.stopMeasPower;
        numpower = self.parent.numMeasPower;

        measurements = zeros((numpower,2),float)
            # column 0 = power, column 1 = current

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "pi--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             startpower,
                                                                             numpower,
                                                                             endpower,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
                
        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            previousPower = self.parent.power
            wasOff = False

        row = 0
        
        for Pset in linspace(startpower,endpower,numpower):
            self.LaserSetOutputPower(Pset)
            measurements[row,0] = Pset
            time.sleep(0.3)
            current_meas = self.SParamGetPhotocurrent()
            measurements[row,1] = current_meas
            print("Measured current for %.2fV = %.2e" % (Pset, current_meas))
            row = row + 1
        io.savemat(outfilePath, {'pimeas': measurements})
        self.SParamSetShortIntegrationTime()

        if not wasOff:
            self.LaserTurnOn()
            self.LaserSetOutputPower(previousPower)


##    def PerformRLVMeasurement(self):
##
##
##        power = 10.0
##        num_power = 1
##
##        saveDirectory = os.path.dirname(self.userFilePath)
##        measDescription = os.path.basename(self.userFilePath)
##
##        rlvStartLambda = self.parent.startMeasWavelength 
##        rlvNumLambda = self.parent.numMeasWavelength
##        rlvStopLambda = self.parent.stopMeasWavelength
##
##        self.SParamSetLongIntegrationTime()
##        
##        measurements = zeros((rlvNumLambda,5),float)
##
##        
##        timeTuple = time.localtime()
##        filename = "rlv--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
##                                                                             rlvStartLambda,
##                                                                             rlvNumLambda,
##                                                                             rlvStopLambda,
##                                                                             timeTuple[0],
##                                                                             timeTuple[1],
##                                                                             timeTuple[2],
##                                                                             timeTuple[3],
##                                                                             timeTuple[4],
##                                                                             timeTuple[5])
##
##        outfilePath = os.path.join(saveDirectory,filename)
##        print "Saving data to ", outfilePath
##                
##        previousBias = self.parent.pdBias
##
##        if self.newWavelength > 0:
##            previousWavelength = self.newWavelength
##        else:
##            previousWavelength = 1260.00
##
##        if self.newPower > 0:
##            previousPower = self.parent.power
##        else:
##            previousPower = 10.00
##
##        if self.activeModule == -1:
##            self.LaserTurnOn()
##            wasOff = True
##        else:
##            wasOff = False
##
##        self.LaserSetOutputPower(power)
##
##        row = 0
##        for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
##
##            print("Setting the wavelength to %.1f nm" % self.newWavelength)
##
##            self.LaserSetWavelength()
##            self.LWMainSetWavelength()
##
##            time.sleep(0.1)
##
##            measurements[row,1] = self.parent.pdBias
##
##            trans, wave, out, rec = self.LWMainGetTransmissions()
##
##            measurements[row,0] = wave
##
##            print("Measured power = %.2e W" % out)
##            measurements[row,2] = out 
##
##            print("Measured transmission = %.2f dB" % trans)
##            measurements[row,3] = trans
##
##            dummy = self.SParamGetPhotocurrent()
##
##            time.sleep(0.01)
##            current_meas = self.SParamGetPhotocurrent()
##
##            measurements[row,4] = current_meas
##
##            print("Measured current = %.2e A" % current_meas)
##
##            coarse_responsivity = current_meas / (out + 1e-15)
##
##            print("Coarse responsivity = %.3f A/W" % coarse_responsivity)
##
##            row = row + 1
##
##        io.savemat(outfilePath, {'rlv': measurements})
##
##        self.SParamSetShortIntegrationTime()
##
##        if wasOff:
##            self.LaserTurnOff()
##        else:
##            self.LaserSetOutputPower(previousPower)
##            self.SetWavelength(previousWavelength)

    def PerformRLVMeasurement(self):

        startBias = self.parent.startMeasV
        stopBias = self.parent.stopMeasV
        numBias = self.parent.numMeasV

        self.SParamSetLongIntegrationTime()
        #Enter power here
        #powerSweepFixOutput = [0.125,0.125,0.125,0.125,0.125,0.125,0.125,0.125,0.125,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.127,0.127,0.127,0.127,0.127,0.127,0.127,0.127,0.127,0.127,0.127,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.126,0.125,0.125,0.125,0.125,0.125,0.125,0.125,0.124,0.124,0.124,0.124,0.124,0.123,0.123,0.123,0.123,0.122,0.122,0.122,0.122,0.121,0.121,0.121,0.120,0.120,0.120,0.120,0.119,0.119,0.119,0.118,0.118,0.118,0.118,0.117,0.117,0.117,0.116,0.116,0.116,0.115,0.115,0.115,0.115,0.114,0.114,0.114,0.113,0.113,0.113,0.113,0.112,0.112,0.112,0.112,0.112,0.111,0.111,0.111,0.111,0.111,0.111,0.111,0.111,0.111,0.111,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.110,0.109,0.109,0.109,0.109,0.109,0.108,0.108,0.108,0.108,0.107,0.107,0.107,0.107,0.106,0.106,0.106,0.105,0.105,0.104,0.104,0.104,0.103,0.103,0.103,0.102,0.102,0.102,0.101,0.101,0.101,0.100,0.100,0.100,0.100,0.099,0.099,0.099,0.099,0.098,0.098,0.098,0.098,0.098,0.097,0.097,0.097,0.097,0.097,0.097,0.096,0.096,0.096,0.096,0.096,0.096,0.095,0.095,0.095,0.095,0.095,0.095,0.094,0.094,0.094,0.094,0.094,0.094,0.093,0.093,0.093,0.093,0.093,0.092,0.092,0.092,0.092,0.092,0.092,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.088,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.089,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.090,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.091,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.092,0.093,0.093,0.093,0.093,0.093,0.093,0.094,0.094,0.094,0.094,0.094,0.095,0.095,0.095,0.095,0.096,0.096,0.096,0.096,0.096,0.097,0.097,0.097,0.097,0.097,0.098,0.098,0.098,0.098,0.098,0.099,0.099,0.099,0.099,0.099,0.100,0.100,0.100,0.100,0.100,0.101,0.101,0.101,0.101,0.102,0.102,0.102,0.102,0.103,0.103,0.103,0.104,0.104,0.104,0.105,0.105,0.105,0.106,0.106,0.106,0.107,0.107,0.108,0.108,0.109,0.109,0.110,0.110,0.111,0.111,0.111,0.112,0.112,0.113,0.113,0.114,0.114,0.114,0.115,0.115,0.115,0.116,0.116,0.117,0.117,0.117,0.118,0.118,0.119,0.119,0.120,0.120,0.121,0.121,0.122,0.122,0.123,0.123,0.124,0.124,0.125,0.125,0.126,0.126,0.127,0.127,0.128,0.128,0.128,0.129,0.129,0.129,0.130,0.130,0.130,0.130,0.131,0.131,0.131,0.132,0.132,0.132,0.133,0.133,0.133,0.134,0.134,0.135,0.135,0.136,0.136,0.136,0.137,0.137,0.138,0.138,0.139,0.139,0.140,0.141,0.141,0.142,0.142,0.143,0.143,0.144,0.144,0.145,0.145,0.146,0.146,0.146,0.147,0.147,0.148,0.148,0.148,0.149,0.149,0.150,0.150,0.150,0.151,0.151,0.151,0.151,0.152,0.152,0.152,0.153,0.153,0.153,0.153,0.154,0.154,0.154,0.155,0.155,0.155,0.155,0.156,0.156,0.156,0.156,0.157,0.157,0.157,0.157,0.158,0.158,0.158,0.158,0.159,0.159,0.159,0.159,0.160,0.160,0.160,0.160,0.161,0.161,0.161,0.161,0.162,0.162,0.162,0.162,0.163,0.163,0.163,0.163,0.163,0.164,0.164,0.164,0.164,0.164,0.165,0.165,0.165,0.165,0.166,0.166,0.166,0.166,0.166,0.167,0.167,0.167,0.167,0.168,0.168,0.168,0.169,0.169,0.169,0.170,0.170,0.170,0.171,0.171,0.171,0.172,0.172,0.173,0.173,0.174,0.174,0.174,0.175,0.175,0.176,0.176,0.177,0.178,0.178,0.179,0.179,0.180,0.180,0.181,0.181,0.182,0.182,0.183,0.183,0.184,0.184,0.185,0.185,0.186,0.186,0.187,0.187,0.188,0.188,0.189,0.189,0.189,0.190,0.190,0.191,0.191,0.192,0.192,0.192,0.193,0.193,0.193,0.194,0.194,0.194,0.195,0.195,0.195,0.195,0.196,0.196,0.196,0.197,0.197,0.197,0.197,0.198,0.198,0.198,0.199,0.199,0.199,0.199,0.200,0.200,0.200,0.201,0.201,0.201,0.202,0.202,0.202,0.203,0.203,0.203,0.204,0.204,0.204,0.205,0.205,0.206,0.206,0.206,0.207,0.207,0.207,0.208,0.208,0.208,0.209,0.209,0.209,0.210,0.210,0.210,0.211,0.211,0.211,0.212,0.212,0.213,0.213,0.213,0.214,0.214,0.215,0.215,0.216,0.216,0.217,0.217,0.218,0.218,0.219,0.219,0.220,0.220,0.221,0.222,0.222,0.223,0.224,0.224,0.225,0.226,0.226,0.227,0.228,0.229,0.230,0.231,0.231,0.232,0.233,0.234,0.235,0.237,0.238,0.239,0.240,0.241,0.243,0.244,0.246,0.247,0.249,0.250,0.252,0.253,0.255,0.257,0.258,0.260,0.262,0.263,0.265,0.267,0.268,0.270,0.271,0.273,0.274,0.276,0.277,0.278,0.279,0.281,0.282,0.282,0.283,0.284,0.285,0.285,0.285,0.286,0.286,0.286,0.285,0.285,0.285,0.284,0.283,0.282,0.281,0.279,0.278,0.276,0.274,0.272]
        #powerSweepFixOutput = [0.996,0.995,0.994,0.994,0.993,0.993,0.993,0.992,0.992,0.993,0.993,0.993,0.993,0.994,0.994,0.995,0.995,0.996,0.996,0.997,0.998,0.998,0.999,0.999,0.999,1.000,1.000,1.000,1.000,1.000,1.000,0.999,0.999,0.998,0.997,0.996,0.995,0.994,0.992,0.990,0.988,0.986,0.983,0.980,0.977,0.974,0.970,0.966,0.961,0.957,0.952,0.947,0.941,0.936,0.931,0.927,0.922,0.918,0.914,0.911,0.907,0.904,0.900,0.897,0.894,0.890,0.886,0.883,0.879,0.875,0.871,0.867,0.863,0.859,0.855,0.852,0.848,0.845,0.843,0.840,0.838,0.836,0.834,0.833,0.831,0.830,0.829,0.828,0.828,0.827,0.826,0.826,0.825,0.825,0.824,0.824,0.823,0.823,0.823,0.823,0.822,0.822,0.822,0.821,0.821,0.820,0.820,0.820,0.819,0.819,0.818,0.818,0.818,0.817,0.817,0.817,0.817,0.817,0.817,0.818,0.818,0.818,0.819,0.820,0.821,0.822,0.823,0.824,0.825,0.826,0.827,0.828,0.829,0.830,0.831,0.832,0.832,0.833,0.833,0.833,0.834,0.834,0.834,0.835,0.835,0.836,0.837,0.838,0.839,0.840,0.841,0.843,0.845,0.846,0.848,0.849,0.851,0.852,0.853,0.853,0.854,0.854,0.854,0.854,0.855,0.855,0.855,0.855,0.855,0.856,0.856,0.857,0.858,0.858,0.859,0.860,0.860,0.861,0.862,0.863,0.864,0.864,0.865,0.866,0.867,0.868,0.868,0.869,0.870,0.871,0.871,0.872,0.872,0.873,0.874,0.874,0.875,0.875,0.876,0.876,0.877,0.877,0.878,0.878,0.878,0.879,0.879,0.879,0.880,0.880,0.881,0.881,0.881,0.882,0.882,0.882,0.883,0.883,0.883,0.884,0.884,0.883,0.883,0.882,0.881,0.880,0.879,0.877,0.875,0.872,0.869,0.866,0.862,0.858,0.853,0.847,0.842,0.836,0.831,0.825,0.820,0.815,0.810,0.805,0.801,0.797,0.793,0.790,0.786,0.783,0.779,0.776,0.772,0.769,0.765,0.762,0.758,0.755,0.751,0.747,0.743,0.738,0.734,0.730,0.726,0.721,0.717,0.712,0.708,0.704,0.699,0.695,0.691,0.687,0.683,0.678,0.674,0.670,0.665,0.660,0.655,0.650,0.644,0.638,0.632,0.626,0.620,0.614,0.608,0.603,0.598,0.593,0.589,0.586,0.583,0.580,0.578,0.576,0.573,0.571,0.569,0.567,0.564,0.561,0.558,0.555,0.551,0.548,0.544,0.540,0.536,0.532,0.528,0.524,0.521,0.518,0.515,0.512,0.509,0.507,0.505,0.502,0.500,0.498,0.496,0.494,0.492,0.489,0.487,0.484,0.481,0.478,0.475,0.472,0.469,0.465,0.462,0.459,0.456,0.453,0.450,0.447,0.444,0.442,0.439,0.437,0.434,0.432,0.430,0.427,0.425,0.423,0.421,0.420,0.418,0.416,0.414,0.413,0.411,0.410,0.408,0.407,0.405,0.404,0.402,0.401,0.399,0.398,0.396,0.395,0.393,0.392,0.390,0.388,0.387,0.386,0.384,0.383,0.382,0.381,0.380,0.379,0.379,0.378,0.378,0.377,0.377,0.377,0.377,0.377,0.377,0.376,0.376,0.376,0.376,0.375,0.375,0.375,0.374,0.374,0.373,0.373,0.372,0.372,0.371,0.371,0.370,0.370,0.370,0.369,0.369,0.369,0.369,0.368,0.368,0.368,0.367,0.367,0.367,0.366,0.366,0.365,0.364,0.364,0.363,0.363,0.362,0.361,0.361,0.361,0.360,0.360,0.360,0.359,0.359,0.359,0.359,0.359,0.360,0.360,0.360,0.360,0.360,0.360,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.361,0.360,0.360,0.360,0.360,0.360,0.359,0.359,0.359,0.359,0.358,0.358,0.358,0.358,0.357,0.357,0.357,0.356,0.356,0.356,0.356,0.355,0.355,0.355,0.354,0.354,0.354,0.354,0.353,0.353,0.353,0.353,0.353,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.352,0.351,0.351,0.350,0.350,0.349,0.349,0.348,0.347,0.346,0.345,0.344,0.343,0.341,0.340,0.339,0.337,0.335,0.334,0.332,0.330,0.329,0.327,0.325,0.324,0.322,0.321,0.319,0.317,0.316,0.314,0.313,0.311,0.310,0.309,0.307,0.306,0.305,0.303,0.302,0.300,0.299,0.297,0.296,0.294,0.292,0.291,0.289,0.287,0.285,0.283,0.282,0.280,0.278,0.276,0.275,0.273,0.272,0.270,0.269,0.268,0.266,0.265,0.264,0.263,0.262,0.260,0.259,0.258,0.256,0.255,0.253,0.251,0.249,0.247,0.245,0.243,0.240,0.238,0.236,0.234,0.231,0.229,0.227,0.225,0.224,0.222,0.221,0.219,0.218,0.217,0.216,0.215,0.213,0.212,0.211,0.210,0.209,0.208,0.207,0.206,0.205,0.203,0.202,0.201,0.199,0.198,0.197,0.195,0.194,0.192,0.191,0.190,0.188,0.187,0.185,0.184,0.183,0.182,0.180,0.179,0.178,0.177,0.176,0.175,0.174,0.173,0.172,0.171,0.170,0.170,0.169,0.168,0.168,0.167,0.166,0.166,0.165,0.164,0.164,0.163,0.162,0.161,0.160,0.159,0.158,0.157,0.156,0.155,0.154,0.153,0.152,0.151,0.149,0.148,0.148,0.147,0.146,0.145,0.145,0.144,0.144,0.143,0.143,0.143,0.142,0.142,0.142,0.142,0.142,0.142,0.142,0.142,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.141,0.142,0.142,0.142,0.142,0.143,0.143,0.143,0.144,0.144,0.145,0.145,0.145,0.146,0.146,0.147,0.147,0.147,0.148,0.148,0.149,0.149,0.150,0.150,0.150,0.151,0.151,0.152,0.152,0.153,0.153,0.154,0.154,0.155,0.155,0.156,0.156,0.157,0.157,0.157,0.158,0.158,0.158,0.159,0.159,0.159,0.159,0.159,0.160,0.160,0.160,0.160,0.160,0.161,0.161,0.161,0.161,0.161,0.162,0.162,0.162,0.162,0.163,0.163,0.163,0.164,0.164,0.164,0.164,0.165,0.165,0.165,0.166,0.166,0.166,0.167,0.167,0.167,0.168,0.168,0.168,0.169,0.169,0.170,0.170,0.170,0.171,0.171,0.171,0.172,0.172,0.173,0.173,0.173,0.174,0.174]
        #AA
        
        biasSet = linspace(startBias,stopBias,numBias)
                   
        num_bias = len(biasSet)

        num_power = 1

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        rlvStartLambda = self.parent.startMeasWavelength 
        rlvNumLambda = self.parent.numMeasWavelength
        rlvStopLambda = self.parent.stopMeasWavelength

        ## self.SParamSetMedIntegrationTime()
        
        measurements = zeros((rlvNumLambda,num_bias*(num_power*6)+1),float)

        timeTuple = time.localtime()
        filename = "rlv--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             rlvStartLambda,
                                                                             rlvNumLambda,
                                                                             rlvStopLambda,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
                
        previousBias = self.parent.pdBias

        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.newPower > 0:
            previousPower = self.parent.power
        else:
            previousPower = 4.00

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

##        self.LaserSetOutputPower(power)

        bias_index=0
        
        for bias in biasSet:
            self.SParamSetBias(bias)
            ## self.KeithleySetBias(bias)

            print("Setting the bias to %.1f V" % bias)

            time.sleep(0.2)

            row = 0
            for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
                measurements[row,0] = self.newWavelength
                print("Setting the wavelength to %.1f nm" % self.newWavelength)
                self.LaserSetWavelength()
                self.LWMainSetWavelength()
                #changing power here
                #powerAdjusted=powerSweepFixOutput[row]
                #self.LaserSetOutputPower(powerAdjusted)
                #AA
                time.sleep(.5)
                wave_counter = 0
                wave_average = 0.0              

                power_index = 0
                measurements[row,bias_index*(num_power*6)+power_index*4+1] = bias 

                #trans, wave, out, rec = self.LWMainGetTransmissions()
                trans, wave, out, rec, power_tap = self.LWMainGetTransmissions()
                #AA

                if ((wave > 1000) and (wave < 2000)):
                    wave_average = wave_average+wave
                    wave_counter = wave_counter + 1

                print("Measured power = %.2e C:\Users\Admin\Downloads" % out)
                measurements[row,bias_index*(num_power*6)+power_index*4+2] = out 

                print("Measured transmission = %.2f dB" % trans)
                measurements[row,bias_index*(num_power*6)+power_index*4+3] = trans

                print("Measured wavelength = %.2f nm" % wave)
                measurements[row,bias_index*(num_power*6)+power_index*4+4] = wave
                #AA
                print("Tap power = %.2e W" % power_tap) 
                measurements[row,bias_index*(num_power*6)+power_index*4+5] = power_tap  



                dummy = self.SParamGetPhotocurrent()
                ## dummy = self.KeithleyGetPhotocurrent()

                time.sleep(0.1)
                current_meas = self.SParamGetPhotocurrent()
                ## current_meas = self.KeithleyGetPhotocurrent()

                measurements[row,bias_index*(num_power*6)+power_index*4+6] = current_meas ##AA

                print("Measured current = %.2e A" % current_meas)

                coarse_responsivity = current_meas / (out + 1e-15)

                print("Coarse responsivity = %.3f A/W" % coarse_responsivity)
                row=row+1
                

             
            #print("Meas Wavelength = %.3f nm" % wave_average/wave_counter)
            bias_index = bias_index + 1
            
        #Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        io.savemat(outfilePath, {'rlv': measurements})

        self.SParamSetShortIntegrationTime()

        self.SParamSetBias(previousBias)
        ## self.KeithleySetBias(0)

        if wasOff:
            self.LaserTurnOff()
        else:
            self.LaserSetOutputPower(previousPower)
            self.SetWavelength(previousWavelength)

    def PerformRLPMeasurement(self):

        startV = self.parent.startMeasV
        stopV = self.parent.stopMeasV
        numV = self.parent.numMeasV

        Voltages = linspace(startV,stopV,numV)

        for Vset in Voltages:
            self.KeithleySetBias(Vset)

            startpower = self.parent.startMeasPower
            endpower = self.parent.stopMeasPower
            numpower = self.parent.numMeasPower

            #powset1 = linspace(math.log(startpower,10),math.log(endpower,10),numpower)
            #powset = zeros((numpower,1),float)
            #powind = 0

            #for logpow in powset1:
            #    powset[powind,0] = math.pow(10,logpow)
            #    powind = powind+1

            powset = linspace(startpower,endpower,numpower)
            
            num_power = len(powset)

            saveDirectory = os.path.dirname(self.userFilePath)
            measDescription = os.path.basename(self.userFilePath)

            rlvStartLambda = self.parent.startMeasWavelength 
            rlvNumLambda = self.parent.numMeasWavelength
            rlvStopLambda = self.parent.stopMeasWavelength

            self.SParamSetMedIntegrationTime()
            
            measurements = zeros((rlvNumLambda,(num_power*5)+1),float)

            timeTuple = time.localtime()
            filename = "rlp--%s-%d-mV-%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                                 1000*Vset,
                                                                                 rlvStartLambda,
                                                                                 rlvNumLambda,
                                                                                 rlvStopLambda,
                                                                                 timeTuple[0],
                                                                                 timeTuple[1],
                                                                                 timeTuple[2],
                                                                                 timeTuple[3],
                                                                                 timeTuple[4],
                                                                                 timeTuple[5])

            outfilePath = os.path.join(saveDirectory,filename)
            print "Saving data to ", outfilePath
                    
            previousBias = self.parent.pdBias

            if self.newWavelength > 0:
                previousWavelength = self.newWavelength
            else:
                previousWavelength = 1260.00

            if self.newPower > 0:
                previousPower = self.parent.power
            else:
                previousPower = 4.00

            if self.activeModule == -1:
                self.LaserTurnOn()
                wasOff = True
            else:
                wasOff = False

    ##        self.LaserSetOutputPower(power)

            power_index = 0

            for power in powset:
                row = 0
                self.LaserSetOutputPower(power)
                print("Setting the laser power to %.3f mW" % power)
                time.sleep(0.1)
                measurements[row,power_index*5+1] = power ##AA
                
                wave_counter = 0
                wave_average = 0.0

                pastpeak=0

                for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
                    maxcur=0.0
                    if(not(pastpeak)):
                        print("Setting the wavelength to %.1f nm" % self.newWavelength)
        
                        self.LaserSetWavelength()
                        self.LWMainSetWavelength()
                        measurements[row,0] = self.newWavelength
       
                        time.sleep(.5)

                        ##trans, wave, out, rec = self.LWMainGetTransmissions()
                        trans, wave, out, rec, power_tap = self.LWMainGetTransmissions()
                       ##AA
                        if ((wave > 1000) and (wave < 2000)):
                            wave_average = wave_average+wave
                            wave_counter = wave_counter + 1

                        print("Measured power = %.2e W" % out)
                        measurements[row,power_index*5+2] = out 

                        print("Measured wavelength = %.4f nm" % wave)
                        measurements[row,power_index*5+3] = wave
                        ##AA
                        ##print("Tap power = %.2e W" % power_tap) 
                        ##measurements[row,power_index*5+4] = power_tap

                        dummy = self.KeithleyGetPhotocurrent()

                        time.sleep(0.1)
                        current_meas = self.KeithleyGetPhotocurrent()

                        if(abs(current_meas)>maxcur):
                            maxcur = abs(current_meas)
                        
                        measurements[row,power_index*5+5] = current_meas
                        print("Measured current = %.2e A" % current_meas)
                        coarse_responsivity = current_meas / (out + 1e-15)
                        print("Coarse responsivity = %.3f A/W" % coarse_responsivity)
                        if ( row > 5 ):
                            current_meas = abs(current_meas)
                            prev_meas=abs(measurements[row-1, power_index*4+4])
                            prev2_meas=abs(measurements[row-2, power_index*4+4])
                            prev3_meas=abs(measurements[row-3, power_index*4+4])
                            #if ( (prev_meas>current_meas) and (prev2_meas>prev_meas) and (prev3_meas>prev2_meas) and (abs(current_meas)<0.5*maxcur)):
                            if (abs(current_meas)<0.65*maxcur):
                               pastpeak=1
                        row = row + 1
                    else:
                        measurements[row,0] = self.newWavelength
                        row = row + 1

                power_index = power_index + 1

            io.savemat(outfilePath, {'rlp': measurements})



        #self.SParamSetShortIntegrationTime()

        if wasOff:
            self.LaserTurnOff()
        else:
            self.LaserSetOutputPower(previousPower)
            self.SetWavelength(previousWavelength)

        self.KeithleySetBias(0)
        self.LaserTurnOff()


    def PerformScatteringMeasurement(self, plot = True):
        
        # Wavelength sweep with the set power and bias
        
        measurements = zeros((self.parent.numMeasWavelength,5),float)

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "scattering--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             self.parent.startMeasWavelength,
                                                                             self.parent.numMeasWavelength,
                                                                             self.parent.stopMeasWavelength,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
                
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        #if self.newPower > 0:
        #    previousPower = self.parent.power
        #else:
        #    previousPower = 1.00
        #
        #laserPower = 10.00 # mW

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        #self.LaserSetOutputPower(laserPower)
        #self.LWMainInitializeSensors(averagingTime=0.10)

        row = 0

        for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):

            self.LaserSetWavelength()
            self.LWMainSetWavelength()
            time.sleep(1)

            trans, meas_wavelength, out, rec, power_tap = self.LWMainGetTransmissions()
            
            # [lambda, transmission, input power, lambda, received power]
            measurements[row,1] = trans
            measurements[row,2] = out
            measurements[row,3] = self.newWavelength
            measurements[row,4] = rec

            measurements[row,0] = meas_wavelength

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Meas Wavelength = %.5f" % meas_wavelength)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)

            row = row + 1

        io.savemat(outfilePath, {'scattering': measurements})
        
        #Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)
        
        self.SetWavelength(previousWavelength)
        #self.LWMainInitializeSensors()

        if wasOff:
            self.LaserTurnOff()
        #else:
        #    self.LaserSetOutputPower(previousPower)
        
        if (plot):
            plt.plot(measurements[:,3], measurements[:,1])
            plt.ion()
            plt.show()


    def PerformTransmissionBiasMeasurement(self, plot = True):
        
        #command to set parameter analyzer voltage:             self.SParamSetBias(bias_voltage)

        previousBias = self.parent.pdBias;

        
        startvoltage = self.parent.startMeasV;
        endvoltage = self.parent.stopMeasV;
        numvoltage = self.parent.numMeasV;
        
        if (plot):
            plt.clf()
        
        for Vset in linspace(startvoltage,endvoltage,numvoltage):
            print Vset
            self.SParamSetBias(Vset)
            measurements = zeros((self.parent.numMeasWavelength,6),float)

            saveDirectory = os.path.dirname(self.userFilePath)
            measDescription = os.path.basename(self.userFilePath)
            

            timeTuple = time.localtime()
            filename = "TvsV--%s-%d%s-%dnm-%dnm-%dnm--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                                 1000*Vset,
                                                                                 "mV",
                                                                                 self.parent.startMeasWavelength,
                                                                                 self.parent.numMeasWavelength,
                                                                                 self.parent.stopMeasWavelength,
                                                                                 timeTuple[0],
                                                                                 timeTuple[1],
                                                                                 timeTuple[2],
                                                                                 timeTuple[3],
                                                                                 timeTuple[4],
                                                                                 timeTuple[5])

            outfilePath = os.path.join(saveDirectory,filename)
            print "Saving data to ", outfilePath
                    
            if self.newWavelength > 0:
                previousWavelength = self.newWavelength
            else:
                previousWavelength = 1260.00

            #if self.newPower > 0:
            #    previousPower = self.parent.power
            #else:
            #    previousPower = 1.00
            #
            #laserPower = 10.00 # mW

            if self.activeModule == -1:
                self.LaserTurnOn()
                wasOff = True
            else:
                wasOff = False

            #self.LWMainInitializeSensors(averagingTime=0.10)

            row = 0
            for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):

                self.LaserSetWavelength()
                self.LWMainSetWavelength()


                if self.parent.direction == "RIGHT_TO_LEFT":
                    power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
                else:
                    power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

                power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
                try:
                    power_tap_initial = max(0.0,float(power_tap_initial_string))
                except ValueError:
                    power_tap_initial = 0.0
                
                IPpower = power_tap_initial/self.throughCalibrationFactor
                #CHECK THAT THIS IS WHAT I THINK IT IS
                trans, meas_wavelength, out, rec, tap_power = self.LWMainGetTransmissions()
                
                # [lambda, transmission, input_power, lambda, received power, power in 10% tap]
                measurements[row,1] = trans
                measurements[row,2] = out
                measurements[row,3] = self.newWavelength
                measurements[row,4] = rec
                measurements[row,5] = power_tap_initial
                measurements[row,0] = meas_wavelength

                print("Set Wavelength = %.3f" % self.newWavelength)
                print("Meas Wavelength = %.5f" % meas_wavelength)
                print("Rec Power = %.3e" % rec)
                print("Transmission Loss = %.2f" % trans)
                io.savemat(outfilePath, {'scattering': measurements})

                row = row + 1
                
            if plot:
                plt.plot(measurements[:,3], measurements[:,1])
                
        self.SetWavelength(previousWavelength)
            
        #self.LWMainInitializeSensors()

        if wasOff:
            self.LaserTurnOff()
            
        if (plot):
            plt.ion()
            plt.show()
            
        #else:
        #    self.LaserSetOutputPower(previousPower)


    def PerformSantecPowerScan(self, plot = True):
        # No wavelength sweep here
        # to set laser power    self.LaserSetOutputPower(self.newPower)
        startpower = self.parent.startMeasPower;
        endpower = self.parent.stopMeasPower;
        numpower = self.parent.numMeasPower;
        row = 0;
        
        measurements = zeros((numpower,6),float)
        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)
        
        timeTuple = time.localtime()
        filename = "T-%s.mat" % (    measDescription)
        
        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
        
        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False
            
        for Pset in linspace(startpower,endpower,numpower):

            self.LaserSetOutputPower(Pset)
            #self.LWMainInitializeSensors(averagingTime=0.10)

            if self.parent.direction == "RIGHT_TO_LEFT":
                power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            else:
                power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

            power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
            try:
                power_tap_initial = max(0.0,float(power_tap_initial_string))
            except ValueError:
                power_tap_initial = 0.0
            
            trans, meas_wavelength, out, rec, tap_power = self.LWMainGetTransmissions() #Ebrahim
            
            # [lambda, transmission, tap_power, input power in waveguide, received power, laser output power]
            measurements[row,1] = trans
            measurements[row,2] = power_tap_initial
            measurements[row,3] = out
            measurements[row,4] = rec
            measurements[row,5] = Pset
            measurements[row,0] = self.newWavelength

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Meas Wavelength = %.5f" % meas_wavelength)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)
            
            io.savemat(outfilePath, {'scattering': measurements})

            row = row + 1

        if wasOff:
            self.LaserTurnOff()
        #else:
        #    self.LaserSetOutputPower(previousPower)

    def PerformSantecPowerSweep(self, plot = True):
        # to set laser power    self.LaserSetOutputPower(self.newPower)
        
        startpower = self.parent.startMeasPower;
        endpower = self.parent.stopMeasPower;
        numpower = self.parent.numMeasPower;
        
        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        lamstart = self.parent.startMeasWavelength;
        lamend = self.parent.stopMeasWavelength;
        numlam = self.parent.numMeasWavelength;
        
        if (plot):
            plt.clf()
            
        for Pset in linspace(startpower,endpower,numpower):
            measurements = zeros((numlam,6),float)

            filename = "TvsP-%s-%duW-%dnm-%dnm-%dnm.mat" % (measDescription, 1000*Pset,  self.parent.startMeasWavelength,
                                                                             self.parent.numMeasWavelength,
                                                                             self.parent.stopMeasWavelength
                                                )
            outfilePath = os.path.join(saveDirectory,filename)
            print "Saving data to ", outfilePath

            lrow=0
            self.LaserSetOutputPower(Pset)
            #self.LWMainInitializeSensors(averagingTime=0.10)

            if self.parent.direction == "RIGHT_TO_LEFT":
                power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            else:
                power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

            power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
            try:
                power_tap_initial = max(0.0,float(power_tap_initial_string))
            except ValueError:
                power_tap_initial = 0.0
            
            IPpower = power_tap_initial/self.throughCalibrationFactor

  #          for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
            for self.newWavelength in linspace(lamstart,lamend,numlam):

                self.LaserSetWavelength()
                self.LWMainSetWavelength()
                #self.SetILXWavelength()
                                
                if self.parent.direction == "RIGHT_TO_LEFT":
                    power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
                else:
                    power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

                power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
                try:
                    power_tap_initial = max(0.0,float(power_tap_initial_string))
                except ValueError:
                    power_tap_initial = 0.0;
                
                IPpower = power_tap_initial/self.throughCalibrationFactor
                trans, meas_wavelength, out, rec, power_tap = self.LWMainGetTransmissions()
                
                time.sleep(0.01)
                #ILXPower = float(self.GetILXPower())
                
                # [lambda, transmission, input power in waveguide, lambda, tap_power]
                measurements[lrow,0] = meas_wavelength
                measurements[lrow,1] = trans
                measurements[lrow,2] = IPpower
                measurements[lrow,3] = self.newWavelength
                measurements[lrow,4] = power_tap_initial
                #measurements[lrow,5] = ILXPower

                print("Set Wavelength = %.3f" % self.newWavelength)
                print("Set Power = %.3f" % Pset)

                print("Meas Wavelength = %.5f" % meas_wavelength)
                print("Rec Power = %.3e" % rec)
                print("Transmission Loss = %.2f" % trans)
                # print("Optometer Power = %.3e" % ILXPower)
                io.savemat(outfilePath, {'scattering': measurements})

                lrow = lrow + 1
                ##End lambda loop
            
            if (plot):
                plt.plot(measurements[:,3], measurements[:,1])
            ##End power loop
            

        self.LaserTurnOff()
        
        if (plot):
            plt.ion()
            plt.show()
        #else:
        #    self.LaserSetOutputPower(previousPower)


    def PerformAttenPowerScan(self):
        # to set laser power    self.LaserSetOutputPower(self.newPower)
        previousBias = self.parent.pdBias;

        startvoltage = self.parent.startV;
        endvoltage = self.parent.stopV;
        numvoltage = self.parent.numV;

        row = 0;
        
        measurements = zeros((numvoltage,6),float)
        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)
        
        timeTuple = time.localtime()
        filename = "scattering--%s--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath

        #if self.newPower > 0:
        #    previousPower = self.parent.power
        #else:
        #    previousPower = 1.00
        #
        #laserPower = 10.00 # mW

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        for Vset in linspace(startvoltage,endvoltage,numvoltage):

            #self.LWMainInitializeSensors(averagingTime=0.10)

            if self.parent.direction == "RIGHT_TO_LEFT":
                power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            else:
                power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

            power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
            try:
                power_tap_initial = max(0.0,float(power_tap_initial_string))
            except ValueError:
                power_tap_initial = 0.0
            
            IPpower = power_tap_initial/self.throughCalibrationFactor
            #CHECK THAT THIS IS WHAT I THINK IT IS
            trans, meas_wavelength, out, rec = self.LWMainGetTransmissions()

            measurements[row,1] = trans
            measurements[row,2] = 0.0
            measurements[row,3] = Vset
            measurements[row,4] = rec
            measurements[row,5] = power_tap_initial
            measurements[row,0] = meas_wavelength

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Meas Wavelength = %.5f" % meas_wavelength)
            print("Atten. Voltage = " % Vset)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)
            io.savemat(outfilePath, {'scattering': measurements})

            row = row + 1



        if wasOff:
            self.LaserTurnOff()
        self.SParamSetBias(previousBias)

        #else:
        #    self.LaserSetOutputPower(previousPower)


    def PerformWatchTransmission(self):
        numpoints = 2220;
        measurements = zeros((numpoints,6),float)

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "scattering--%s--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
##                
##        if self.newWavelength > 0:
##            previousWavelength = self.newWavelength
##        else:
##            previousWavelength = 1260.00
##
##        if self.newPower > 0:
##            previousPower = self.parent.power
##        else:
##            previousPower = 1.00
##        
##        #laserPower = 10.00 # mW
##
        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False
##
##        self.LaserSetOutputPower(previousPower)
        #self.LWMainInitializeSensors(averagingTime=0.10)

        self.SParamSetMedIntegrationTime()

        row = 0
        while (row < numpoints):

            if self.parent.direction == "RIGHT_TO_LEFT":
                power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            else:
                power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

            #power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
            #try:
            #    power_tap_initial = max(0.0,float(power_tap_initial_string))
            #except ValueError:
            #    power_tap_initial = 0.0
           # 
            #IPpower = power_tap_initial*self.throughCalibrationFactor
            
            #trans, meas_wavelength, out, rec = self.LWMainGetTransmissions()

            received_power_string = self.lwmain.query("READ%d:POW?" % RECEIVED_POWER_CHANNEL )
            current = self.SParamGetPhotocurrent()
            try:
                received_power = max(0.0,float(received_power_string))
            except ValueError:
                received_power = 0.0

            measurements[row,0] = row
            #measurements[row,1] = trans
            #measurements[row,2] = meas_wavelength
            measurements[row,3] = received_power
            measurements[row,4] = current

            

            #print("Meas Wavelength = %.5f" % meas_wavelength)
            #print("%d Rec Power = %.3e with Current = " % (row, received_power))
            print("%d Rec Power = %.3e with Current = %.3e" % (row, received_power, current))
            #print("Transmission Loss = %.2f" % trans)
            io.savemat(outfilePath, {'scattering': measurements})

            row = row + 1

        self.SParamSetShortIntegrationTime()

        if wasOff:
            self.LaserTurnOff()
        #else:
        #    self.LaserSetOutputPower(previousPower)


    def PerformScatteringMeasurementFast(self):
        measurements = zeros((self.parent.numMeasWavelength,5),float)

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "scattering--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             self.parent.startMeasWavelength,
                                                                             self.parent.numMeasWavelength,
                                                                             self.parent.stopMeasWavelength,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
                
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        #if self.newPower > 0:
        #    previousPower = self.parent.power
        #else:
        #    previousPower = 1.00
        #
        #laserPower = 10.00 # mW

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        #self.LaserSetOutputPower(laserPower)
        #self.LWMainInitializeSensors(averagingTime=0.10)

        row = 0
        for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):

            self.LaserSetWavelength()
            self.LWMainSetWavelength()

            trans, meas_wavelength, out, rec = self.LWMainGetTransmissions(noWavemeter = True)

            measurements[row,1] = trans
            measurements[row,2] = 0.0
            measurements[row,3] = self.newWavelength
            measurements[row,4] = rec

            measurements[row,0] = meas_wavelength

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Meas Wavelength = %.5f" % meas_wavelength)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)

            row = row + 1

        io.savemat(outfilePath, {'scattering': measurements})

        self.SetWavelength(previousWavelength)
        #self.LWMainInitializeSensors()

        if wasOff:
            self.LaserTurnOff()
        #else:
        #    self.LaserSetOutputPower(previousPower)

    def PerformScatteringMeasurementTwoPort(self):
        measurements = zeros((self.parent.numMeasWavelength,6),float)

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        timeTuple = time.localtime()
        filename = "scattering--%s--%d-%d-%d--%d#%d#%d--%d#%d#%d.mat" % (    measDescription,
                                                                             self.parent.startMeasWavelength,
                                                                             self.parent.numMeasWavelength,
                                                                             self.parent.stopMeasWavelength,
                                                                             timeTuple[0],
                                                                             timeTuple[1],
                                                                             timeTuple[2],
                                                                             timeTuple[3],
                                                                             timeTuple[4],
                                                                             timeTuple[5])

        outfilePath = os.path.join(saveDirectory,filename)
        print "Saving data to ", outfilePath
                
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        #if self.newPower > 0:
        #    previousPower = self.parent.power
        #else:
        #    previousPower = 1.00
        #
        #laserPower = 10.00 # mW

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        #self.LaserSetOutputPower(laserPower)
        #self.LWMainInitializeSensors(averagingTime=0.10)

        row = 0
        for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):

            self.LaserSetWavelength()
            self.LWMainSetWavelength()

            trans, trans2, meas_wavelength, out, rec, rec2 = self.LWMainGetTransmissions(twoPort=True)

            measurements[row,1] = trans
            measurements[row,2] = trans2
            measurements[row,3] = self.newWavelength
            measurements[row,4] = rec
            measurements[row,5] = rec2

            measurements[row,0] = meas_wavelength

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Meas Wavelength = %.5f" % meas_wavelength)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)

            row = row + 1

        io.savemat(outfilePath, {'scattering': measurements})

        self.SetWavelength(previousWavelength)
        #self.LWMainInitializeSensors()

        if wasOff:
            self.LaserTurnOff()
        #else:
        #    self.LaserSetOutputPower(previousPower)


    def PerformL2RSplitterCalibration(self, plot = True):

        old_direction = self.parent.direction
        self.parent.direction = "LEFT_TO_RIGHT"

        newCalibration = list()


        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.newPower > 0:
            previousPower = self.parent.power
        else:
            previousPower = 10.00

        laserPower = 3.00 # mW (switchable)
        measurementCount = 10

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        self.LaserSetOutputPower(laserPower)
        #print 'power set'
        
        for self.newWavelength in linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths):
            
            self.LaserSetWavelength()
            self.LWMainSetWavelength(applyCalibrations=False)
            
            measList = list()
            #for i in xrange(measurementCount):
            trans, ret, out, rec, power_tap = self.LWMainGetTransmissions(applyCalibrations=False) ##AA added , power_tap
            ratio = 10.0**((0.0-trans)/10.0)
            measList.append(ratio)

            measArray = array(measList)

            aveRatio = measArray.mean()
            newCalibration.append(aveRatio)

            print("Mean ratio for %.2fnm = %.2f" % (self.newWavelength, aveRatio))
                
        self.parent.opticalCalibration = newCalibration

        pickleFileObject = open(self.parent.opticalCalibrationFile_1, 'w')
        pickle.dump(self.parent.opticalCalibration, pickleFileObject)
        pickleFileObject.close()

        self.SetWavelength(previousWavelength)
        
        if wasOff:
            self.LaserTurnOff()
        else:
            self.LaserSetOutputPower(previousPower)

        self.parent.direction = old_direction
        
        if (plot):
            plt.plot(linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths), newCalibration)
            plt.show()
            
    def PerformNoCalibration(self, plot = True):

        old_direction = self.parent.direction
        self.parent.direction = "NONE"

        newCalibration = list()


        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.newPower > 0:
            previousPower = self.parent.power
        else:
            previousPower = 10.00

        laserPower = 3.00 # mW (switchable)
        measurementCount = 10

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        self.LaserSetOutputPower(laserPower)
        #print 'power set'
        
        for self.newWavelength in linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths):
            
            self.LaserSetWavelength()
            self.LWMainSetWavelength(applyCalibrations=False)
            
            measList = list()
            #for i in xrange(measurementCount):
            trans, ret, out, rec, power_tap = self.LWMainGetTransmissions(applyCalibrations=False) ##AA added , power_tap
            ratio = 10.0**((0.0-trans)/10.0)
            measList.append(1)

            measArray = array(measList)

            aveRatio = measArray.mean()
            newCalibration.append(aveRatio)

            print("Mean ratio for %.2fnm = %.2f" % (self.newWavelength, aveRatio))
                
        self.parent.opticalCalibration = newCalibration

        pickleFileObject = open(self.parent.opticalCalibrationFile_None, 'w')
        pickle.dump(self.parent.opticalCalibration, pickleFileObject)
        pickleFileObject.close()

        self.SetWavelength(previousWavelength)
        
        if wasOff:
            self.LaserTurnOff()
        else:
            self.LaserSetOutputPower(previousPower)

        self.parent.direction = old_direction
        
        if (plot):
            plt.plot(linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths), newCalibration)
            plt.show()




    def PerformR2LSplitterCalibration(self, plot = True):

        old_direction = self.parent.direction
        self.parent.direction = "LEFT_TO_RIGHT"

        newCalibration = list()


        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.newPower > 0:
            previousPower = self.parent.power
        else:
            previousPower = 10.00

        laserPower = 3.00 # mW (switchable)
        measurementCount = 10

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        self.LaserSetOutputPower(laserPower)

        for self.newWavelength in linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths):
            self.LaserSetWavelength()
            self.LWMainSetWavelength(applyCalibrations=False)

            measList = list()
            for i in xrange(measurementCount):
                trans, ret, out, rec, power_tap = self.LWMainGetTransmissions(applyCalibrations=False) ##AA added , power_tap
                ratio = 10.0**((0.0-trans)/10.0)
                measList.append(ratio)

            measArray = array(measList)

            aveRatio = measArray.mean()
            newCalibration.append(aveRatio)

            print("Mean ratio for %.2fnm = %.2f" % (self.newWavelength, aveRatio))
                
        self.parent.opticalCalibration = newCalibration

        pickleFileObject = open(self.parent.opticalCalibrationFile_2, 'w')
        pickle.dump(self.parent.opticalCalibration, pickleFileObject)
        pickleFileObject.close()

        self.SetWavelength(previousWavelength)
        
        if wasOff:
            self.LaserTurnOff()
        else:
            self.LaserSetOutputPower(previousPower)

        self.parent.direction = old_direction
        
        if (plot):
            plt.plot(linspace(self.startCalWavelength,self.stopCalWavelength,self.numCalWavelengths), newCalibration)
            plt.show()


    def PerformPumpProbeScan(self):
        print("Congratulations!")

        ## EXPERIMENT PARAMETERS
        ## pump powers over which to scan
        ##lowpow = .1
        ##highpow = 10
        ##numpow = 20

        ## starting wavelength for sweeps up to final
        ##startwavelength = 1551.8

        ## finlambda = fitA*pow + fitB
        ##fitA = .016566
        ##fitB = 1552.195


        self.lockin.write("OUTX1")
        rcur = self.lockin.query("OUTP?3") ## gets current value of r
        print(rcur)

        measurements = zeros((self.parent.numMeasWavelength,3),float)

        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)

        ##First turn on the pump laser
        ###self.parent.laserSource = "Santec"
        ##if self.newWavelength > 0:
        ##    previousWavelength = self.newWavelength
       ## else:
       ##     previousWavelength = 1260.00

       ## self.LaserTurnOn()

        ##self.newWavelength=self.parent.wavelength
       ## self.LaserSetWavelength()


        filename = "lockinsweep--%s--%d-%d-%d.mat" % (    measDescription,
                                                    self.parent.startMeasWavelength,
                                                    self.parent.numMeasWavelength,
                                                    self.parent.stopMeasWavelength)
        outfilePath = os.path.join(saveDirectory,filename)

        ##Conduct the probe sweep
        ## self.parent.laserSource = "HP"
        
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        self.LaserTurnOn()
        ##self.LaserSetOutputPower(.5) ##weak probe power
        row = 0
        
        for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
      
            self.LaserSetWavelength()
            self.LWMainSetWavelength()

            time.sleep(2.5) ##for lock in value to be stable
            trans, meas_wavelength, out, rec = self.LWMainGetTransmissions()
            rcur = self.lockin.query("OUTP?3") ## gets current value of r
            measurements[row,0] = self.newWavelength
            measurements[row,1] = rcur
            measurements[row,2] = out

            print("Set Wavelength = %.3f" % self.newWavelength)
            print("Rec Power = %.3e" % rec)
            print("Transmission Loss = %.2f" % trans)
            print("Lockin R value:")
            print(rcur)

            row = row + 1

        io.savemat(outfilePath, {'liset': measurements})

        #### END OF BOTH LOOPS
        self.SetWavelength(previousWavelength)
        #self.LWMainInitializeSensors()

        #else:
        #    self.LaserSetOutputPower(previousPower)
    
    def PerformNaiveInitMeasurement(self, plot = True):
        # to set laser power    self.LaserSetOutputPower(self.newPower)
        
        startpower = self.parent.startMeasPower;
        endpower = self.parent.stopMeasPower;
        numpower = self.parent.numMeasPower;
        
        saveDirectory = os.path.dirname(self.userFilePath)
        measDescription = os.path.basename(self.userFilePath)
        if self.newWavelength > 0:
            previousWavelength = self.newWavelength
        else:
            previousWavelength = 1260.00

        if self.activeModule == -1:
            self.LaserTurnOn()
            wasOff = True
        else:
            wasOff = False

        lamstart = self.parent.startMeasWavelength;
        lamend = self.parent.stopMeasWavelength;
        numlam = self.parent.numMeasWavelength;
        
        if (plot):
            plt.clf()
            
        for Pset in linspace(startpower,endpower,numpower):
            measurements = zeros((numlam,6),float)

            filename = "TvsPNaive-%s-%duW-%dnm-%dnm-%dnm.mat" % (measDescription, 1000*Pset,  self.parent.startMeasWavelength,
                                                                             self.parent.numMeasWavelength,
                                                                             self.parent.stopMeasWavelength
                                                )
            outfilePath = os.path.join(saveDirectory,filename)
            print "Saving data to ", outfilePath

            lrow=0
            self.LaserSetOutputPower(Pset)
            #self.LWMainInitializeSensors(averagingTime=0.10)

            if self.parent.direction == "RIGHT_TO_LEFT":
                power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            else:
                power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

            power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
            try:
                power_tap_initial = max(0.0,float(power_tap_initial_string))
            except ValueError:
                power_tap_initial = 0.0
            
            IPpower = power_tap_initial/self.throughCalibrationFactor

  #          for self.newWavelength in linspace(self.parent.startMeasWavelength,self.parent.stopMeasWavelength,self.parent.numMeasWavelength):
            for self.newWavelength in linspace(lamstart,lamend,numlam):
                
                # Turn Off and On the laser to mimic the naive behavior
                self.LaserTurnOff()
                self.LaserSetWavelength()
                self.LWMainSetWavelength()
                self.LaserTurnOn()
                time.sleep(0.01)

                #self.SetILXWavelength()
                                
                if self.parent.direction == "RIGHT_TO_LEFT":
                    power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
                else:
                    power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL

                power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
                try:
                    power_tap_initial = max(0.0,float(power_tap_initial_string))
                except ValueError:
                    power_tap_initial = 0.0;
                
                IPpower = power_tap_initial/self.throughCalibrationFactor
                trans, meas_wavelength, out, rec, power_tap = self.LWMainGetTransmissions()
                
                time.sleep(0.01)
                #ILXPower = float(self.GetILXPower())
                
                # [lambda, transmission, input power in waveguide, lambda, tap_power]
                measurements[lrow,0] = meas_wavelength
                measurements[lrow,1] = trans
                measurements[lrow,2] = IPpower
                measurements[lrow,3] = self.newWavelength
                measurements[lrow,4] = power_tap_initial
                #measurements[lrow,5] = ILXPower

                print("Set Wavelength = %.3f" % self.newWavelength)
                print("Set Power = %.3f" % Pset)

                print("Meas Wavelength = %.5f" % meas_wavelength)
                print("Rec Power = %.3e" % rec)
                print("Transmission Loss = %.2f" % trans)
                # print("Optometer Power = %.3e" % ILXPower)
                io.savemat(outfilePath, {'scattering': measurements})

                lrow = lrow + 1
                ##End lambda loop
            
            if (plot):
                plt.plot(measurements[:,3], measurements[:,1])
            ##End power loop
            
        self.LaserTurnOff()
        
        if (plot):
            plt.ion()
            plt.show()
        #else:
        #    self.LaserSetOutputPower(previousPower)

        

##-----------------------------------------------------
## Generic Laser Commands
##-----------------------------------------------------


    def LaserTurnOn(self):
        if self.santec1 and self.parent.laserSource == "Santec":
            self.activeModule = 0
            self.santec1.write("LO")
            self.santec2.write("LO")
            self.santec3.write("LO")
            self.santec4.write("LO")
        elif self.lwmain and self.parent.laserSource == "HP":
            self.lwmain.write(":POW:STAT 1")
        elif self.isgsantec and self.parent.laserSource == "IsgSantec":
            self.isgsantec.write(":POW:STAT 1")
            self.isgsantec.write(":POW:SHUT 1")
        elif self.isgsantec and self.parent.laserSource == "IsgSantecFINE":
            self.isgsantec.write(":POW:STAT 1")
            self.isgsantec.write(":POW:SHUT 1")
        else:
            print "Laser Error"


    def LaserTurnOff(self):
        if self.santec1 and self.parent.laserSource == "Santec":
            self.activeModule = -1
            self.santec1.write("LF")
            self.santec2.write("LF")
            self.santec3.write("LF")
            self.santec4.write("LF")
        elif self.lwmain and self.parent.laserSource == "HP":
            self.lwmain.write(":POW:STAT 0")
        elif self.isgsantec and self.parent.laserSource == "IsgSantec":
            self.isgsantec.write(":POW:STAT 0")
            self.isgsantec.write(":POW:SHUT 0")
        elif self.isgsantec and self.parent.laserSource == "IsgSantecFINE":
            self.isgsantec.write(":POW:STAT 0")
            self.isgsantec.write(":POW:SHUT 0")
        else:
            print "Laser Error"


    def LaserSetOutputPower(self, power):
        if self.santec1 and self.parent.laserSource == "Santec":
            self.santec1.write("LP %.2f" % power)
            self.santec2.write("LP %.2f" % power)
            self.santec3.write("LP %.2f" % power)
            self.santec4.write("LP %.2f" % power)
        elif self.lwmain and self.parent.laserSource == "HP":
            self.lwmain.write("POW %.7EMW" % power)
            time.sleep(0.01)
        elif self.isgsantec and self.parent.laserSource == "IsgSantec":
            self.isgsantec.write(":POW %.7E" % power)
        elif self.isgsantec and self.parent.laserSource == "IsgSantecFINE":
            self.isgsantec.write(":POW %.7E" % power)
        else:
            print "Laser Error"


    def LaserSetWavelength(self):
        
        print self.parent.laserSource
        
        if self.santec1 and self.parent.laserSource == "Santec":
            if self.newWavelength < 1630.000001 and self.newWavelength > 1530 :
                self.santec1.write("SW 4")
                self.santec4.write("WA %.4f" % self.newWavelength)
                if self.activeModule != 4:
                    self.activeModule = 4
                    time.sleep(5.00)
                else:
                    time.sleep(0.01)
            elif self.newWavelength < 1530.1 and self.newWavelength > 1440 :
                self.santec1.write("SW 3")
                self.santec3.write("WA %.4f" % self.newWavelength)
                if self.activeModule != 3:
                    self.activeModule = 3
                    time.sleep(5.00)
                else:
                    time.sleep(0.01)
            elif self.newWavelength < 1440.1 and self.newWavelength > 1355 :
                self.santec1.write("SW 2")
                self.santec2.write("WA %.4f" % self.newWavelength)
                if self.activeModule != 2:
                    self.activeModule = 2
                    time.sleep(5.00)
                else:
                    time.sleep(0.01)
            elif self.newWavelength < 1355.1 and self.newWavelength > 1259.999999 :
                self.santec1.write("SW 1")
                self.santec1.write("WA %.4f" % self.newWavelength)
                if self.activeModule != 1:
                    self.activeModule = 1
                    time.sleep(5.00)
                else:
                    time.sleep(0.01)
            else :
                print "error wave out of range" 
                
        elif self.lwmain and self.parent.laserSource == "HP":
            self.lwmain.write("WAV %.7ENM" % self.newWavelength)
            self.activeModule = 0
            
            time.sleep(0.01)
            

            #dummy = ''
            #while dummy != '1':
            #    dummy = self.lwmain.query("*OPC?").strip()
            #    print dummy

            
        elif self.isgsantec and self.parent.laserSource == "IsgSantec":
            self.isgsantec.write(":WAV %.4f" % self.newWavelength)
            self.activeModule = 0
            time.sleep(0.01)
        elif self.isgsantec and self.parent.laserSource == "IsgSantecFINE":
            self.isgsantec.write(":WAV:FINE %.3f" % self.newWavelength)
            self.activeModule = 0
            time.sleep(0.01)
        else:
            print "Laser Error"


##-----------------------------------------------------
## Sensor Commands
##-----------------------------------------------------


    def LWMainInitializeSensors(self, averagingTime = 0.05):

        # Set basic parameters
        self.lwmain.write("SENS%d:CHAN1:POW:ATIME %.3fS" % (LEFT_POWER_TAP_CHANNEL, averagingTime))
        self.lwmain.write("SENS%d:CHAN1:POW:ATIME %.3fS" % (RIGHT_POWER_TAP_CHANNEL, averagingTime))
        self.lwmain.write("SENS%d:CHAN1:POW:ATIME %.3fS" % (RECEIVED_POWER_CHANNEL, averagingTime))
        self.lwmain.write("SENS%d:CHAN1:POW:ATIME %.3fS" % (RECEIVED_POWER_2_CHANNEL, averagingTime))
        self.lwmain.write("SENS%d:CHAN1:POW:UNIT 1" % RECEIVED_POWER_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:UNIT 1" % RECEIVED_POWER_2_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:UNIT 1" % LEFT_POWER_TAP_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:UNIT 1" % RIGHT_POWER_TAP_CHANNEL)

        self.lwmain.write("SENS%d:CHAN1:POW:RANG:AUTO 1" % RECEIVED_POWER_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:RANG:AUTO 1" % RECEIVED_POWER_2_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:RANG:AUTO 1" % LEFT_POWER_TAP_CHANNEL)
        self.lwmain.write("SENS%d:CHAN1:POW:RANG:AUTO 1" % RIGHT_POWER_TAP_CHANNEL)

        # Do not measure continuously
        self.lwmain.write("INIT%d:CHAN1:CONT 0" % LEFT_POWER_TAP_CHANNEL)
        self.lwmain.write("INIT%d:CHAN1:CONT 0" % RIGHT_POWER_TAP_CHANNEL)
        self.lwmain.write("INIT%d:CHAN1:CONT 0" % RECEIVED_POWER_CHANNEL)
        self.lwmain.write("INIT%d:CHAN1:CONT 0" % RECEIVED_POWER_2_CHANNEL)


    def UpdateCalibration(self):
        
        waveDelta = self.newWavelength-self.startCalWavelength
        waveIndex = int(round(waveDelta/(self.stopCalWavelength-self.startCalWavelength)*(self.numCalWavelengths-1)))
        if (waveIndex > self.numCalWavelengths-1):
            waveIndex = self.numCalWavelengths-1
        elif (waveIndex < 0):
            waveIndex = 0
        self.throughCalibrationFactor = self.parent.opticalCalibration[waveIndex]


    def LWMainSetWavelength(self, applyCalibrations = True):
        self.lwmain.write("SENS%d:CHAN1:POW:WAV %.7ENM" % (RECEIVED_POWER_CHANNEL, self.newWavelength))
        self.lwmain.write("SENS%d:CHAN1:POW:WAV %.7ENM" % (RECEIVED_POWER_2_CHANNEL, self.newWavelength))
        self.lwmain.write("SENS%d:CHAN1:POW:WAV %.7ENM" % (LEFT_POWER_TAP_CHANNEL, self.newWavelength))
        self.lwmain.write("SENS%d:CHAN1:POW:WAV %.7ENM" % (RIGHT_POWER_TAP_CHANNEL, self.newWavelength))
        time.sleep(0.01)

        if applyCalibrations:
            waveDelta = self.newWavelength-self.startCalWavelength
            waveIndex = int(round(waveDelta/(self.stopCalWavelength-self.startCalWavelength)*(self.numCalWavelengths-1)))
            if (waveIndex > self.numCalWavelengths-1):
                waveIndex = self.numCalWavelengths-1
            elif (waveIndex < 0):
                waveIndex = 0
            self.throughCalibrationFactor = self.parent.opticalCalibration[waveIndex]
        else:
            self.throughCalibrationFactor = 1.0


    def WMeterGetWavelength(self):
        
        if self.bristol_get_wave:
            measured_wavelength = self.bristol_get_wave(self.bristol_handle)
        else:
            measured_wavelength = -1

        return measured_wavelength


    def LWMainGetTransmissions(self, applyCalibrations = True, twoPort = False, noWavemeter = False):
        
        if self.parent.direction == "RIGHT_TO_LEFT":
            power_tap_channel_to_use = RIGHT_POWER_TAP_CHANNEL
            print power_tap_channel_to_use
        else:
            power_tap_channel_to_use = LEFT_POWER_TAP_CHANNEL
        
        #self.lwmain.write("INIT%d:IMM" % RETURN_LOSS_CHANNEL)
        self.lwmain.write("INIT%d:IMM" % power_tap_channel_to_use)
        self.lwmain.write("INIT%d:IMM" % RECEIVED_POWER_CHANNEL)
        if twoPort:
            self.lwmain.write("INIT%d:IMM" % RECEIVED_POWER_2_CHANNEL)

        if not noWavemeter:
            wavelength = self.WMeterGetWavelength()
            #wavelength = -1
#Ebrahim
#            dummy = ''
#            while dummy != '1':
#                dummy = self.lwmain.query("*OPC?")

        else: 

            wavelength = self.newWavelength

        #power_tap_initial_string = self.lwmain.query("READ%d:POW?" % power_tap_channel_to_use)
        #received_power_string = self.lwmain.query("READ%d:POW?" % RECEIVED_POWER_CHANNEL )
        
        power_tap_initial_string = self.lwmain.query("FETC%d:POW?" % power_tap_channel_to_use)
        try:
            power_tap_initial = max(0.0,float(power_tap_initial_string))
        except ValueError:
            power_tap_initial = 0.0
        
        received_power_string = self.lwmain.query("FETC%d:POW?" % RECEIVED_POWER_CHANNEL )
        
        try:
            received_power = max(0.0,float(received_power_string))
        except ValueError:
            received_power = 0.0
            
        if twoPort:
            received_power_2_string = self.lwmain.query("FETC%d:POW?" % RECEIVED_POWER_2_CHANNEL )
            try:
                received_power_2 = max(0.0,float(received_power_2_string))
            except ValueError:
                received_power_2 = 0.0

        self.lwmain.write("*CLS")
        
        if applyCalibrations:
            through_loss = 10*log10((received_power + 1.0e-15)/(power_tap_initial/self.throughCalibrationFactor + 1.0e-15))
            if twoPort:
                through_loss_2 = 0.0-10*log10((received_power_2 + 1.0e-15)/(power_tap_initial/self.throughCalibrationFactor + 1.0e-15))
        else:
            through_loss = 10*log10((received_power + 1.0e-15)/(power_tap_initial + 1.0e-15))

            if twoPort:
                through_loss_2 = 0.0-10*log10((received_power_2 + 1.0e-15)/(power_tap_initial + 1.0e-15))

        if applyCalibrations:
            out_power = power_tap_initial/self.throughCalibrationFactor+1.0e-15
#            print('Calibration Factor: ', self.outputCalibrationFactor) #Ebrahim
        else:
            out_power = power_tap_initial+1.0e-15

        #return through_loss, return_loss, out_power, received_power
        if twoPort:
            return through_loss, through_loss_2, wavelength, out_power, received_power, power_tap_initial
        else:
           ## return through_loss, wavelength, out_power, received_power
            return through_loss, wavelength, out_power, received_power, power_tap_initial ##AA

##-----------------------------------------------------
## Sensor Commands
##-----------------------------------------------------


    def SParamInitializeChannel(self):
        self.sparam.write("US")
        time.sleep(1.0)

        self.sparam.write("FMT 2")
        self.sparam.write("AV 1")
        self.sparam.write("CM 0")
        self.sparam.write("SLI 1")
        #self.sparam.write("FL 0")
        self.sparam.write("CN %d" % self.parent.sparamChannel)
        self.sparam.write("CN 2")
        self.sparam.write("DV 2,11,0,"+str(SPARAM_CURRENT_COMPLIANCE)) # Last number: current compliance (0.05)

        self.SParamSetBias(self.parent.pdBias)

    def LaserDrvOutput(self, enable):
        print("LASer:OUTput %d"%enable)
        self.laserdrv.write("LASer:OUTput %d"%enable)

    def LaserDrvLocal(self):
        self.laserdrv.write("LOCAL")


    def KeithleySetBias(self, bias_voltage):
        self.keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % bias_voltage)
        time.sleep(0.01)
        self.keithley.write(":INIT")

    def KeithleyGetPhotocurrent(self):
        if self.keithley:
            try:
                self.keithley.write(":INIT")
                time.sleep(0.1)
                current_meas_array = self.keithley.query_for_values(":FETC?")
                photocurrent = current_meas_array[1]
            except ValueError:
                photocurrent=0.0
        else:
            photocurrent = 0.0
        return photocurrent

    #def SParamSetBias(self, bias_voltage):
    #    self.keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % bias_voltage)
    #    time.sleep(0.01)
    #    self.keithley.write(":INIT")

    def SParamGetPhotocurrent(self):
        if self.keithley:
            try:
                self.keithley.write(":INIT")
                time.sleep(0.1)
                current_meas_array = self.keithley.query_for_values(":FETC?")
                photocurrent = current_meas_array[1]
            except ValueError:
                photocurrent=0.0
        else:
            photocurrent = 0.0
        return photocurrent


    def KeithleyInitializeChannel(self):
        self.keithley.write("*RST")
        time.sleep(1.0)
        self.keithley.write(':SOUR:FUNC VOLT')
        self.keithley.write(':SENS:FUNC "CURR"')
        self.keithley.write(':SOUR:SWE:RANG AUTO')
        self.keithley.write(':SENS:CURR:PROT 0.001')
        self.keithley.write(':SENS:CURR:RANG:AUTO ON')
        self.keithley.write(':SENS:CURR:NPLC 1')
        self.keithley.write(':SOUR:VOLT:LEV:AMPL 0.0')

        self.keithley.write(':OUTP ON')
        print("Initializing Keithley")

    def SParamClose(self):
        self.sparam.write("CL")
        self.sparam.write(":PAGE")


    def SParamSetBias(self, bias_voltage):                                ## THE ORIGINAL
        #self.sparam.write("DV %d,12,%.5E,0.100" % (self.parent.sparamChannel, bias_voltage))
        #self.sparam.write("DV %d,12,%.5E,0.050" % (self.parent.sparamChannel, bias_voltage)) # commented by amir 10.27.2016 to change compliance
        #self.sparam.write("DV %d,12,%.5E,0.050" % (2, 0.0))  # commented by amir 10.27.2016 to change compliance
        self.sparam.write("DV %d,12,%.5E,%.4f" % (self.parent.sparamChannel, bias_voltage, SPARAM_CURRENT_COMPLIANCE))  # added by amir 10.27.2016 to change compliance
        #self.sparam.write("DV %d,12,%.5E,0.001" % (2, 0.0))  # added by amir 10.27.2016 to change compliance
        #self.sparam.write("*CLS")
        #dummy = '0'
        #while dummy == '0':
        #    self.sparam.write("*OPC")
        #    dummy = self.sparam.query("*ESR?")
        #self.sparam.write("*CLS")



    def SParamSetLongIntegrationTime(self):
        self.sparam.write("SLI 3")

    def SParamSetMedIntegrationTime(self):
        self.sparam.write("SLI 2")
        
    def SParamSetShortIntegrationTime(self):
        self.sparam.write("SLI 1")
        
    def SParamGetPhotocurrent(self):                             ##THE ORIGINAL
        if self.sparam:
            try:
                photocurrent = float(self.sparam.query("TI? %d,0" % self.parent.sparamChannel))
            except ValueError:
                photocurrent = 0.0
        else:
            photocurrent = 0.0
        return photocurrent


    def SetILXWavelength(self):
        try:
            self.optometer.write("WAVE %.4f" % self.newWavelength)
        except:
            print("Error Setting Wavelength")

    def GetILXPower(self):
        return self.optometer.query("POWer?")