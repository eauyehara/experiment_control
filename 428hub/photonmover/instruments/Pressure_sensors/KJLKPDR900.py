import sys
sys.path.insert(0, '../..')
from Interfaces.Instrument import Instrument
import serial
import time

COM_ADDRESS = 'COM2'


class KJLKPDR900(Instrument):

    def __init__(self):
        super().__init__()

    def initialize(self):
        """
        Initializes the instrument.
        :return:
        """
        print("Initializing connection to Tunable Filter")
        self.ser = serial.Serial(COM_ADDRESS, timeout=3)

    def close(self):
        """
        Closes the instrument.
        :return:
        """
        print("Closing connection to Tunable Filter")
        self.ser.close()

    def get_pressure(self):
        """
        Queries the pressure.
        :return:
        """
        message = '@001DL?;FF'
        self.ser.write(message.encode('ascii'))
        self.ser.flush()
        print(self.ser.read(5).encode('ascii'))


if __name__ == '__main__':
    ps = KJLKPDR900()
    ps.initialize()
    print(ps.get_pressure())
    ps.close()

