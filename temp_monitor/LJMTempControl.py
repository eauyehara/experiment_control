# import labjack library and connect to Labjack T7
# from labjack import ljm
from instrumental import u
import socket
import sys
import struct

### set up TCP communication ################
HOST, PORT = "localhost", 9999
data = " ".join(sys.argv[1:])

width_pix = 320
height_pix = 240
##############################################


def lj_client_read(ch):
    try:
        # open connection to server
        # Create a socket (SOCK_STREAM means a TCP socket)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        # Request AI data from server
        sock.sendall(bytes('AI{}'.format(ch), "utf-8"))
        # Receive float voltage from the server
        val = struct.unpack('f',sock.recv(1024))[0]
    finally:
        # close server
        sock.close()
    return val

def lj_client_write(V,ch):
    V_volt = V.to(u.volt).m
    try:
        # open connection to server
        # Create a socket (SOCK_STREAM means a TCP socket)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        # Request AO change from server
        AO_str = 'AO{} '.format(ch) + str(V_volt)
        sock.sendall(bytes(AO_str, "utf-8"))
        # Receive float voltage from the server
        val = struct.unpack('f',sock.recv(1024))[0]
    finally:
        # close server
        sock.close()
    return val


# # Open first found LabJack
# lj_handle = ljm.openS("ANY", "ANY", "ANY")  # Any device, Any connection, Any identifier
# lj_info = ljm.getHandleInfo(lj_handle)
# print("Opened a LabJack with Device type: %i, Connection type: %i,\n"
#       "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i" %
#       (lj_info[0], lj_info[1], lj_info[2], ljm.numberToIP(lj_info[3]), lj_info[4], lj_info[5]))
# lj_deviceType = lj_info[0]
#
# # define functions for reading and writing analog values and sending a TTL pulse using one of the digital channels
#
# def lj_write(voltage,handle=lj_handle,channel=0):
#     if channel not in [0,1]:
#         raise Exception('Invalid LabJack AIN channel')
#     name = 'DAC' + str(channel)
#     value = voltage.to(u.volt).m
#     ljm.eWriteName(lj_handle, name, value)
#
# def lj_read(handle=lj_handle,channel=0):
#     if channel not in [0,1,2,3]:
#         raise Exception('Invalid LabJack AIN channel')
#     name = 'AIN' + str(channel)
#     return ljm.eReadName(lj_handle, name) * u.volt
