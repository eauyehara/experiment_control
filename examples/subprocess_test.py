import subprocess
spec_server_proc = subprocess.Popen(["python","oceanoptics_hr4000_server.py"])
from oceanoptics_hr4000_client import *
