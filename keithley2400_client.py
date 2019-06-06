#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Client for Keithley 2400 Source Meter

get_i: Fetches current measurement from source meter
"""

import socket
import sys
import struct
import numpy as np
from time import sleep
from instrumental import u

default_wait = 0.1*u.second

### set up TCP communication ################
HOST, PORT = "localhost", 9998
data = " ".join(sys.argv[1:])
##############################################

def get_i(wait=default_wait):
    current = np.array([])
    n_tries = 0
    while len(current)==0 and n_tries<10:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request AI0 data from server
            sock.sendall(bytes('GI', "utf-8"))
            sleep(wait.to(u.second).m)
            # Receive float current value from server

            current = np.append(current, struct.unpack('f',sock.recv(1024))[0])

        finally:
            # close server
            sock.close()
        n_tries +=1
    return current[-1]

def set_v(wait=default_wait, voltage=0.0):
    status = 'NO'
    n_tries = 0
    print('Setting voltage to {}'.format(voltage))

    while status!='OK' and n_tries<10:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request AI0 data from server
            sock.sendall(bytes('SV', "utf-8")+bytes(struct.pack("f", voltage)))
            sleep(wait.to(u.second).m)

            # Receive OK confirmation back from server
            status = str(sock.recv(1024), "utf-8")

        finally:
            # close server
            sock.close()
        n_tries +=1
    return status

def set_out(wait=default_wait, output='OFF'):
    status = 'NO'
    n_tries = 0
    print('Setting output {}'.format(output))

    while status!='OK' and n_tries<10:
        try:
            # open connection to server
            # Create a socket (SOCK_STREAM means a TCP socket)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            # Request AI0 data from server
            sock.sendall(bytes('SO'+output, "utf-8"))
            sleep(wait.to(u.second).m)

            # Receive OK confirmation back from server
            status = str(sock.recv(1024), "utf-8")

        finally:
            # close server
            sock.close()
        n_tries +=1
    return status
