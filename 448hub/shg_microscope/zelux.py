"""
Python code for basic use of Thorlabs Zelux compact scientific cameras.
Copied/modified from python code Thorlabs' Scientific Camera Interfaces kit:
    .../Scientific Camera Interfaces/SDK/Python Tookit/examples/*.py
"""

import os
import sys
import  numpy as np
from instrumental import u

"""
Add Zelux camera DLLs to Windows path for Python/ctypes access
"""
is_64bits = sys.maxsize > 2**32
if is_64bits:
    absolute_path_to_dlls = os.path.abspath("C:\Program Files\Thorlabs\Scientific Imaging\ThorCam")
else:
    absolute_path_to_dlls = os.path.abspath("C:\Program Files (x86)\Thorlabs\Scientific Imaging\ThorCam")

os.environ['PATH'] = absolute_path_to_dlls + os.pathsep + os.environ['PATH']
try:
    # Python 3.8 introduces a new method to specify dll directory
    os.add_dll_directory(absolute_path_to_dlls)
except AttributeError:
    pass

from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE

"""
Grab image from camera
"""
def grab_image(exposure_time=10*u.ms,cam_id=None,image_poll_timeout=2*u.second):
    with TLCameraSDK() as sdk:
        if cam_id is None:
            cameras = sdk.discover_available_cameras()
            if len(cameras) == 0:
                print("Error: no cameras detected!")
            cam_id = cameras[0]
        with sdk.open_camera(cam_id) as camera:
            # store existing camera config parameters
            # old_roi = camera.roi  # store the current roi
            old_exp_time = camera.exposure_time_us
            #  setup the camera for single acquisition
            camera.frames_per_trigger_zero_for_unlimited = 1
            camera.exposure_time_us = round(exposure_time.to(u.us).m)
            camera.image_poll_timeout_ms = 2000 #image_poll_timeout.to(u.ms).m  # 2 second timeout
            camera.arm(2)
            # begin acquisition
            camera.issue_software_trigger()
            frame = camera.get_pending_frame_or_null()
            if frame is None:
                raise TimeoutError("Timeout was reached while polling for a frame, program will now exit")
            image_data = np.copy(frame.image_buffer)
            camera.disarm()
            # reset camera configuration
            camera.exposure_time_us = old_exp_time
            # camera.roi = old_roi
    return image_data
