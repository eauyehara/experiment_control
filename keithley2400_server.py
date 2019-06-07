#!/usr/local/bin python
# clear variables
#import sys
#sys.modules[__name__].__dict__.clear()

# Responsivity DAQ routine
from instrumental import u
import struct
import socketserver
import socket
import threading
import visa
import time

# Server Parameters
server_port = 9998

# Keithley 2400 parameters
GPIBPort = 26
keithley_params={'MaxCurrent':0.001, 'Output':'OFF'}

# Setup interface
rm = visa.ResourceManager()
print('Available resources {}'.format(rm.list_resources()))

# timeout is 3 sec
keithley = rm.open_resource('GPIB0::{}::INSTR'.format(GPIBPort), open_timeout=3000)

# Initialize Keithley 2400 Source meter
keithley.write('*RST')
time.sleep(1.0)
keithley.write(':SOUR:FUNC VOLT')
keithley.write(':SENS:FUNC "CURR"')
keithley.write(':SOUR:SWE:RANG AUTO')
keithley.write(':SENS:CURR:PROT {}'.format(keithley_params['MaxCurrent']))
keithley.write(':SENS:CURR:RANG:AUTO 1')
keithley.write(':SENS:CURR:NPLC 1')
keithley.write(':SOUR:VOLT:LEV:AMPL 0.0')

# keithley.write(':OUTP ON')
# keithley_params['Output'] = 'ON'


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(1024).strip()
        print("{} wrote:".format(self.client_address[0]))
        print(self.data)
        in_out = str(self.data[:2], "utf-8")
        # channel = int(str(self.data, "utf-8")[2])
        if in_out=='GI': # Get current
            print('Get current')

            # keithley.write(':OUTP ON')

            # channel = float(str(self.data, "utf-8")[2])

            # lm_nm = spec.get_wavelength().m
            # lm_ba = bytearray(struct.pack("f", lm_nm))
            # self.request.sendall(lm_ba)

            time.sleep(0.01)

            keithley.write(':INIT')

            time.sleep(0.1)

            current_meas_array = keithley.query_ascii_values(':FETC?')
            current_meas = current_meas_array[1]

            # keithley.write(':OUTP OFF')

            # print(current_meas)
            sm_ba = bytearray(struct.pack("f", current_meas))
            # print(sm_ba)
            self.request.sendall(sm_ba)
        elif in_out=='SV': # Set voltage
            print('Set Voltage')

            print(self.data)
            voltage = struct.unpack('f',self.data[2:])[0]

            print('Setting bias to {:g} V'.format(voltage))
            keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % voltage)

            time.sleep(0.01)
            self.request.sendall(bytes('OK', "utf-8"))
            # keithley.write(':OUTP ON')
            #
            #
            # measurements = zeros((bias_steps,2))
            #
            # row=0
            # # Enter measurement loop
            # bias_index = 0
            # for bias_current in bias_voltages:
            #
            #     keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % bias_current)
            #     print('Setting bias to {:g} V'.format(bias_current))
            #
            #     time.sleep(0.01)
            #
            #     measurements[bias_index,0] = bias_current
            #
            #     keithley.write(':INIT')
            #
            #     time.sleep(0.1)
            #
            #     # Test
            #     #current_meas_array = keithley.ask_for_values(":FETC?")
            #     #current_meas = current_meas_array[1]
            #
            #     current_meas_array = keithley.query_ascii_values(':FETC?')
            #     current_meas = current_meas_array[1]
            #
            #
            #     print('current {:g} uA'.format(current_meas*1e6))
            #     measurements[bias_index,1] = current_meas
            #
            #     bias_index = bias_index+1
            #
            #
            # keithley.write(':OUTP OFF')


            # sp_nm = spec.get_spectrum().m
            # sp_ba = bytearray(struct.pack("f", sp_nm))
            # self.request.sendall(sp_ba)
        elif in_out=='SO': # Set output
            # print(self.data)
            keithley_params['Output'] = str(self.data[2:], "utf-8")

            print('Setting output {}'.format(keithley_params['Output']))
            if keithley_params['Output']=='ON':
                keithley.write(':OUTP ON')
            else:
                keithley.write(':OUTP OFF')

            time.sleep(0.01)
            self.request.sendall(bytes('OK', "utf-8"))
        
        else:
            self.request.sendall('request not understood')




class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    HOST, PORT = "localhost", server_port

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    print('Starting Keithley 2400 server')
    server_thread.start()

    server.serve_forever()
#
#
#
#
# from datetime import date
# from math import *
# from numpy import *
# from scipy import io
# from scipy import optimize
# import visa
# from matplotlib import pyplot as plt
#
# print('Import successful')
#
# #bv1= linspace(-1.5, -0.5, 101)
# #bv2= linspace(-0.49, 0, 50)
# #bv3= linspace(0.01, 0.25, 25)
# #bv4= linspace(0.26, 0.5, 25)
#
# #bva = append(bv1,bv2)
# #bvb = append(bv3,bv4)
#
# #bias_voltages = append(bva,bvb)
# bias_voltages = linspace(1, -10, 11)
#
# start_voltage = min(bias_voltages)
# end_voltage = max(bias_voltages)
#
# bias_steps = len(bias_voltages)
#
# device_description = "pSi_PD_fixed_7_1220_tap70uW"
#
# timeTuple = time.localtime()
# DirectoryName = ".\\"
# Resp_OutFileName = "iv_%s_%d-%d-%d_on_%d#%d#%d--%d#%d#%d.mat" % (
#                             device_description,
#                             start_voltage,
#                             bias_steps,
#                             end_voltage,
#                             timeTuple[0],
#                             timeTuple[1],
#                             timeTuple[2],
#                             timeTuple[3],
#                             timeTuple[4],
#                             timeTuple[5])
# Resp_OutFileName = DirectoryName + Resp_OutFileName
#
# Figure_OutFileName = "iv_%s_%d-%d-%d_on_%d#%d#%d--%d#%d#%d.png" % (
#                             device_description,
#                             start_voltage,
#                             bias_steps,
#                             end_voltage,
#                             timeTuple[0],
#                             timeTuple[1],
#                             timeTuple[2],
#                             timeTuple[3],
#                             timeTuple[4],
#                             timeTuple[5])
# Figure_OutFileName = DirectoryName + Figure_OutFileName
#
#
# print('Set file names ok')
#
# # Setup interface
# rm = visa.ResourceManager()
# print('Available resources {}'.format(rm.list_resources()))
#
# # timeout is 3 sec
# keithley = rm.open_resource('GPIB::15::INSTR', open_timeout=3000)
#
# # Initialize semiconductor parameter analyzer
# keithley.write('*RST')
# time.sleep(1.0)
# keithley.write(':SOUR:FUNC VOLT')
# keithley.write(':SENS:FUNC "CURR"')
# keithley.write(':SOUR:SWE:RANG AUTO')
# keithley.write(':SENS:CURR:PROT 0.001')
# keithley.write(':SENS:CURR:RANG:AUTO 1')
# keithley.write(':SENS:CURR:NPLC 1')
# keithley.write(':SOUR:VOLT:LEV:AMPL 0.0')
#
# keithley.write(':OUTP ON')
#
#
# measurements = zeros((bias_steps,2))
#
# row=0
# # Enter measurement loop
# bias_index = 0
# for bias_current in bias_voltages:
#
#     keithley.write(':SOUR:VOLT:LEV:AMPL %.3f' % bias_current)
#     print('Setting bias to {:g} V'.format(bias_current))
#
#     time.sleep(0.01)
#
#     measurements[bias_index,0] = bias_current
#
#     keithley.write(':INIT')
#
#     time.sleep(0.1)
#
#     # Test
#     #current_meas_array = keithley.ask_for_values(":FETC?")
#     #current_meas = current_meas_array[1]
#
#     current_meas_array = keithley.query_ascii_values(':FETC?')
#     current_meas = current_meas_array[1]
#
#
#     print('current {:g} uA'.format(current_meas*1e6))
#     measurements[bias_index,1] = current_meas
#
#     bias_index = bias_index+1
#
#
# keithley.write(':OUTP OFF')
#
# # Plot
# plt.figure(0)
# #plt.plot(measurements[:,0], measurements[:,1], 'b-')
# plt.plot(measurements[:,0], log10(abs(measurements[:,1])), 'b-')
#
# #plt.xlim([0, 20])
# plt.xlabel("Bias Voltage [V]")
# plt.ylabel("Diode Current [uA]")
#
# plt.show()
# #plt.savefig(Figure_OutFileName, dpi=300)
# #plt.close(0)
#
#
# # Save to .mat file
# #io.savemat(Resp_OutFileName, {'IV_data': measurements})
