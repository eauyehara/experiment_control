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
#### For Windows
Download installer from 
https://sourceforge.net/projects/seabreeze/files/SeaBreeze/installers/
and run

#### For MacOS
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

### 3. Install pyqtgraph
conda install pyqtgraph

http://www.pyqtgraph.org/documentation/installation.html

### 3. Connect usb to spectrometer and test 
$ python ./experiment_control/ocean_optics_HR4000_plot.py


## Setup for PyVisa and Keithley 2400 SourceMeter

### 1. Install PyVisa
Follow instructions at https://pyvisa.readthedocs.io/en/master/getting.html

### 2. Install NI-VISA backend(drivers etc.)

Download and install NI-VISA
http://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html#305862

Install NI-488.2 for GPIB support
http://www.ni.com/en-us/support/downloads/drivers/download.ni-488-2.html#306165

for Mac OSX
Allow National Instruments software access to system in System Preferences > Security & Privacy

Check to see if the driver is properly installed
In [1]: import visa
In [2]: rm = visa.ResourceManager()
In [3]: rm.list_resources()
Out[3]: ('ASRL1::INSTR', 'GPIB0::15::INSTR')
