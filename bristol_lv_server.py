from labview_automation import LabVIEW
from os import path
#vi_path = r"C:\Program Files (x86)\Bristol Instruments\721 LSA\Programming\LabVIEWdrivers\Example I\getWavelength_v80_721_02.vi"
vi_path = path.normpath("C:/Program Files (x86)/Bristol Instruments/721 LSA/Programming/LabVIEWdrivers/Example I/getWavelength_v80_721_02.vi")

lv = LabVIEW()
lv.start() # Launches the active LabVIEW with the listener VI
with lv.client() as c:
    control_values = {
        "CommPort": 3,
        # "String Control": "Hello World!",
        # "Error In": {
        #     "status": False,
        #     "code": 0,
        #     "source": ""
        # }
    }
    indicators = c.run_vi_synchronous(
        vi_path, control_values)
    print(indicators['Result'])
    error_message = c.describe_error(indicators['Error Out'])
lv.kill() # Stop LabVIEW
