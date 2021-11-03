import sys
sys.path.insert(0,'../..')

from Interfaces.LightSource import LightSource
from Interfaces.Instrument import Instrument


class MockLaser(Instrument, LightSource):

    def __init__(self):
        super().__init__()

    def initialize(self):
        """
        Initializes the instrument
        :return:
        """
        print('Opening connnection to laser')

    def close(self):
        """
        Closes the instrument
        :return:
        """
        print('Closing connnection to laser')

    def turn_off(self):
        """
        Turn light off
        :return:
        """
        print('Turning off laser')

    def turn_on(self):
        """
        Turn light on
        :return:
        """
        print('Turning on laser')

    def set_power(self, power):
        """
        Set the power to the specified value (in mW)
        :return:
        """
        print('Setting power to %.4f mW' % power)

    def set_wavelength(self, wavelength):
        """
        Set the wavelength to the specified value (in nm)
        :return:
        """
        print('Setting wavelength to %.4f nm' % wavelength)
