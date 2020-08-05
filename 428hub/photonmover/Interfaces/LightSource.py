# This is an interface that any instrument that can
# be used as a light source has to implement.

from abc import ABC, abstractmethod
# ABC means Abstract Base Class and is basically an interface

class LightSource(ABC):

    def __init__(self):
        super().__init__()

    @abstractmethod
    def turn_off(self):
        """
        Turn light off
        :return:
        """
        pass

    @abstractmethod
    def turn_on(self):
        """
        Turn light on
        :return:
        """
        pass

    @abstractmethod
    def set_power(self, power):
        """
        Set the power to the specified value (in mW)
        :return:
        """
        pass

    @abstractmethod
    def set_wavelength(self, wavelength):
        """
        Set the wavelength to the specified value (in nm)
        :return:
        """
        pass