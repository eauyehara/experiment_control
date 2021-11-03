from instruments.Light_sources.HPLightWave import HPLightWave
from instruments.Wavelength_meters.BrsitolWlMeter import BristolWlMeter
from instruments.Temperature_controllers.Newport3040 import Newport3040
import time
import numpy as np
import sys
import scipy.io as io
import winsound

# This script performs a wavelength sweep by sweeping the temperature of the laser diode.
# This is a console controlled interface (for simplicity).

TAP_CHANNEL = 1
REC_CHANNEL = 3

class TempSweeper():

    def __init__(self):
        self.power_meter = None
        self.temp_controller = None
        self.wavemeter = None

    def connect_instruments(self):
        # Connects to the relevant instruments (temp controller, power meter and wavemeter)
        self.power_meter = HPLightWave(tap_channel=TAP_CHANNEL, rec_channel=REC_CHANNEL)
        self.power_meter.initialize()
        self.power_meter.set_wavelength(1180)
        self.temp_controller = Newport3040()
        self.temp_controller.initialize()
        self.temp_controller.turn_on()
        self.wavemeter = BristolWlMeter()
        self.wavemeter.initialize()

    def close_connections(self):
        self.wavemeter.close()
        self.temp_controller.close()
        self.power_meter.close()

    def set_temp(self, temp):
        # Sets the temperature and prints the new wavelength
        self.temp_controller.set_temperature(temp)
        # Wait for the temp to stabilize
        time.sleep(1)
        return self.wavemeter.get_wavelength()

    def sweep_temp(self, init_temp, end_temp, step_temp, filename):
        # Sweeps the temperature to make a wavelength sweep.
        # If filename is not None, it saves the data into a csv file

        # Initialize the matrix to save the data
        temp_vec = np.arange(init_temp, end_temp+0.001, step_temp)
        measurements = np.zeros((len(temp_vec), 4), float)

        if filename is not None:

            time_tuple = time.localtime()
            filename = "Tsweep-%s-%d-%d-%d--%d#%d#%d_%d#%d#%d.mat" % (filename,
                                                                      init_temp,
                                                                      end_temp,
                                                                      step_temp,
                                                                      time_tuple[0],
                                                                      time_tuple[1],
                                                                      time_tuple[2],
                                                                      time_tuple[3],
                                                                      time_tuple[4],
                                                                      time_tuple[5])

            out_file_path = filename
            print("Saving data to ", out_file_path)

        row = 0

        for temp in temp_vec:

            wav = self.set_temp(temp)
            print(wav)
            time.sleep(0.2)

            tap_power, measured_received_power = self.power_meter.get_powers()

            measurements[row, 0] = wav
            measurements[row, 1] = temp
            measurements[row, 2] = measured_received_power
            measurements[row, 3] = tap_power

            print("Set Temp = %.3f C" % temp)
            print("Meas Wavelength = %.5f nm" % wav)
            print("Rec Power = %.3e W" % measured_received_power)
            sys.stdout.flush()

            row = row + 1

        if filename is not None:
            io.savemat(out_file_path, {'scattering': measurements})

        # Beep when done
        frequency = 2000  # Set Frequency To 2500 Hertz
        duration = 1000  # Set Duration To 1000 ms == 1 second
        winsound.Beep(frequency, duration)

        return measurements


if __name__ == '__main__':

    temp_sweeper = TempSweeper()
    temp_sweeper.connect_instruments()

    close = False

    while close is False:

        next_op = input("Enter operation (set [temp] - sweep [T0 T1 Tstep filename]) - end:")
        next_op = next_op.split()
        op = next_op[0]
        if op == 'set':
            try:
                temp = float(next_op[1])
                new_wav = temp_sweeper.set_temp(temp)
                print('The measured wavelength is %.4f nm' % new_wav)
            except:
                print('Temeperature not recognized.')

        elif op == 'sweep':
            #try:
            init_temp = float(next_op[1])
            end_temp = float(next_op[2])
            step_temp = float(next_op[3])
            if len(next_op) == 5:
                file_name = next_op[4]
            else:
                file_name = None

            temp_sweeper.sweep_temp(init_temp, end_temp, step_temp, file_name)
            #except:
            #    print('Temeperature not recognized.')

        elif op == 'end':
            close = True

        else:
            print('Operation not recognized. Enter a valid command. ')

    temp_sweeper.close_connections()
