# import socketserver
from instrumental import u
from instrumental.drivers.vacuum.kjl import KPDR900
import struct
import socketserver
import socket
import threading

# Server Parameters
server_port = 9997

# Bristol 721 Instrumental driver parameters
kjl_visa_address = 'ASRL9::INSTR'
bristol_params={'module':'vacuum.kjl',
                'classname':'KPDR900',
                'visa_address':kjl_visa_address}

# Open KJL vacuum gauge
kjl = KPDR900(visa_address=kjl_visa_address)


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
        if in_out=='p':
            p_torr = kjl.get_pressure().m
            p_ba = bytearray(struct.pack("f", p_torr))
            self.request.sendall(p_ba)
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
