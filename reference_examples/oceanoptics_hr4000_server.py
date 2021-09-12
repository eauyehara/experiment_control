# import socketserver
from instrumental import u
from numpy import argmax
import seabreeze.spectrometers as sb
import struct
import socketserver
import socket
import threading

# Server Parameters
server_port = 9998

# Setup spectrometer
devices = sb.list_devices()
spec = sb.Spectrometer(devices[0])
spec.integration_time_micros(10000)
λ_nm = spec.wavelengths()
λ_nm_ba = λ_nm.tobytes()

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
        # in_out = str(self.data, "utf-8")[:2]
        # channel = int(str(self.data, "utf-8")[2])
        in_out = self.data.decode("utf-8")[:2]
        # channel = int(self.data.decode("utf-8")[2])
        if in_out=='SP':
            cts = spec.intensities()
            cts_ba = bytearray(cts.tobytes())
            self.request.sendall(cts_ba)
        elif in_out=='LM':
            self.request.sendall(λ_nm_ba)
        elif in_out=='PK':
            λ_peak_nm = λ_nm[argmax(spec.intensities())]
            λ_peak_nm_ba = bytearray(struct.pack("f", λ_peak_nm))
            self.request.sendall(λ_peak_nm_ba)
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
    server_thread.start()

    server.serve_forever()
