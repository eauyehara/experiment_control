# import socketserver
from instrumental import u
from instrumental.drivers.tempcontrollers.lakeshore import LakeShore331S
import struct
import socketserver
import socket
import threading

# Server Parameters
server_port = 9996

# Bristol 721 Instrumental driver parameters
lakeshore_visa_address = 'GPIB1::12::INSTR'
lakeshore_params={'module':'tempcontrollers.lakeshore',
                'classname':'LakeShore331S',
                'visa_address':lakeshore_visa_address}

# Open KJL vacuum gauge
tc = LakeShore331S(visa_address=lakeshore_visa_address)


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
        in_out = str(self.data, "utf-8")
        print('in_out: ' + in_out)
        #channel = int(str(self.data, "utf-8")[2])
        if in_out=='TmA':
            Tmeas_A_K = tc.Tmeas_A.m
            Tmeas_A_ba = bytearray(struct.pack("f", Tmeas_A_K))
            self.request.sendall(Tmeas_A_ba)
        elif in_out=='TmB':
            Tmeas_B_K = tc.Tmeas_B.m
            Tmeas_B_ba = bytearray(struct.pack("f", Tmeas_B_K))
            self.request.sendall(Tmeas_B_ba)
        elif in_out=='TsA':
            Tset_A_K = tc.Tset_A.m
            Tset_A_ba = bytearray(struct.pack("f", Tset_A_K))
            self.request.sendall(Tset_A_ba)
        elif in_out=='TsB':
            Tset_B_K = tc.Tset_B.m
            Tset_B_ba = bytearray(struct.pack("f", Tset_B_K))
            self.request.sendall(Tset_B_ba)
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
