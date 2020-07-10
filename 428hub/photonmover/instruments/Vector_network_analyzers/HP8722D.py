import sys
sys.path.insert(0,'../..')
from Interfaces.VNA import VNA
from Interfaces.Instrument import Instrument

import visa
import time
import numpy as np
import matplotlib.pyplot as plt
import csv


GPIB_ADDRESS = "GPIB1::24::INSTR"


class HP8722D(VNA, Instrument):
    """
    Code for getting data out of the HP 8722D VNA.
    For now, we are only interested in getting the data. If we found it is useful, we can
    extend it to actually control the VNA from the computer.
    """

    def __init__(self):
        super().__init__()
        self.gpib = None

    def initialize(self):
        print('Opening connnection to HP VNA')

        rm = visa.ResourceManager()
        try:
            self.gpib = rm.open_resource(GPIB_ADDRESS, timeout=5000)
        except:
            raise ValueError('Cannot connect to the HP VNA')

    def close(self):
        print('Disconnecting HP VNA')
        self.gpib.close()

    def read_data_lin_sweep(self, file=None, plot_data=True):
        """
        Reads the data from a linear sweep, by asking for initial frequency, end frequency and
        number of points to construct the frequencies.

        If file is specified, it creates a csv with the specified path and filename
        """

        # We assume that the measurement has been taken, we just want to retrieve the data
        #print('a')
        #sys.stdout.flush() 
        #res = self.gpib.query_ascii_values('OPC?;')
        #print(res)
        #sys.stdout.flush()        
        #while int(res[0]) != 1:
        #    time.sleep(1)
        #    res = self.gpib.query_ascii_values('OPC?;')
        #    print(res)
        #    sys.stdout.flush()

        # Set correct data transfer mode
        self.gpib.write('FORM4;')
        self.gpib.write('OUTPFORM;')

        # Get the data and convert it to a list
        data = self.gpib.read_raw().decode('ascii')
        data = data.replace('\n', ',')
        data = data.replace(' ', '')
        data = data.split(",")
        data = data[0:-2]
        data = [float(i) for i in data[0::2]]

        # Now get initial frequency, end frequency and number of points
        num_f = float(self.gpib.query_ascii_values('POIN?;')[0])
        init_f = float(self.gpib.query_ascii_values('STAR?;')[0])
        span_f = float(self.gpib.query_ascii_values('SPAN?;')[0])
        f = np.linspace(init_f, init_f+span_f, num_f)

        if plot_data:
            plt.plot(f, data)
            plt.show()

        if file is not None:
            with open(file, 'w+') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(f)
                writer.writerow(data)

        return [f, data]

    def read_data(self, file=None, plot_data=True):
        """
        Reads the data from any sweep. The data transfer is more complicated here.
        """

        # Assume that the data has been taken, just retrieving from the VNA
        # res = self.gpib.query_ascii_values('OPC?;')
        # print(res)
        # sys.stdout.flush()
        # while int(res) != 1:
        #     time.sleep(1)
        #     res = self.gpib.query_ascii_values('OPC?;')
        #     print(res)
        #     sys.stdout.flush()

        # Set correct data transfer mode
        self.gpib.write('FORM4;')
        self.gpib.write('OUTPFORM;')

        # Get the data and convert it to a list
        data = self.gpib.read_raw().decode('ascii')
        data = data.replace('\n', ',')
        data = data.replace(' ', '')
        data = data.split(",")
        data = data[0:-2]
        data = [float(i) for i in data[0::2]]

        # Get frequency
        self.gpib.write('OUTPLIML;')
        fr = self.gpib.read_raw().decode('ascii')
        fr = fr.replace('\n', ',')
        fr = fr.replace(' ', '')
        fr = fr.split(",")
        fr = fr[0:-4]
        fr = [float(i) for i in fr[0::4]]

        if plot_data:
            plt.plot(fr, data)
            plt.show()

        if file is not None:
            with open(file, 'w+') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(fr)
                writer.writerow(data)

        return [fr, data]


    def take_data(self, num_sweeps):
        """
        Triggers the acquisition of data over num_sweeps acquisitions
        """

        if num_sweeps == 1:
            self.gpib.query_ascii_values('OPC?; SING;')

        else:
            # Turn on averaging and trigger num_sweeps sweeps
            self.gpib.write('AVEROON; AVERFACT%d; AVERREST;' % num_sweeps)
            self.gpib.write('NUMG%d;' % num_sweeps)

        time.sleep(num_sweeps*4)


if __name__ == '__main__':
    hp = HP8722D()
    hp.initialize()
    #.read_data_lin_sweep('D:\\photonmover_MARC\\new_photonmover\\instruments\\Vector_network_analyzers\\'
     #                      'bw_0_8Vdc_1547_18nm_-20dBm.csv')
    hp.read_data('C:\\Users\\Prismo\\Desktop\\Marc\\trial_log.csv')
    hp.close()


