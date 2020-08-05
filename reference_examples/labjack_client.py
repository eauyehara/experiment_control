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


def read(ch):
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

def write(V,ch):
    try:
        # open connection to server
        # Create a socket (SOCK_STREAM means a TCP socket)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        # Request AO change from server
        AO_str = 'AO{} '.format(ch) + str(V)
        sock.sendall(bytes(AO_str, "utf-8"))
        # Receive float voltage from the server
        val = struct.unpack('f',sock.recv(1024))[0]
    finally:
        # close server
        sock.close()
    return val
