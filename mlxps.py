import XPS_C8_drivers
import sys

# Display error function: simplify error print out and closes socket
def displayErrorAndClose (socketId, errorCode, APIName):
    if (errorCode != -2) and (errorCode != -108):
        [errorCode2, errorString] = myxps.ErrorStringGet(socketId,errorCode)
        if (errorCode2 != 0):
            print APIName + ': ERROR ' + str(errorCode)
        else:
            print APIName + ': ' + errorString
    else:
        if (errorCode == -2):
            print APIName + ': TCP timeout'
        if (errorCode == -108):
            print APIName + ': The TCP/IP connection was closed by an administrator'
    myxps.TCP_CloseSocket(socketId)
    return


# Instantiate the class
xps = XPS_C8_drivers.XPS()
# Connect to the XPS
socketId = xps.TCP_ConnectToServer('mlxps3.stanford.edu', 5001, 20)
# Check connection passed
if (socketId == -1):
    print 'Connection to XPS failed, check IP & Port'
    sys.exit ()

group = 'Autocorrelator'
positioner = group + '.UTM50'

# Kill the group
[errorCode, returnString] = xps.GroupKill(socketId, group)
if (errorCode != 0):
    displayErrorAndClose (socketId, errorCode, 'GroupKill')
    sys.exit ()
# Initialize the group
[errorCode, returnString] = xps.GroupInitialize(socketId,
group)
if (errorCode != 0):
    displayErrorAndClose (socketId, errorCode, 'GroupInitialize')
    sys.exit ()
# Home search
[errorCode, returnString] = xps.GroupHomeSearch(socketId,
group)
if (errorCode != 0):
    displayErrorAndClose (socketId, errorCode, 'GroupHomeSearch')
    exit
# Make some moves
# for index in range(10):
#     # Forward
#     [errorCode, returnString] = myxps.GroupMoveAbsolute(socketId,
#     positioner, [25.0])
#     if (errorCode != 0):
#         displayErrorAndClose (socketId, errorCode,'GroupMoveAbsolute')
#         sys.exit ()

#scanning UTM50 between extremes

while True:
    [errorCode, returnString] = xps.GroupMoveAbsolute(socketId,positioner, [-23])
    if (errorCode != 0):
        displayErrorAndClose (socketId, errorCode, 'GroupHomeSearch')
        exit
    [errorCode, returnString] = xps.GroupMoveAbsolute(socketId,positioner, [-24.5])
    if (errorCode != 0):
        displayErrorAndClose (socketId, errorCode, 'GroupHomeSearch')
        exit
