#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot of cryo-probe station sample stage and radiation shield temperatures
and their set points streaming to a Lake Shore 331S cryo temperature controller.
"""

import socket
import sys
import struct
import numpy as np
from time import sleep
from instrumental import u

#default_wait = 0.9*u.second

### set up TCP communication ################
HOST, PORT = "localhost", 9996
data = " ".join(sys.argv[1:])
##############################################

def get_temperature(wait=0.1*u.second,n_tries_max=3,Temp_data='Tmeas_A'):
    if Temp_data=='Tmeas_A':
        call_str = 'TmA'
    elif Temp_data=='Tmeas_B':
        call_str = 'TmB'
    elif Temp_data=='Tset_A':
        call_str = 'TsA'
    elif Temp_data=='Tset_B':
        call_str = 'TsB'
    else:
        raise Exception('unrecognized Temp_data input')
    temperature = -1*u.degK
    n_tries = 0
    while temperature.m<0 and n_tries<3:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request measurement data from server
            sock.sendall(bytes(call_str, "utf-8"))
            sleep(wait.to(u.second).m)
            # Receive float wavelength in nm from the server
            temperature = struct.unpack('f',sock.recv(1024))[0]*u.degK
        finally:
            # close server
            sock.close()
        n_tries +=1
    return temperature
