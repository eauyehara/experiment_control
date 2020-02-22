# experiment control

## Common setup

### 0. Create Python 3.6 environment
python-seabreeze does not support Python 3.7 and above

$ conda create -n py36 python=3.6

$ conda activate py36

### 1. Clone Mabuchi lab sources

$ git clone https://github.com/mabuchilab/Instrumental.git

$ git clone https://github.com/mabuchilab/NiceLib.git

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
If a zip file is downloaded, plug in the spectrometer and use the update driver and browse for driver files from the extracted files.

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
For Python 3.6 distributions and below
$ conda install -c poehlmann python-seabreeze

For Python 3.8 and beyond
$ conda install -c poehlmann seabreeze

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
