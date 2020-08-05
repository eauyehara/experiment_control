#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot of cryo-probe station pressure measured by KJL KPDR900 vacuum gauge.
"""

import socket
import sys
import struct
import numpy as np
from time import sleep
from instrumental import u

#default_wait = 0.9*u.second

### set up TCP communication ################
HOST, PORT = "localhost", 9997
data = " ".join(sys.argv[1:])
##############################################

def get_pressure(wait=0.9*u.second,n_tries_max=3):
    pressure = -1*u.torr
    n_tries = 0
    while lm.m<0 and n_tries<3:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request measurement data from server
            sock.sendall(bytes('p', "utf-8"))
            sleep(wait.to(u.second).m)
            # Receive float wavelength in nm from the server
            pressure = struct.unpack('f',sock.recv(1024))[0]*u.torr # KPDR900 measured pressure
        finally:
            # close server
            sock.close()
        n_tries +=1
    return pressure
