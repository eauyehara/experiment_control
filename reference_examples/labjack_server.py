# import socketserver
from labjack import ljm
import struct
import socketserver
import socket
import threading

# Open first found LabJack
lj_handle = ljm.openS("ANY", "ANY", "ANY")  # Any device, Any connection, Any identifier
def lj_read_unitless(handle=lj_handle,channel=0):
    if channel not in [0,1,2,3]:
        raise Exception('Invalid LabJack AIN channel')
    name = 'AIN' + str(channel)
    return ljm.eReadName(lj_handle, name)

def lj_write_unitless(voltage,handle=lj_handle,channel=0):
    if channel not in [0,1]:
        raise Exception('Invalid LabJack AO channel')
    name = 'DAC' + str(channel)
    ljm.eWriteName(lj_handle, name, voltage)

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
        if in_out=='AI':
            V = lj_read_unitless(handle=lj_handle,channel=channel)
            V_ba = bytearray(struct.pack("f", V))
            self.request.sendall(V_ba)
        elif in_out=='AO':
            V = float(str(self.data, "utf-8")[3:])
            lj_write_unitless(V,handle=lj_handle,channel=channel)
            V_ba = bytearray(struct.pack("f", V))
            self.request.sendall(V_ba)
        else:
            self.request.sendall('request not understood')




class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()

    server.serve_forever()


##### pre-threading code
#
# class MyTCPHandler(socketserver.BaseRequestHandler):
#     """
#     The RequestHandler class for our server.
#
#     It is instantiated once per connection to the server, and must
#     override the handle() method to implement communication to the
#     client.
#     """
#
#     def handle(self):
#         # self.request is the TCP socket connected to the client
#         self.data = self.request.recv(1024).strip()
#         channel=int(str(self.data, "utf-8")[2])
#         V = lj_read_unitless(handle=lj_handle,channel=channel)
#         #V = lj_read_unitless(handle=lj_handle,)
#         V_ba = bytearray(struct.pack("f", V))
#         print("{} wrote:".format(self.client_address[0]))
#         print(self.data)
#         # just send back the same data, but upper-cased
#         #self.request.sendall(self.data.upper())
#         self.request.sendall(V_ba)
#         #self.request.sendall(bytes(channel_str+ "\n", "utf-8"))
#         #self.request.sendall(bytes(channel_str, "utf-8"))
#
# if __name__ == "__main__":
#     HOST, PORT = "localhost", 9999
#
#     # Create the server, binding to localhost on port 9999
#     server = socketserver.TCPServer((HOST, PORT), MyTCPHandler)
#
#     # Activate the server; this will keep running until you
#     # interrupt the program with Ctrl-C
#     server.serve_forever()
