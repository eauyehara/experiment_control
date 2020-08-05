# import socketserver
from instrumental import u
from instrumental.drivers.spectrometers.bristol import Bristol_721
import struct
import socketserver
import socket
import threading

# Server Parameters
server_port = 9998

# Bristol 721 Instrumental driver parameters
CommPort = 3
bristol_params={'module':'spectrometers.bristol',
                'classname':'Bristol_721',
                'port':CommPort}
# Open Bristol 721 LSA
spec = Bristol_721(port=CommPort)

# class for fake Bristol instrument that opens and immediately closes, just in case errors persist
# class bristol_temp:
#     def __enter__(self):
#         spec = instrument(**bristol_params)
#         self.inst = spec
#         return spec
#     def __exit__(self,type,value,thing):
#         self.inst.close()

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
        in_out = str(self.data, "utf-8")[:2]
        channel = int(str(self.data, "utf-8")[2])
        if in_out=='LM':
            lm_nm = spec.get_wavelength().m
            lm_ba = bytearray(struct.pack("f", lm_nm))
            self.request.sendall(lm_ba)
        elif in_out=='SP':
            sp_nm = spec.get_spectrum().m
            sp_ba = bytearray(struct.pack("f", sp_nm))
            self.request.sendall(sp_ba)
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
