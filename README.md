# experiment control

## Common setup

### 1. Clone Mabuchi lab sources

$ git clone https://github.com/mabuchilab/Instrumental.git

$ git https://github.com/mabuchilab/NiceLib.git

$ git clone https://github.com/doddgray/experiment_control.git

### 2. Install Pyvisa

$ pip install pyvisa

### 3. Install future

$  conda install future

### 4. Run setup on each of Mabuchi lab sources

$  python ./NiceLib/setup.py install

$  python ./Instrumental/setup.py install
 
## Setup for Ocean Optics Spectrometer
### 1. Install seabreeze open source drivers

Download from 

https://sourceforge.net/projects/seabreeze/

Following the instructions in 

https://oceanoptics.com/api/seabreeze/index.html#install_linux

Run the following to compile Seabreeze drivers and set paths

$ make 

$ export DYLD_FALLBACK_FRAMEWORK_PATH="$PWD/lib"

$ export DYLD_LIBRARY_PATH="$PWD/lib"

Un plug and replug usb and Run the following to test if Seabreeze drivers are installed
$  test/seabreeze_test_posix 

### 2. Install python-seabreeze

$ conda install -c poehlmann python-seabreeze


### 3. Connect usb to spectrometer and test with Dodd's source

$ python ./experiment_control/live_ocean_optics_HR2000_spectrometer_gui.py
