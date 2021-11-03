import sys
sys.path.insert(0,'../..')
import numpy as np
import visa
import time
from Interfaces.SourceMeter import SourceMeter
from Interfaces.Instrument import Instrument

GPIB_ADDR = "GPIB1::23::INSTR"  # GPIB adress
DEFAULT_CURRENT_COMPLIANCE = 0.002  # Default current compliance in A


class KeysightB2902A(Instrument, SourceMeter):
    """
    Code for controlling Keysight B2902A through GPIB
    """

    def __init__(self, current_compliance=DEFAULT_CURRENT_COMPLIANCE):
        super().__init__()

        # It is good practice to initialize variables in init
        self.gpib = None
        self.cur_compliance = current_compliance
        self.is_on = 0
        self.v_compliance = None
        self.mode = 'VOLT'

    def initialize(self):
        """
        Initializes the instrument
        :return:
        """
        print('Opening connnection to keysight source meter')

        rm = visa.ResourceManager()
        try:
            self.gpib = rm.open_resource(GPIB_ADDR, timeout=5000)
        except:
            raise ValueError('Cannot connect to the Keysight Source meter')

        self.init_function()  # Set to voltage source with compliance

    def close(self):
        self.gpib.close()

    def turn_on(self):
        """
        Turns the source on
        :return:
        """
        self.gpib.write(":OUTP ON")
        self.is_on = 1

    def turn_off(self):
        """
        Turns the source off
        :return:
        """
        self.gpib.write(":OUTP OFF")
        self.is_on = 0

    def set_func(self, mode):
        """

        :param mode: Either VOLT or CURR
        :return:
        """
        if not (mode == 'VOLT' or mode == 'CURR'):
            print('Source meter mode not correct. NO action taken')
            return

        self.gpib.write((":SOUR:FUNC:MODE %s" % mode))
        self.mode = mode

    def set_voltage_compliance(self, v_comp):
        self.gpib.write((":SENS:VOLT:PROT %.4E" % v_comp))
        self.gpib.write(":OUTP:PROT ON")
        self.v_compliance = v_comp

    def set_current_compliance(self, i_comp):
        self.gpib.write((":SENS:CURR:PROT %.4E" % i_comp))
        self.gpib.write(":OUTP:PROT ON")
        self.cur_compliance = i_comp

    def set_voltage(self, voltage):
        """
        Sets the specified voltage
        :param voltage: 
        :return: 
        """
        if not (self.mode == 'VOLT'):
            self.turn_off()
            self.set_func('VOLT')
            time.sleep(0.1)

        if not self.is_on:
            self.turn_on()

        self.gpib.write(":SOUR1:VOLT %.4E" % voltage)

    def set_current(self, current):
        """
        Sets the specified current
        :param current:
        :return:
        """
        if not (self.mode == 'CURR'):
            self.turn_off()
            self.set_func('CURR')
            time.sleep(0.1)

        if not self.is_on:
            self.turn_on()

        self.gpib.write(":SOUR:CURR %.4E" % current)

    def init_function(self):
        """
        Initializes the source meter as a voltage source
        with the specified compliance
        """
        self.gpib.write("*RST")
        self.set_func('VOLT')
        self.set_current_compliance(self.cur_compliance)
        self.gpib.write(":SOUR:VOLT:RANG:AUTO ON")  # Auto voltage range
        self.gpib.write(":SENS:CURR:RANG:AUTO:MODE NOR")  # Auto meaasurement params

    def measure_current(self):
        self.gpib.write(":FORM:ELEM:SENS CURR")
        return float(self.gpib.query(":MEAS?"))

    def measure_voltage(self):
        self.gpib.write(":FORM:ELEM:SENS VOLT")
        return float(self.gpib.query(":MEAS?"))

    def measure_resistance(self):
        self.gpib.write(":FORM:ELEM:SENS RES")
        return float(self.gpib.query(":MEAS?"))

    def take_IV(self, start_v, stop_v, num_v):
        """
        Takes an IV curve
        :return: A two column matrix, where the first column is voltage
        and the second is current
        """

        self.config_volt_sweep(start_v, stop_v, num_v)

        # Once measurement is set up, perform the sweep and get the data
        self.gpib.write(":outp on")
        self.gpib.write(":init (@1)")
        self.gpib.write(":fetc:arr:curr? (@1)")
        currents = self.gpib.read()

        return [[np.linspace(start_v, stop_v, num_v)], [currents]]

    def config_volt_sweep(self, start_v, stop_v, num_v):
        """
        Sets the instrument to perform a voltage sweep with the
        specified parameters
        :param start_v:
        :param stop_v:
        :param num_v:
        :return:
        """

        self.set_func('VOLT')

        self.gpib.write(":sour:volt:mode swe")
        self.gpib.write(":sour:volt:star %.4E" % start_v)
        self.gpib.write(":sour:volt:stop %.4E" % stop_v)
        self.gpib.write(":sour:volt:poin %d" % num_v)

        # Set auto range current measurement
        self.gpib.write(":sens:func curr")
        self.gpib.write(":sens:curr:nplc 0.1")

        # Generate num_V triggers by automatic internal algorithm
        self.gpib.write(":trig:sour aint")
        self.gpib.write(":trig:coun %d" % num_v)
