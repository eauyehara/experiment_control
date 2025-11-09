import os
import time
import numpy as np
import xarray as xr
import sys
import clr
from copy import deepcopy
# from fontTools.ttLib.tables.otConverters import DeltaValue

sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
os.getcwd()
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.FilterFlipperCLI")

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.interpolate import griddata
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter
from scipy.stats import norm
from scipy import io

# import stuff from instrumental
from instrumental import instrument
from instrumental.drivers.daq.ni import Task # NIDAQ,
from instrumental.drivers.motion.filter_flipper import Position
from instrumental.drivers.motion.BPC203 import BPC203
# from photonmover.instruments.Lasers.M2_solstis import M2_Solstis
# from instrumental.drivers.lockins import sr844

from ..util.units import Q_, u
from ..util.io import *         # hdf5 utilites
from .powermeter import get_power, set_wavelength

## This code is derived from Dodd's shg_microscope.py
srs_rc_params = {
    'lines.linewidth': 1.5,
    'lines.markersize': 8,
    'legend.fontsize': 12,
    'text.usetex': False,
    'font.family': "serif",
    'font.serif': "cm",
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'axes.labelsize': 14,
    'axes.titlesize': 14,
    'font.size': 14,
    'axes.linewidth': 1,
    "grid.color": '#707070',
    'grid.linestyle':':',
    'grid.linewidth':0.7,
    'axes.grid': True,
    'axes.grid.axis': 'both',
    'axes.grid.which': 'both',
    'image.cmap':'winter',
    'savefig.dpi': 150,
    'figure.dpi': 75,
}

""" Initialize instruments """
daq = instrument("NIDAQ_USB-6259", reopen_policy='reuse')
daq2 = instrument("NIDAQ_USB-6259_2", reopen_policy='reuse')
ff = instrument("Thorlabs_FilterFlipper", reopen_policy='reuse')
cam = instrument('Thorlabs_camera', reopen_policy='reuse')
sm = instrument('Keithley_sm', reopen_policy='reuse',current_compliance=10e-9, voltage_compliance=89)
ps = instrument('Agilent_powerSupply', reopen_policy='reuse', current_limit=3e-3)
stage = instrument("NanoMax_stage", reopen_policy='reuse')
# laser = M2_Solstis()
# laser.initialize()

# Directory for calibration data
calib_dir = os.path.join(home_dir, "experiment_control","calibration_data","VCSEL_calibration")
# Calibration files
wavvolt_file = os.path.join(calib_dir, "wavvolt16_dev1b_15C_OE1076_0.00mW_2025-11-1.mat") #For wavelength set
wavvolt_HVCALIB = os.path.join(calib_dir, "wavvolt_HVCALIB_GSdev1b_delayvolt16_BOA700mA_2025-11-2.mat") #For post-acquisition wavelength calibration
delayvolt_file =os.path.join(calib_dir, "delayvolt16.mat")
# HV_calib_file = os.path.join(calib_dir, "HV_calib.mat")
# Directory for data save
data_dir = os.path.join(home_dir,"OneDrive","Documents","data","srs_microscope")
# data_dir = os.path.join(home_dir,"Dropbox (MIT)","POE","srs_microscope_data","srs_microscope_scans")

# Configure DAQ analog output channels for differential (0V-centered) control of x and y galvo mirrors
ch_Vx_p, ch_Vx_p_str = daq.ao0, 'Dev1/ao0'
ch_Vx_n, ch_Vx_n_str = daq.ao1, 'Dev1/ao1'
ch_Vy_p, ch_Vy_p_str = daq.ao2, 'Dev1/ao2'
ch_Vy_n, ch_Vy_n_str = daq.ao3, 'Dev1/ao3'
# Configure DAQ ctr1 channel
ch_clock, ch_clock_str = daq.ctr1, '/Dev1/PFI13'
# Configure DAQ 2 analog outputs (for sweeping VCSEL)
ch_VCSEL_MEMS, ch_VCSEL_MEMS_str = daq2.ao1, 'Dev2/ao1'  
ch_VOA, ch_VOA_str = daq2.ao0, 'Dev2/ao0' #Controls pump power to VCSEL
# Configure DAQ 2 ctr0 channel
ch_sync, ch_sync_str = daq2.ctr0, 'Dev2/ctr0'

# Configure DAQ analog input channels
ch_Vsrs, ch_Vsrs_str = daq.ai0, 'Dev1/ai0'
ch_Vx_meas, ch_Vx_meas_str = daq.ai2, 'Dev1/ai2'
ch_Vy_meas, ch_Vy_meas_str = daq.ai3, 'Dev1/ai3'#daq.ai3, 'Dev1/ai3'
ch_Vmon, ch_Vmon_str = daq.ai20, 'Dev1/ai20'  #O-ELand wavelength monitor in continuous sweep
# Configure DAQ PFI input channel
ch_trig_str = '/Dev1/PFI12'
# Configure DAQ 2 analog input channels
ch_Vsrs_2, ch_Vsrs_2_str = daq2.ai0, 'Dev2/ai0' #For spectrum sweeps
ch_HVA_Vmon, ch_HVA_Vmon_str = daq2.ai1, 'Dev2/ai1' #HVA voltage monitor
ch_wav_mon, ch_wav_mon_str = daq2.ai3, 'Dev2/ai3' #VCSEL wavelength monitor

# Configure filter flipper positions
ff_pos_in = Position.one
ff_pos_out = Position.two


""" Calibration data """
## Galvo scan distance/voltage calibrations
# Using Nikon 20x objective with cover slip, 0.5V/deg galvo mechanical scan angle setting, and 80umx80um bonding pads on TC2 chip - 3/2024
# Optical scan angle is 2x the mechanical scan angle (nominally 0.25V/deg)
Vx0, Vy0 = (0.21)*u.volt, (0.43)*u.volt # Galvo voltages for centered output beam, given centered input beam
dx_dVx = 174.2919 * u.um / u.volt   
dy_dVy = 173.1602 * u.um / u.volt   
Vmeas_Vwrite = 2  # Measured voltage at J6P1 is 2x the write voltage - Specify meas voltage throughout for consistency and convert before writing

## DCC1545M camera pixel to distance
pix_size = 5.2 * u.um #per pixel
obj_mag = 20  #Nikon 20x
dx_dpix = pix_size / obj_mag  #u.um # dx_dpix =  0.3651 * u.um # per pixel

## Lock in settle time scale factor
τ_settle = 5


""" Widefield Image """
def remove_bs():
    ff.move_and_wait(ff_pos_out)

def insert_bs():
    ff.move_and_wait(ff_pos_in)

def wf_illum_on():
    """
    Write TTL high to LED trigger
    """
    daq.port0.write(0x01)

def wf_illum_off():
    """
    Write TTL low to LED trigger
    """
    daq.port0.write(0x00)

def wf_image(exposure_time=3*u.ms):
    """
    Insert beam splitter, turn on LED, take widefield image, and remove beamsplitter. Return LED to initial state when done
    :param exposure_time:
    :return: img [2d array]
    """
    wf_illum_init = daq.port0.read()
    wf_illum_on()
    insert_bs()
    img = cam.grab_image(exposure_time=exposure_time)
    remove_bs()

    if not wf_illum_init:
        wf_illum_off()
    return img

def laser_spot_image(exposure_time=3*u.ms):
    """
    Insert beam splitter, turn off LED, take widefield image, and remove beamsplitter.  Return LED to initial state when done
    :param exposure_time:
    :return: laser_spot_img [2d array]
    """
    wf_illum_init = daq.port0.read()
    wf_illum_off()
    insert_bs()
    laser_spot_img = cam.grab_image(exposure_time=exposure_time)
    remove_bs()

    if wf_illum_init:
        wf_illum_on()
    return laser_spot_img


def wf_and_laser_spot_images(exposure_time=3*u.ms):
    """
    Insert beam splitter, turn off LED, take laser spot widefield image. Turn LED on, take widefield image (with laser spot).
    Remove beamsplitter, return LED to initial state
    :return: wf_img, laser_spot_img
    """
    wf_illum_init = daq.port0.read()
    insert_bs()
    wf_illum_off()
    laser_spot_img = cam.grab_image(exposure_time=exposure_time)
    wf_illum_on()
    wf_img = cam.grab_image(exposure_time=exposure_time)
    remove_bs()
    if not wf_illum_init:
        wf_illum_off()
    return wf_img, laser_spot_img

""" Stage Motion """
def initialize_stage():
    # Stage position jumps when initialize - only run if doing stage scan
    stage = instrument("NanoMax_stage", reopen_policy='reuse')
    return stage


def scan_single_axis(stage, scan_length, axis, step_size, wait=1 * u.s, fsamp = 3*u.Hz, num_avg=10):
    """
    Scan scan_length in [um] along specified axis (x,y,z) from initial position with specified step size (- if backward, + if forward)
    Read photodiode signal (at DAQ ch_Vsrs) at each position
    :return: [pos_arr (um), pd_arr (V)]
    """
    ax0 = stage.get_axis_position(axis)
    if step_size > 0:
        end_pos = scan_length.m + ax0
    elif step_size < 0:
        end_pos = ax0 - scan_length.m
    print(end_pos)

    if not stage.check_valid_position(axis, end_pos):
        raise ValueError("End position out of range")

    pos_arr = np.arange(ax0, end_pos + step_size.m, step_size.m)
    pd_arr = []

    # Print calculated scan time
    scan_time = (wait + (1/fsamp).to(u.second)*num_avg) * pos_arr.shape[0]
    start_time = time.time()
    end_time = start_time + scan_time.m
    print(f"scan time: {scan_time:3.2f}")
    print(f"start time: {time.ctime(start_time):s}")
    print(f"stop time: {time.ctime(end_time):s}")

    # Create DAQ task
    scan_task = Task(
        ch_Vsrs
    )

    # Set DAQ sampling rate and number of samples to write/read
    scan_task.set_timing(fsamp=fsamp, n_samples=num_avg)


    for pos in pos_arr:
        stage.set_axis_position(axis, float(pos))
        time.sleep(wait.m)
        read_data = scan_task.run()
        time.sleep((1/fsamp).m*num_avg)
        pd_arr.append(np.mean(read_data[ch_Vsrs_str].m))

    # Set stage back to initial position
    stage.set_axis_position(axis, ax0)

    return [pos_arr * u.um, pd_arr * u.V]


def knife_edge_scan(stage, scan_length, axis, step_size, wait=1*u.s, num_avg=10, sample_dir=None, name=None):
    """
    Beam spot size characterization - scans stage and acquires photodiode readings
    :return: ds_spot
    """
    remove_bs()

    # Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    fpath = new_path(name=name, data_dir=sample_dir, ds_type='knifeScan', extension='h5', timestamp=True)
    print("saving data to: ")
    print(fpath)

    # Run scan
    [pos_arr, pd_arr] = scan_single_axis(stage, scan_length, axis, step_size, wait=wait, num_avg=num_avg)

    # save scan parameters to hdf5
    dump_hdf5(
        {'scan_length': scan_length,
         'axis': axis,
         'step_size': step_size,
         'num_avg': num_avg,
         'pos_arr': pos_arr,
         'pd_arr': pd_arr
         },
        fpath,
        open_mode='x',
    )

    ds_spot = load_hdf5(fpath=fpath)

    return ds_spot


""" Galvo Motion """
def move_spot(Vx,Vy,Vx0=Vx0,Vy0=Vy0,wait=True,Verr=0.001*u.volt,t_polling=10*u.ms):
    """
    Move spot to position (Vx0 + Vx, Vy0 + Vy) (volt), where (Vx0, Vy0) is center position. Wait t_polling [ms] before exiting
    """
    Vx_target, Vy_target = (Vx+Vx0), (Vy+Vy0)
    #Divide voltage by 2 before writing to convert from
    ch_Vx_p.write(Vx_target / Vmeas_Vwrite)
    ch_Vx_n.write(-Vx_target / Vmeas_Vwrite)
    ch_Vy_p.write(Vy_target / Vmeas_Vwrite)
    ch_Vy_n.write(-Vy_target / Vmeas_Vwrite)
    if wait:
        time.sleep(t_polling.m_as('s'))
        # while abs(ch_Vx_meas.read()-Vx_target)>Verr or abs(ch_Vy_meas.read()-Vy_target)>Verr:
        #     time.sleep(t_polling.m_as('s'))
    return


def center_spot(Vx0=Vx0,Vy0=Vy0):
    """
    Move spot to center position (Vx0, Vyo) [volts]
    """
    move_spot(0*u.volt,0*u.volt,Vx0=Vx0,Vy0=Vy0)
    return


def get_spot_pos(Vx0=Vx0,Vy0=Vy0):
    """
    Get spot position [volts]
    :return: Vx, Vy [volts]
    """
    Vx = 2*ch_Vx_p.read() - Vx0
    Vy = 2*ch_Vy_p.read() - Vy0
    return Vx, Vy


""" Preview Scan """
def preview_scan_area(nx,ny,ΔVx,ΔVy,fsamp, exposure_time=3*u.ms):
    """
    Take a widefield laser spot image.  Given galvo scan voltage inputs (nx,ny,ΔVx,ΔVy), plot the widefield image cropped to the galvo scan area
    :return fig
    """
    # Print calculated scan time
    scan_time = (1 / fsamp).to(u.second) * nx * ny
    print(f"scan time: {scan_time:3.2f}")

    center_spot()
    Vx, Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time)
    fig = plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.gray)
    return fig


def preview_hyperspectral_scan(nx,ny,ΔVx,ΔVy,fsamp,wav_start,wav_stop,Δwav,num_sweep, exposure_time=3*u.ms):
    """
    Take a widefield laser spot image.  Given galvo scan voltage inputs (nx,ny,ΔVx,ΔVy), plot the widefield image cropped to the galvo scan area.
    Estimate scan time for given parameters
    :return fig
    """
    pad_galvo_endpts=1
    pad=5
    
    wavelength_set = generate_valid_sweep(wav_start, wav_stop, Δwav, wavvolt_file=wavvolt_file)
    daq_HVset, _, _, _ = parse_wav_delay(wavelength_set, wavvolt_file, delayvolt_file)
    V_MEMS_sweep = VCSEL_sweep_volts(daq_HVset, num_sweep)
    num_wav = (V_MEMS_sweep.shape[0] + pad_galvo_endpts)

    # Print calculated scan time
    print(f"num_pix: {nx*ny}")
    print(f"num_sweep_pts: {num_wav*nx*ny + pad*2}")
    scan_time = (1 / fsamp).to(u.second) * (nx * ny * num_wav + pad*2)
    print(f"scan time: {scan_time.to(u.min):3.2f}")

    center_spot()
    Vx, Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time)
    fig = plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.gray)
    return fig
    
    
def get_Nyquist_vals(N, d_spot, scale=2):
    """
    Calculate Nyquist-limite galvo scan length and corresponding galvo voltages given the number of sampling points and laser spot diamter
    """
    Nyq_samp = d_spot/scale
    dV = (Nyq_samp / max(dx_dVx, dy_dVy)).to(u.V)
    V_scan = (dV*N).to(u.V)
    L_scan = Nyq_samp*N
    print(f"scan volt: {V_scan}")
    print(f"scan length: {L_scan}")
    print(f"step size: {Nyq_samp}")
    return V_scan, L_scan
    
""" Scanning Galvo image acquisition """
def scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0):
    """
    Create 1d arrays of x scan voltages and y scan voltages
    :param nx, ny: number of points to scan in x and y
    :param ΔVx, ΔVy: Range of voltages to scan in x and y [volt] (Scan range  (-ΔVx/2, ΔVx/2) in x and (-ΔVy/2, ΔVy/2) in y)
    :param Vx0, Vy0: Spot center position [volt]
    :return Vx, Vy: 1d voltage arrays
    """
    Vx0V = Vx0.to(u.volt).m
    ΔVxV = ΔVx.to(u.volt).m
    Vy0V = Vy0.to(u.volt).m
    ΔVyV = ΔVy.to(u.volt).m
    Vx = np.linspace(Vx0V-(ΔVxV/2.0),Vx0V+(ΔVxV/2.0),nx)*u.volt  # 1d array of x voltages
    Vy = np.linspace(Vy0V-(ΔVyV/2.0),Vy0V+(ΔVyV/2.0),ny)*u.volt  # 1d array of y voltages
    return Vx, Vy


def raster_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0):
    """
    Arrange 1d scan arrays from scan_vals into proper order for raster scan
    :param nx, ny: number of points to scan in x and y
    :param ΔVx, ΔVy: Range of voltages to scan in x and y [volt] (Scan range  (-ΔVx/2, ΔVx/2) in x and (-ΔVy/2, ΔVy/2) in y)
    :param Vx0, Vy0: Spot center position [volt]
    :return: Vx_scan, Vy_scan: 1d arrays of raster scan values
    """
    # Create 1d x and y scan voltage arrays
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)

    # Concatenate 2 columns (forward and return scan: length 2*nx) and repeat ny/2 times
    Vx_scan = np.tile(np.concatenate((Vx.m,Vx.m[::-1])),ny//2)*u.volt

    # if ny odd, need to add one more forward traversing column
    if np.mod(ny,2):
        Vx_scan = np.concatenate((Vx_scan, Vx))

    # y voltages constant in each column (length nx)
    Vy_scan = np.repeat(Vy.m,nx)*u.volt

    return Vx_scan, Vy_scan


def configure_clock_signal(ch_trig_str, ch_clock, nsamples, freq_div):
    """
    Configure DAQ minitask to receive a trigger input signal and generate a clock signal output using a counter output
    ch_trig_str: channel name of terminal receiving trigger input signal
    ch_clock: channel object (counter output) of terminal outputting clock signal
    nsamples: number of samples to write to ch_clock
    freq_div: scales down trigger signal 
    """
    low_ticks = freq_div // 2
    
    if freq_div % 2 != 0: # even 
        high_ticks = low_ticks + 1
    else: # odd
        high_ticks = low_ticks 
        
    if freq_div <= 2:
        raise ValueError(f"freq_div must be greater than 2")
    # high_ticks = low_ticks + 1 # 50% duty cycle square wave
    clock_task = daq2._create_mini_task('CO') 
    clock_task.add_CO_channel(ch_clock, low_ticks=low_ticks, high_ticks=high_ticks, source_terminal=ch_trig_str)
    clock_task.config_implicit_timing(nsamples=nsamples)
    
    return clock_task


def configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,ch_clock_str=None):
    """
    Configure DAQ task with input/output channels specified above, set timing, and specify data to write to outputs (doesn't run task)
    :param nx, ny: number of points to scan in x and y
    :param ΔVx, ΔVy: Range of voltages to scan in x and y [volt] (Scan range  (-ΔVx/2, ΔVx/2) in x and (-ΔVy/2, ΔVy/2) in y)
    :param Vx0, Vy0: Spot center position [volt]
    :param fsamp: frequency at which DAQ writes a new output point and collects a new input point (NOT Galvo scan frequency)
    :return: scan_task, write_data: DAQ task, dict of output data to write to each channel
    """
    #Create 1d arrays of x and y raster scan voltages
    Vx_scan, Vy_scan = raster_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    
    # ai channels lag ao channels by one sample point - repeat last ao write value and discard first ai value in process_scan
    Vx_scan = np.concatenate((Vx_scan, [Vx_scan[-1]]))
    Vy_scan = np.concatenate((Vy_scan, [Vy_scan[-1]]))

    # Create DAQ task
    if ch_clock_str is not None:
        clock_str = ch_clock_str
    else:
        clock_str = None
    
    scan_task = Task(
        ch_Vx_p,
        ch_Vx_n,
        ch_Vy_p,
        ch_Vy_n,
        ch_Vsrs,
        ch_Vx_meas,
        ch_Vy_meas, 
        ch_range={
            ch_Vx_p_str :   (np.min(Vx_scan / Vmeas_Vwrite), np.max(Vx_scan / Vmeas_Vwrite)),
            ch_Vx_n_str :   (np.min(-Vx_scan / Vmeas_Vwrite), np.max(-Vx_scan / Vmeas_Vwrite)),
            ch_Vy_p_str :   (np.min(Vy_scan / Vmeas_Vwrite), np.max(Vy_scan / Vmeas_Vwrite)),
            ch_Vy_n_str :   (np.min(-Vy_scan / Vmeas_Vwrite), np.max(-Vy_scan / Vmeas_Vwrite)),
            ch_Vx_meas  :   (-np.max(Vx_scan), np.max(Vx_scan)*1.5),
            ch_Vy_meas  :   (-np.max(Vy_scan), np.max(Vy_scan)*1.5)
        }
    )
   
    # Set DAQ sampling rate and number of samples to write/read
    scan_task.set_timing(fsamp=fsamp,n_samples=nx*ny+1, clock=clock_str)

    # Print calculated scan time
    scan_time = (1/fsamp).to(u.second)*(nx*ny + 1)
    start_time = time.time()
    end_time = start_time + scan_time.m
    print(f"scan time: {scan_time:3.2f}")
    print(f"start time: {time.ctime(start_time):s}")
    print(f"stop time: {time.ctime(end_time):s}")

    # Create dictionary of data to write to each DAQ output channel
    write_data = {
        ch_Vx_p_str :   Vx_scan / Vmeas_Vwrite,
        ch_Vx_n_str :   -Vx_scan / Vmeas_Vwrite,
        ch_Vy_p_str :   Vy_scan / Vmeas_Vwrite,
        ch_Vy_n_str :   -Vy_scan / Vmeas_Vwrite,
    }
    
    return scan_task, write_data


def collect_wfscan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,name=None,sample_dir=None,wf_exposure_time=10*u.ms, ch_clock_str=None):
    """
    Collects widefield image and scan.
    Runs DAQ task - writes voltage arrays to galvos and reads srs signal / galvo scanner position. Processes data and dumps write_data, read_data, and proc_data to hdf5 file.
    Saves png image of scan. Loads hdf5 file and returns dataset ds. Recenters spot after scan
    :return: ds
    """
    #Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='GalvoScan',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)

    wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time=wf_exposure_time)
    x_img,y_img = img_spatial_axes(laser_spot_img)

    #Data here is saved as hdf5 attributes since not arrays
    dump_hdf5(
        {   'wf_img': wf_img.astype("int"),
            'laser_spot_img': laser_spot_img.astype("int"),
            'dx_dpix': dx_dpix,
            'x_img': x_img,
            'y_img': y_img,
    #         'P_ex': P_ex,
            "dx_dVx" : dx_dVx,
            "dy_dVy" : dy_dVy,
            "Vx0" : Vx0,
            "Vy0" : Vy0,
        },
        fpath,
        open_mode='x',
    )
    scan_task, write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,ch_clock_str=ch_clock_str)
    dump_hdf5(write_data,fpath)
    read_data = scan_task.run(write_data)
    dump_hdf5(read_data,fpath)
    scan_task.unreserve()
    center_spot(Vx0,Vy0)
    proc_data = process_scan(read_data,nx,ny,ΔVx,ΔVy)
    dump_hdf5(proc_data,fpath)
    ds = load_hdf5(fpath=fpath)
    save_scan_images(ds,name,fpath=sample_dir,wf_cmap=cm.binary_r,laser_cmap=cm.winter,srs_cmap=cm.inferno,rc_params=srs_rc_params,format='png')
    # save_spotzoom(ds,name,fpath=sample_dir,Dxy=10*u.um,figsize=(4.5,4.5),laser_cmap=cm.winter,x_wtext=-3,y_wtext=-3,rc_params=srs_rc_params,format="png",dpi=400,pad_inches=0.5)
    return ds


def collect_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,wf_img,laser_spot_img,name=None,sample_dir=None, ch_clock_str=None):
    """
    Collects scan only. (manually acquire widefield/laser spot image beforehand.
    Runs DAQ task - writes voltage arrays to galvos and reads srs signal / galvo scanner position. Processes data and dumps write_data, read_data, and proc_data to hdf5 file.
    Saves png image of scan. Loads hdf5 file and returns dataset ds. Recenters spot after scan
    :return: ds
    """
    #Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='GalvoScan',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)

    x_img,y_img = img_spatial_axes(laser_spot_img)

    #Data here is saved as hdf5 attributes since not arrays
    dump_hdf5(
        {   'wf_img': wf_img.astype("int"),
            'laser_spot_img': laser_spot_img.astype("int"),
            'dx_dpix': dx_dpix,
            'x_img': x_img,
            'y_img': y_img,
    #         'P_ex': P_ex,
            "dx_dVx" : dx_dVx,
            "dy_dVy" : dy_dVy,
            "Vx0" : Vx0,
            "Vy0" : Vy0,
        },
        fpath,
        open_mode='x',
    )
    scan_task, write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp, ch_clock_str=ch_clock_str)
    dump_hdf5(write_data,fpath)
    read_data = scan_task.run(write_data)
    dump_hdf5(read_data,fpath)
    scan_task.unreserve()
    center_spot(Vx0,Vy0)
    proc_data = process_scan(read_data,nx,ny,ΔVx,ΔVy)
    dump_hdf5(proc_data,fpath)
    ds = load_hdf5(fpath=fpath)
    save_scan_images(ds,name,fpath=sample_dir,wf_cmap=cm.binary_r,laser_cmap=cm.winter,srs_cmap=cm.inferno,rc_params=srs_rc_params,format='png')
    # save_spotzoom(ds,name,fpath=sample_dir,Dxy=10*u.um,figsize=(4.5,4.5),laser_cmap=cm.winter,x_wtext=-3,y_wtext=-3,rc_params=srs_rc_params,format="png",dpi=400,pad_inches=0.5)
    return ds


def collect_hyperspectral_img(
    nx, ny, ΔVx, ΔVy, Vx0, Vy0, fsamp, 
    t_lia, sens_lia, trig_params,
    wav_start, wav_stop, Δwav, fixed_wav, num_sweep=1, 
    pad_galvo_endpts=1,
    sample_dir=None, name=None,
    ch_clock=ch_clock, 
    ch_clock_str=ch_clock_str,
    ch_sync=ch_sync, 
    wf_exposure_time=10*u.ms,
    wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file
):
    """
    Collects widefield image and hyperspectral image.
    Runs 2 DAQ tasks - one to galvo DAQ, one to VCSEL DAQ - to synchronize wavelength sweep with image collection
        - Galvo DAQ: writes voltage arrays to galvos and reads srs signal + galvo scanner positions.
        - VCSEL DAQ: writes voltage arrays to VCSEL and VOA for wavelength tuning and delay compensation, reads srs signal at each wavelength
    Params:
        -wavvolt_file - .mat file with
        voltage to wavelength calibration
        -delayvolt_file - .mat file with VOA voltage per VCSEL MEMS voltage set
        -ch_sync - channel object (counter output) of sync output (VCSEL DAQ2)
        -trig_params - needs to be provided if ch_sync is not None (VCSEL DAQ2)
        -num_sweep - number of full period sweeps (forward + backward sweep)
        -ch_clock - channel object (counter output) of terminal outputting clock signal (Galvo DAQ)

    Processes data and dumps write_data, read_data, and proc_data to hdf5 file.
    Saves png image of scan. Loads hdf5 file and returns dataset ds. Recenters spot after scan
    :return: ds
    """
    
    #Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='HyperspecImg',extension='h5',timestamp=True)
    xrpath = new_path(name=name,data_dir=sample_dir,ds_type='HyperspecImg',extension='nc',timestamp=True)
    print("saving data to: ")
    print(fpath)
    print(xrpath)

    wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time=wf_exposure_time)
    x_img, y_img = img_spatial_axes(laser_spot_img)

    #------------------------------------------------------------------
    # Configure VCSEL wavelength sweep
    # Create array of valid wavelengths
    num_pix = nx*ny #actual number of pixels
    npix = num_pix + 1 # 1 additional galvo write since ai lags ao
    sweep_task, sweep_write_data, record_data = configure_VCSEL_sweep(wav_start, wav_stop, Δwav, fixed_wav, num_sweep, t_lia,
                                                                      wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, 
                                                                      ch_sync=ch_sync, trig_params=trig_params, num_pix=npix, 
                                                                      pad_galvo_endpts=pad_galvo_endpts)
    
    # Initialize to first voltages in sweep
    ramp_VCSEL(record_data["HVA_Vset"][0])
    
    # Number of wavelength samples
    pad = 5 #see configure_VCSEL_sweep()
    nwavs = (sweep_write_data[ch_VOA_str].shape[0] - 2*pad) / npix
    
    #------------------------------------------------------------------
    # Configure galvo scan
    freq_div = nwavs
    ntotal = nwavs*npix + 2*pad
    fsamp_galvo = fsamp / freq_div
    scan_task, galvo_write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp_galvo, ch_clock_str=ch_clock_str)
    print(f'ntotal: {sweep_write_data[ch_VOA_str].shape[0]}')
    print(f'nwavs: {nwavs}')
    print(f'npix: {npix}')
    
    # ------------------------------------------------------------------
    # Configure timing for galvo scan
    clock_task = configure_clock_signal(ch_trig_str, ch_clock, npix, freq_div=freq_div)
    
    # Discards first galvo write - no position initialization necessary
    # move_spot(galvo_write_data[ch_Vx_p_str][0], [ch_Vy_p_str][0])
    
    sweep_task.write(sweep_write_data, autostart=False)
    scan_task.write(galvo_write_data, autostart=False)
    
    # Estimate run time ------------------------------------------------
    # Print calculated scan time
    scan_time = (1/fsamp).to(u.second)*ntotal
    start_time = time.time()
    end_time = start_time + scan_time.m
    print(f"scan time: {scan_time:3.2f}")
    print(f"start time: {time.ctime(start_time):s}")
    print(f"stop time: {time.ctime(end_time):s}")
    
    # Start tasks -----------------------------------------------------
    # Sweep task starts clock_task which starts scan_task - start sweep_task last
    scan_task.start()
    clock_task.start()
    sweep_task.start()
    print('started all tasks')
    try:
        sweep_read_data = sweep_task.read()
        print('read sweep data')
        scan_read_data = scan_task.read()
        print('read scan data')
    finally:
        sweep_task.wait_until_done()
        print("sweep task done")
        scan_task.wait_until_done()
        print("scan task done")
        sweep_task.stop()
        scan_task.stop()
  
    sweep_task.unreserve()
    scan_task.unreserve()
    clock_task.clear() # unreserve() and stop() give errors for CO task
    
    #Data here is saved as hdf5 attributes since not arrays
    dump_hdf5(
        {   'wf_img': wf_img.astype("int"),
            'laser_spot_img': laser_spot_img.astype("int"),
            'dx_dpix': dx_dpix,
            'x_img': x_img,
            'y_img': y_img,
            "dx_dVx" : dx_dVx,
            "dy_dVy" : dy_dVy,
            "Vx0" : Vx0,
            "Vy0" : Vy0,
            'num_sweep': num_sweep,
            't_lia': t_lia,
            'sens_lia': sens_lia,
            'wav_start': wav_start,
            'wav_stop': wav_stop,
            'Δwav': Δwav,
            'wavelength_set': record_data["wavelength_set"],  # Sorted by increasing voltage (same as HV_set)
            'pump_wav': record_data["pump_wav"]
        },
        fpath,
        open_mode='x',
    )

    read_data = {**scan_read_data, **sweep_read_data}
    dump_hdf5(galvo_write_data,fpath)
    dump_hdf5(read_data,fpath)
    
    center_spot(Vx0,Vy0)
    
    proc_data, Vsrs_hs = process_hyperspectral_scan(scan_read_data,nx,ny,ΔVx,ΔVy,
                                                   sweep_read_data,record_data["wavelength_set"],fixed_wav,
                                                    num_sweep,pad_galvo_endpts,pad=5,Vx0=Vx0,Vy0=Vy0)
    dump_hdf5(proc_data,fpath)
    ds = load_hdf5(fpath=fpath)
    Vsrs_hs.to_netcdf(xrpath)
    
    # save_scan_images(ds,name,fpath=sample_dir,wf_cmap=cm.binary_r,laser_cmap=cm.winter,srs_cmap=cm.inferno,rc_params=srs_rc_params,format='png')
    # save_spotzoom(ds,name,fpath=sample_dir,Dxy=10*u.um,figsize=(4.5,4.5),laser_cmap=cm.winter,x_wtext=-3,y_wtext=-3,rc_params=srs_rc_params,format="png",dpi=400,pad_inches=0.5)
    return ds, Vsrs_hs
    

def process_hyperspectral_scan(scan_read_data,nx,ny,ΔVx,ΔVy,
                               sweep_read_data,wavelength_set,fixed_wav,num_sweep,pad_galvo_endpts,
                               pad=5,Vx0=Vx0,Vy0=Vy0):
    """
    Parses sweep_read_data and scan_read_data dicts into a 3d array of wavelength scans at each pixel.
    Creates meshgrids of set Vx and Vy write scan voltages and interpolates Vsrs data AT EACH WAVELENGTH at these points from measured Vx and Vy.
    Notes: 
        - HV to wavelength calibration not performed here, but necessary datasets for calibration saved in proc_data
        - Assumes single sweep per pixel - better to increase SNR by increasing t_lia (see versions before 10/25/25 for unwrapping multiple sweeps per pixel)
    :return: proc_data: dictionary of processed data, with image data stored in an xarray
    """
    t_scan = scan_read_data["t"]
    t_sweep = sweep_read_data["t"]
    
    offset = 0
    
    if num_sweep > 1:
        raise ValueError("Unwrapping only handles num_sweep=1 per pixel!")
    
    #Sort wavelength by ascending order and remove repeated values
    # s_ind = np.argsort(wavelength_set)
    # wavset_sort = wavelength_set[s_ind]
    wavset_sort, s_ind = np.unique(wavelength_set.to(u.nm).m, return_index=True)
    wavset_sort = wavset_sort * u.nm
    
    Vsrs_raw = sweep_read_data[ch_Vsrs_2_str]
    HV_raw = Vmon_to_HVA(sweep_read_data[ch_HVA_Vmon_str])
    VCSEL_wavmon_raw = sweep_read_data[ch_wav_mon_str]
    
    #Remove padded samples at endpoints of daq2 arrays
    Vsrs_raw = Vsrs_raw[pad:-pad]
    HV_raw = HV_raw[pad:-pad]
    VCSEL_wavmon_raw = VCSEL_wavmon_raw[pad:-pad]
    
    #Reshape into 2d array with n_pix rows
    num_pix = nx*ny 
    npix = num_pix + 1
    N_wav = Vsrs_raw.shape[0] // npix
    N_unqwav = s_ind.shape[0]
    
    print(f"npix: {npix}")
    print(f"Vsrs_raw.shape[0]: {Vsrs_raw.shape[0]}")
    print(f"N_wav: {N_wav}")
    print(f"N_unqwav: {N_unqwav}")
    
    Vsrs_pix = np.reshape(np.array(Vsrs_raw.to(u.V).m), (npix, N_wav))
    HV_pix = np.reshape(np.array(HV_raw.to(u.V).m), (npix, N_wav))
    VCSEL_wavmon_pix = np.reshape(np.array(VCSEL_wavmon_raw.to(u.V).m), (npix, N_wav))
    
    #If discard 1st pixel, rows out of sync - images appear striated
    #Discard pad_galvo_endpts points from the start of each row - vcsel ai lags ao
    Vsrs_pix = Vsrs_pix[:-1,pad_galvo_endpts:]
    HV_pix = HV_pix[:-1,pad_galvo_endpts:] 
    VCSEL_wavmon_pix = VCSEL_wavmon_pix[:-1,pad_galvo_endpts:]
    
    # Initialize arrays for pixel x spectra with sorted, unique spectral points
    Vsrs_unqpix = np.zeros((num_pix, N_unqwav))
    HV_unqpix = np.zeros((num_pix, N_unqwav))
    VCSEL_wavmon_unqpix = np.zeros((num_pix, N_unqwav))
    
    #Odd pixels are backward sweeps - flip (Assumes only 1 num_sweeps per pix is 1)
    for row in range(Vsrs_pix.shape[0]):
        if row % 2 != 0:
            Vsrs_pix[row,:] = Vsrs_pix[row,::-1]
            HV_pix[row,:] = HV_pix[row,::-1]
            VCSEL_wavmon_pix[row,:] = VCSEL_wavmon_pix[row,::-1]
        # Sort columns (wavelength sweep) by ascending order and remove repeated values
        Vsrs_unqpix[row,:] = Vsrs_pix[row, s_ind]
        HV_unqpix[row,:] = HV_pix[row, s_ind]
        VCSEL_wavmon_unqpix[row,:] = VCSEL_wavmon_pix[row, s_ind]
        
    #Interpolate each wavelength to measured pixel grid
    Vx_meas = scan_read_data[ch_Vx_meas_str][1:] #discard 1st ai value (ai lags ao by 1 sample point)
    Vy_meas = scan_read_data[ch_Vy_meas_str][1:] #discard 1st ai value (ai lags ao by 1 sample point)
    
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    Vx_g, Vy_g = np.meshgrid(Vx.m,Vy.m)
    
    Vsrs_g = np.zeros((nx, ny, N_unqwav))
    HV_g = np.zeros((nx, ny, N_unqwav))
    VCSEL_wavmon_g = np.zeros((nx, ny, N_unqwav))
    
    for hvind in range(Vsrs_unqpix.shape[1]):
        Vsrs_g[:,:, hvind] = griddata((Vx_meas.m, Vy_meas.m), Vsrs_unqpix[:, hvind], (Vx_g, Vy_g)) * u.volt
        #No interpolation necessary for HV, use griddata to reshape array
        HV_g[:,:, hvind] = unwrap_scan(HV_unqpix[:,hvind], nx, ny) * u.volt
        VCSEL_wavmon_g[:,:,hvind] = unwrap_scan(VCSEL_wavmon_unqpix[:,hvind], nx, ny) * u.volt
        
    x = ((Vx-Vx0)*dx_dVx).to(u.um)
    y = ((Vy-Vy0)*dy_dVy).to(u.um)
    
    #Convert wavelength_set to wavenumber
    raman_shift = (1/fixed_wav - 1/wavset_sort).to(1/u.cm)
    
    #Store hs-image into xarray
    Vsrs_hs = hs_xarray(data=Vsrs_g, x=x, y=y, raman_shift=raman_shift)
    # HV_hs = hs_xarray(data=HV_g, x=x, y=y, wavelength=wavelength_set, raman_shift=raman_shift)
    
    #Store hs-image data and additional info into proc_data dict
    proc_data = {
        "Vx"                : Vx,
        "Vy"                : Vy,
        "dx_dVx"            : dx_dVx,
        "dy_dVy"            : dy_dVy,
        "x"                 : x,
        "y"                 : y,
        "Vsrs_pix"          : Vsrs_unqpix,
        "HV_pix"            : HV_unqpix,
        "VCSEL_wavmon_pix"  : VCSEL_wavmon_unqpix,
        "Vsrs_g"            : Vsrs_g,
        "raman_shift"       : raman_shift,
        "wavset_sort"       : wavset_sort,
        "HV_g"              : HV_g,
        "VCSEL_wavmon_g"    : VCSEL_wavmon_g,
        "t_scan"            : t_scan,
        "t_sweep"           : t_sweep
    }
    
    return proc_data, Vsrs_hs

    
def process_scan(read_data,nx,ny,ΔVx,ΔVy,Vx0=Vx0,Vy0=Vy0):
    """
    Parses read_data dict and writes into variables.  Creates meshgrids of set Vx and Vy write scan voltages and interpolates Vsrs data at these points from measured Vx and Vy.
    Converts galvo voltages to position in microns (x, y).
    :return: proc_data: dictionary of processed data
    """
    t = read_data['t']
    
    # discard first ai value (ai lags ao by 1 sample point)
    Vsrs = read_data[ch_Vsrs_str][1:]
    Vx_meas = read_data[ch_Vx_meas_str][1:]  #J6P1 (scanner position) on x galvo board
    Vy_meas = read_data[ch_Vy_meas_str][1:]  #J6P1 (scanner position) on y galvo board
    
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    Vx_g, Vy_g = np.meshgrid(Vx.m,Vy.m)
    Vsrs_g = griddata((Vx_meas.m, Vy_meas.m), Vsrs.m, (Vx_g, Vy_g)) * u.volt

    x = ((Vx-Vx0)*dx_dVx).to(u.um)
    y = ((Vy-Vy0)*dy_dVy).to(u.um)

    proc_data = {
        "Vx"      : Vx,
        "Vy"      : Vy,
        "dx_dVx"  : dx_dVx,
        "dy_dVy"  : dy_dVy,
        "Vsrs_g"  : Vsrs_g,
        "x"       : x,
        "y"       : y,
    }
    return proc_data


def hs_xarray(
    data: np.ndarray,
    x, y, raman_shift, #wavelength
    x_units='um', y_units='um', rs_units='1/cm', data_units='V', #  wav_units='nm', 
) -> xr.DataArray:
    """
    Convert a 3D numpy array into an xarray.DataArray with dimensions (x, y, raman_shift (wavelength))
        data : (np.ndarray) of shape (nx, ny, nwavelength).
        x, y, raman_shift (wavelength) : (array) Coordinates for each dimension.
        x_units, y_units, rs_units (wavelength_units), data_units : (str) Units 
    :returns: xr.DataArray
    """
    if data.ndim != 3:
        raise ValueError("Input data must be a 3D numpy array (x, y, wavelength).")

    da = xr.DataArray(
        data,
        dims=("x", "y", "raman_shift"),
        coords={
            "x": ("x", x, {"units": x_units}),
            "y": ("y", y, {"units": y_units}),
            # "wavelength": ("wavelength", wavelength, {"units": wav_units}),
            "raman_shift": ("raman_shift", raman_shift, {"units": rs_units})
        },
        name="Vsrs",
        attrs={"units": data_units} 
    )
    return da
    
def unwrap_scan(Vsrs_1d, nx, ny):
    """
    Unwrap 1d array of raster values into (2d (nx,ny) array) without interpolation
    """
    Vsrs_2d = np.reshape(deepcopy(Vsrs_1d), (nx, ny))
    for row in range(Vsrs_2d.shape[0]):
        if row %2 != 0: #odd
            Vsrs_2d[row,:] = Vsrs_2d[row,::-1]
    return Vsrs_2d

  
def find_maxPos(ds, numMax=10, srs_cmap=cm.inferno, vmin=0, vmax=5):
    """
    Finds galvo voltages corresponding to numMax max SRS signals
    Returns (1,numMax) 1d arrays VMx, VMy
    """
    Vsrs_g = ds["Vsrs_g"]
    Vx = ds["Vx"]
    Vy = ds["Vy"]
    M = []
 
    Vsrs_1d = np.reshape(np.nan_to_num(Vsrs_g), (1, Vsrs_g.shape[0]*Vsrs_g.shape[1]))[0]
    sort_i = np.flip(np.argsort(Vsrs_1d))

    for i in range(numMax): #Vsrs_g ordered as (Vy, Vx)
        M.append(tuple(reversed(np.unravel_index(sort_i[i], Vsrs_g.shape))))
    VMx = np.array([Vx[M[i][0]].m for i in range(numMax)])*u.V
    VMy = np.array([Vy[M[i][1]].m for i in range(numMax)])*u.V

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    p0 = ax.pcolormesh(Vx.m, Vy.m, Vsrs_g.m, srs_cmap, vmin, vmax)
    for i in range(numMax):
        ax.scatter(Vx[M[i][0]], Vy[M[i][1]], facecolors='none', edgecolors='w', s=150)
        # print("VMx:", VMx[i])
        # print("VMy:", VMy[i])
    ax.set_aspect("equal")
    return VMx, VMy
    

""" Laser Spot Analysis """
def spotzoom_inds(ds, Dxy=10*u.um):
    """
    Crops widefield laser spot image to size Dxy and returns min and max indices of zoomed in x and y axis
    x_img, y_img: indicies of widefield image cropped to galvo scan area
    """
    ix0,iy0 = [np.nanargmin(np.abs(xx)) for xx in [ds["x_img"],ds["y_img"]] ]  #Find indices of min x and min y values (at center)
    npix_half = np.round((Dxy/2./ds["dx_dpix"]).m_as(u.dimensionless))  #Find (number of pixels)/2 making up Dxy
    ix_min, ix_max = int((ix0 - npix_half)), int((ix0 + npix_half))  #Shift min and max pixel indices to boundary set by Dxy
    iy_min, iy_max = int((iy0 - npix_half)), int((iy0 + npix_half))
    return ix_min, ix_max, iy_min, iy_max


def gaussian(x,w,x0,A):
    return A*np.exp(-2*(x-x0)**2/w**2)


def plot_spotzoom(ds, Dxy=10*u.um,figsize=(4.5,4.5),laser_cmap=cm.winter,
    x_wtext=-3,y_wtext=-3,rc_params=srs_rc_params):
    """
    Estimate spot size from widefield image and laser spot image (in galvo scan ds)
    """
    laser_cmap = transparent_cmap(laser_cmap)
    ix_min_sz, ix_max_sz, iy_min_sz, iy_max_sz = spotzoom_inds(ds, Dxy=Dxy)
    ix0 = int(np.round((ix_min_sz + ix_max_sz)/2.)) - ix_min_sz  #Center around 0
    iy0 = int(np.round((iy_min_sz + iy_max_sz)/2.)) - iy_min_sz  #Center around 0
    X = ds["x_img"][ix_min_sz:ix_max_sz]  #Cropped x axis
    Y = ds["y_img"][iy_min_sz:iy_max_sz]  #Cropped y axis
    Z_bg = ds["laser_spot_img"].min()  #Intensity background
    Z = ds["laser_spot_img"][ix_min_sz:ix_max_sz,iy_min_sz:iy_max_sz] - Z_bg  #Subtract off intensity background of cropped laser spot image
    Z_xcut = (1.0 * Z[:,iy0]) / Z.max()  #X-slice of laser_spot_image normalized to laser spot intensity
    Z_ycut = (1.0 * Z[ix0,:]) / Z.max()  #Y-slice of laser_spot_image normalized to laser spot intensity
    p_x,pcov_x = curve_fit(gaussian,X.m_as(u.um),Z_xcut,[1.0,0.0,1.0])
    p_y,pcov_y = curve_fit(gaussian,Y.m_as(u.um),Z_ycut,[1.0,0.0,1.0])
    wx,x0_fit,I0x = p_x
    wy,y0_fit,I0y = p_y
    x_fit = np.linspace(X.m_as(u.um).min(),X.m_as(u.um).max(),100)
    y_fit = np.linspace(Y.m_as(u.um).min(),Y.m_as(u.um).max(),100)
    Z_xcut_fit = gaussian(x_fit,wx,x0_fit,I0x)
    Z_ycut_fit = gaussian(y_fit,wy,y0_fit,I0y)
    fwhm = np.max(wx,wy)*np.sqrt(2*np.log(2))
    with mpl.rc_context(rc_params):
        fig, ax = plt.subplots(2,2,
        figsize=figsize,
        sharex="col",
        sharey="row",
        gridspec_kw={"wspace":0,"hspace":0,"width_ratios":[1,0.2],"height_ratios":[0.2,1]},
    )
        p0 = ax[1,0].pcolormesh(X,Y,np.fliplr(Z.T),cmap=laser_cmap)
        ax[1,0].set_aspect("equal")
        ly_fit = ax[1,1].plot(Z_ycut_fit,y_fit,'k--')
        lx_fit = ax[0,0].plot(x_fit,Z_xcut_fit,'k--')
        sy = ax[1,1].scatter(Z_ycut,Y)
        sx = ax[0,0].scatter(X,Z_xcut,)
        ax[1,0].set_xlabel("x (μm)")
        ax[1,0].set_ylabel("y (μm)")
        ax[1,0].text(x_wtext,y_wtext,f"x waist: {wx:2.2f} μm"+"\n"+f"y waist: {wy:2.2f} μm")
        ax[1,0].set_title("FWHM: %2.2f μm" %fwhm)
    return fig,ax


def plot_spotzoom_wf(wf_img, Dxy=10*u.um,figsize=(4.5,4.5),laser_cmap=cm.winter,
    x_wtext=-3,y_wtext=-3,rc_params=srs_rc_params):
    """
    Estimate spot size from widefield image and laser spot image (no galvo scan ds necessary)
    """
    x_img, y_img = img_spatial_axes(wf_img)

    #find spot zoom inds
    ix0, iy0 = [np.nanargmin(np.abs(xx)) for xx in
                [x_img, y_img]]  # Find indices of min x and min y values (at center)
    npix_half = np.round((Dxy / 2. / dx_dpix).m_as(u.dimensionless))  # Find (number of pixels)/2 making up Dxy
    ix_min, ix_max = int((ix0 - npix_half)), int(
        (ix0 + npix_half))  # Shift min and max pixel indices to boundary set by Dxy
    iy_min, iy_max = int((iy0 - npix_half)), int((iy0 + npix_half))

    laser_cmap = transparent_cmap(laser_cmap)
    # ix_min_sz, ix_max_sz, iy_min_sz, iy_max_sz = spotzoom_inds(ds, Dxy=Dxy)
    ix0 = int(np.round((ix_min + ix_max)/2.)) - ix_min  #Center around 0
    iy0 = int(np.round((iy_min + iy_max)/2.)) - iy_min  #Center around 0
    X = x_img[ix_min:ix_max]  #Cropped x axis
    Y = y_img[iy_min:iy_max]  #Cropped y axis
    Z_bg = wf_img.min()  #Intensity background
    Z = wf_img[ix_min:ix_max,iy_min:iy_max] - Z_bg  #Subtract off intensity background of cropped laser spot image
    Z_xcut = (1.0 * Z[:,iy0]) / Z.max()  #X-slice of laser_spot_image normalized to laser spot intensity
    Z_ycut = (1.0 * Z[ix0,:]) / Z.max()  #Y-slice of laser_spot_image normalized to laser spot intensity
    p_x,pcov_x = curve_fit(gaussian,X.m_as(u.um),Z_xcut,[1.0,0.0,1.0])
    p_y,pcov_y = curve_fit(gaussian,Y.m_as(u.um),Z_ycut,[1.0,0.0,1.0])
    wx,x0_fit,I0x = p_x
    wy,y0_fit,I0y = p_y
    x_fit = np.linspace(X.m_as(u.um).min(),X.m_as(u.um).max(),100)
    y_fit = np.linspace(Y.m_as(u.um).min(),Y.m_as(u.um).max(),100)
    Z_xcut_fit = gaussian(x_fit,wx,x0_fit,I0x)
    Z_ycut_fit = gaussian(y_fit,wy,y0_fit,I0y)
    fwhm = np.max([wx, wy]) * np.sqrt(2 * np.log(2))
    with mpl.rc_context(rc_params):
        fig, ax = plt.subplots(2,2,
        figsize=figsize,
        sharex="col",
        sharey="row",
        gridspec_kw={"wspace":0,"hspace":0,"width_ratios":[1,0.2],"height_ratios":[0.2,1]},
    )
        p0 = ax[1,0].pcolormesh(X,Y,np.fliplr(Z.T),cmap=laser_cmap)
        ax[1,0].set_aspect("equal")
        ly_fit = ax[1,1].plot(Z_ycut_fit,y_fit,'k--')
        lx_fit = ax[0,0].plot(x_fit,Z_xcut_fit,'k--')
        sy = ax[1,1].scatter(Z_ycut,Y)
        sx = ax[0,0].scatter(X,Z_xcut,)
        ax[1,0].set_xlabel("x (μm)")
        ax[1,0].set_ylabel("y (μm)")
        ax[1, 0].text(x_wtext, y_wtext, f"x waist: {wx:2.2f} μm" + "\n" + f"y waist: {wy:2.2f} μm")
        ax[0, 0].set_title("FWHM: %2.2f μm" % fwhm)
    return fig, ax


def plot_knife_scan(ds_spot, figsize=(4.5,4.5)):
    """
    Extract beam waist from knife edge scan data
    Fits scan data to a gaussian cdf, extracts sigma and mu, then calculates FWHM of associated gaussian
    """
    x = ds_spot["pos_arr"].m
    pd_arr = ds_spot["pd_arr"].m / max(ds_spot["pd_arr"].m)

    if pd_arr[0] > pd_arr[-1]:  # scanning from exposed to covered beam
        f = lambda x, mu, sigma, A, B: B + A * norm(mu, sigma).cdf(-x)
        gauss_fit = lambda x, mu, sigma: norm(mu, sigma).pdf(-x) / np.max(norm(mu, sigma).pdf(-x))
    elif pd_arr[-1] > pd_arr[0]:  # scanning from covered to exposed beam
        f = lambda x, mu, sigma, A, B: B + A * norm(mu, sigma).cdf(x)
        gauss_fit = lambda x, mu, sigma: norm(mu, sigma).pdf(x) / np.max(norm(mu, sigma).pdf(x))

    mu, sigma, A, B = curve_fit(f, x, pd_arr)[0]
    fwhm = 2 * sigma * np.sqrt(2 * np.log(2))
    print("σ = %2.2fμm" % sigma)

    fig, ax = plt.subplots(2, 1, figsize=figsize)
    ax[0].set_title("FWHM = %3.3f μm" % fwhm)
    ax[0].plot(x, pd_arr)
    ax[0].plot(x, f(x, mu, sigma, A, B))
    ax[0].set_xlabel("x [μm]")
    ax[0].set_ylabel("Voltage [V]")
    ax[0].set_xlim((np.min(x), np.max(x)))

    ax[1].plot(x, gauss_fit(x, mu, sigma))
    ax[1].set_xlabel("x [μm]")
    ax[1].set_ylabel("Normalized [a.u.]")
    ax[1].set_xlim((np.min(x), np.max(x)))

    return fig


""" Widefield Image Pre-plotting Processing """
def img_max_pixel_inds(img, threshold=100):
    """
    Return (x,y) indices for laser spot location. If no laser spot recognized (max value below threshold),
    return center of image
    """
    if np.max(img) > threshold:
        max_inds = np.unravel_index(np.argmax(img), img.shape)
    else:
        max_inds = (np.round(img.shape[0]/2), np.round(img.shape[1]/2))
    return max_inds


def img_spatial_axes(laser_spot_img, dx_dpix=dx_dpix):
    """
    Return x axis and y axis (in microns) of laser spot widefield image, centered around laser spot
    :param laser_spot_img: [2d array]
    :param dx_dpix: pixel to position conversion
    :return: x_img, y_img [1d arrays]
    """
    x_pix_laser, y_pix_laser = img_max_pixel_inds(laser_spot_img)   #Find indices of laser spot
    npix_x,npix_y = laser_spot_img.shape    #Dimensions of laser spot image
    x_img, y_img = dx_dpix*(np.arange(npix_x)-x_pix_laser), dx_dpix*(np.arange(npix_y)-y_pix_laser) #Shift image center to laser spot position and convert pixels to microns 
    return x_img, y_img


def img_spatial_axes_nolaser(img, dx_dpix=dx_dpix):
    """
    Return x axis and y axis (in microns) of widefield image without a laser spot - no centering
    :param img: [2d array] from wf_image()
    :param dx_dpix: pixel to position conversion
    :return: x_img, y_img
    """
    npix_x, npix_y = img.shape  # Dimensions of widefield image
    x_img, y_img = dx_dpix * (np.arange(npix_x)), dx_dpix * (np.arange(npix_y))
    return x_img, y_img


def wf_img_inds(ds):
    """
    Return min and max indices of widefield image cropped to galvo scan image area
    """
    i_xmax = np.nanargmin(np.abs(ds['x_img'] - ds['x'].max()))
    i_xmin = np.nanargmin(np.abs(ds['x_img'] - ds['x'].min()))
    i_ymax = np.nanargmin(np.abs(ds['y_img'] - ds['y'].max()))
    i_ymin = np.nanargmin(np.abs(ds['y_img'] - ds['y'].min()))
    return i_xmax, i_xmin, i_ymax, i_ymin


def scan_volt_to_wf_inds(Vx, Vy, laser_spot_img, dx_dpix=dx_dpix):
    """
    Given Vx, Vy scan voltage 1d arrays, convert to x, y 1d position arrays.
    Return widefield img min and max indices corresponding to scan area
    :return: i_xmax, i_xmin, i_ymax, i_ymin
    """
    x = ((Vx - Vx0) * dx_dVx).to(u.um)
    y = ((Vy - Vy0) * dy_dVy).to(u.um)

    x_img, y_img = img_spatial_axes(laser_spot_img) #find indices of laser spot

    i_xmax = np.nanargmin(np.abs(x_img - x.max()))
    i_xmin = np.nanargmin(np.abs(x_img - x.min()))
    i_ymax = np.nanargmin(np.abs(y_img - y.max()))
    i_ymin = np.nanargmin(np.abs(y_img - y.min()))
    return i_xmax, i_xmin, i_ymax, i_ymin


""" Plotting """
def transparent_cmap(cmap):
    """
    Generate colormap `cmap_tr` with graded transparency (transparent at 0, opaque
    at maximum) from input colormap `cmap` for 2D heatmap overlays
    """
    cmap_tr = cmap(np.arange(cmap.N))
    cmap_tr[:,-1] = np.linspace(0, 1, cmap.N)
    cmap_tr = ListedColormap(cmap_tr)
    return cmap_tr


def plot_scan_data(ds,wf_cmap=cm.gray,laser_cmap=cm.Reds, srs_cmap=cm.inferno, vmin=None, vmax=None):
    """
    Plot 2x1 subplots with [0] laser spot superimposed on cropped widefield image, and [1] SRS image
    :param ds: from collect_scan()
    :return: fig with (2) subplots
    """
    laser_cmap = transparent_cmap(laser_cmap)
    fig, ax = plt.subplots(2,1, figsize = (10,10))
    
    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    x_off = 0#10
    y_off = 0#40
    i_xmax += x_off
    i_xmin += x_off
    i_ymin += y_off
    i_ymax += y_off
 
    # [0] Laser spot + cropped widefield image
    im0 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                              ds["wf_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=wf_cmap)
    im1 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                              ds["laser_spot_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=laser_cmap)
    cb0 = plt.colorbar(im1, ax=ax[0])
    ax[0].set_aspect("equal")

    # [1] SRS (galvo) image
    p0 = ax[1].pcolormesh(ds["y"].m, ds["x"].m, np.flipud(np.transpose(ds["Vsrs_g"].m)), cmap=srs_cmap, vmin=vmin, vmax=vmax)
    cb1 = plt.colorbar(p0, ax=ax[1])
    ax[1].set_aspect("equal")

    plt.show()
    return fig


def plot_hyperspectral_scan(ds, Vsrs_hs: xr.DataArray, wavnum, wf_cmap=cm.gray, laser_cmap=cm.Reds, srs_cmap=cm.inferno, vmin=None, vmax=None, wf_offsets: dict=None, plot_wf=True):
    """
    Plot 2x1 subplots with [0] laser spot superimposed on cropped widefield image, and [1] SRS image
    :param ds: from collect_hyperspectral_scan()
    :param wavnum (unitful Quantity): wavenumber where to plot hyperspectral image
    :return: fig with (2) subplots
    """
    laser_cmap = transparent_cmap(laser_cmap)
    
    offset = 0*u.V
    
    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    if wf_offsets is not None:
        x_off = wf_offsets["x_off"]
        y_off = wf_offsets["y_off"]
    else:
        x_off = 0 #10
        y_off = 0 #40
        
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    i_xmax += x_off
    i_xmin += x_off
    i_ymin += y_off
    i_ymax += y_off
    
    # 2d slice in xarray
    # if spec_ind.u == 1/u.cm:
    #     Vsrs_2d = Vsrs_hs.sel(wavelength=(Vsrs_hs["raman shift"]==spec_ind), method="nearest").squeeze()
    # elif spec_ind.u == u.V:
    #     Vsrs_2d = Vsrs_hs.sel(wavelength=(Vsrs_hs["HV"]==spec_ind), method="nearest").squeeze()
    # elif spec_ind.u == u.nm:
    #     Vsrs_2d = Vsrs_hs.sel(wavelength=spec_ind, method="nearest")
    # else:
    #     raise ValueError("Invalid spec_ind - must have units (1/u.cm, u.V, or u.nm)")
    Vsrs_2d = np.asarray(Vsrs_hs.sel(raman_shift=wavnum, method="nearest")) 
    # Vsrs_2d = (Vsrs_2d / 10 + offset).to(u.V).m * ds["sens_lia"].to(u.V).m
    
    if plot_wf:
        fig, ax = plt.subplots(2, 1, figsize=(10,10))
        # [0] Laser spot + cropped widefield image
        im0 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                                ds["wf_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=wf_cmap)
        im1 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                                ds["laser_spot_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=laser_cmap)
        cb0 = plt.colorbar(im1, ax=ax[0])
        ax[0].set_aspect("equal")

        # [1] SRS (galvo) image
        p0 = ax[1].pcolormesh(Vsrs_hs["y"], Vsrs_hs["x"], np.flipud(np.transpose(Vsrs_2d)), cmap=srs_cmap, vmin=vmin, vmax=vmax)
        cb1 = plt.colorbar(p0, ax=ax[1])
        ax[1].set_aspect("equal")
    else:
        fig, ax = plt.subplots(1,1,figsize=(4,4))
        p0 = ax.pcolormesh(Vsrs_hs["y"], Vsrs_hs["x"], np.flipud(np.transpose(Vsrs_2d)), cmap=srs_cmap, vmin=vmin, vmax=vmax)
        cb1 = plt.colorbar(p0, ax=ax)
        ax.set_aspect("equal")
    
    plt.show()
    return fig

def plot_pixel_spec(Vsrs_hs, x, y, ax=None, fig=None):
    """
    Plot the spectra at the specified x,y cooridnate
    """
    spec = Vsrs_hs.sel(x=x, y=-y, method="nearest")
    pk_shift = spec.idxmax(dim="raman_shift")
    print(f"Peak at {pk_shift.values} 1/cm")
    
    if ax is None:
        fig, ax = plt.subplots(1,1, figsize=(6,4), tight_layout=True)
    ax.plot(Vsrs_hs["raman_shift"], spec)
    ax.set_xlabel("Raman Shift ($cm^{-1}$)")
    ax.set_ylabel("Voltage (V)")
    return fig


def plot_widefield_img(img, wf_cmap=cm.gray):
    """
    Plot widefield image without scan data or laser
    :param img: from wf_image())
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes_nolaser(img)
    fig, ax = plt.subplots()
    im0 = ax.pcolormesh(y_img, x_img, img[::-1,:], cmap=wf_cmap)
    ax.set_aspect("equal")
    plt.show
    return fig


def plot_laser_widefield_img(wf_img, laser_spot_img, wf_cmap=cm.gray, laser_cmap=cm.Reds):
    """
    Plot full widefield image with laser spot (no scan data), axis centered around laser spot
    :param img, laser_spot_image: from wf_and_laser_spot_images()
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes(wf_img)
    laser_cmap = transparent_cmap(laser_cmap)

    fig, ax = plt.subplots()
    im0 = ax.pcolormesh(y_img, x_img, wf_img[::-1,:], cmap=wf_cmap)
    im1 = ax.pcolormesh(y_img, x_img, laser_spot_img[::-1,:], cmap=laser_cmap)
    cb1 = plt.colorbar(im1, ax=ax)
    ax.set_aspect("equal")
    plt.show
    return fig


def plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.gray, laser_cmap=cm.Reds):
    """
    Plot widefield image with laser spot (before acquiring scan data) cropped to scan area, axis centered around laser spot
    :param laser_spot_img: from laser_spot_images(); Vx, Vy: from scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes(laser_spot_img)
    
    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    i_xmax, i_xmin, i_ymax, i_ymin = scan_volt_to_wf_inds(Vx, Vy, laser_spot_img)
    x_off = 0#10
    y_off = 0#40
    i_xmax += x_off
    i_xmin += x_off
    i_ymin += y_off
    i_ymax += y_off
    
    fig, ax = plt.subplots()
    im0 = ax.pcolormesh(y_img[i_ymin:i_ymax], x_img[i_xmin:i_xmax],
                              np.flipud(wf_img[i_xmin:i_xmax, i_ymin:i_ymax]), cmap=wf_cmap)
    im1 = ax.pcolormesh(y_img[i_ymin:i_ymax], x_img[i_xmin:i_xmax], np.flipud(laser_spot_img[i_xmin:i_xmax, i_ymin:i_ymax]), cmap=transparent_cmap(laser_cmap))
    
    cb1 = plt.colorbar(im1, ax=ax)
    ax.set_aspect("equal")
    plt.show()
    return fig


""" Saving Images """
def save_single_img(X,Y,Z,cmap,fname,fpath=False,xlabel="x (μm)",ylabel="y (μm)",cbar=False,cbar_label=None,figsize=(4,6),format='png',rc_params=srs_rc_params,**kwargs):
    """
    Given X,Y,Z arrays, plot and save figure
    """
    with mpl.rc_context(rc_params):
        fig,ax = plt.subplots(1,1) #,figsize=figsize) #**kwargs)
        ps = [ax.pcolormesh(X,Y,zz,cmap=ccmm,vmin=np.nanmin(zz),vmax=np.nanmax(zz)) for (zz,ccmm) in zip(Z,cmap) ]
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if cbar:
            cb = plt.colorbar(ps[-1],ax=ax,label=cbar_label)
        ax.set_aspect("equal")
        # fig.tight_layout()
        if fpath:
            fname=os.path.normpath(os.path.join(fpath,fname))
        # plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
        #     orientation='portrait', papertype=None, format=format,
        #     transparent=True, bbox_inches=None, pad_inches=0.5)
        plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
            orientation='portrait', transparent=True, bbox_inches=None, pad_inches=0.5)
    return fig


def save_scan_images(ds,fname,fpath=False,wf_cmap=cm.binary_r,laser_cmap=cm.winter,srs_cmap=cm.inferno,rc_params=srs_rc_params,format='png',**kwargs):
    """
    Save data and figs for following images:
    (1) Widefield image
    (2) Laser spot superimposed on widefield image
    (3) Widefield image zoomed 
    (4) Laser spot superimposed on cropped widefield image
    (5) SRS image
    """

    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    x_off = 0#10
    y_off = 0#40
    i_xmax += x_off
    i_xmin += x_off
    i_ymin += y_off
    i_ymax += y_off
    
    laser_cmap = transparent_cmap(laser_cmap)
    img_data = [
#         (ds["y_img"].m, ds["x_img"].m, (np.flipud(ds["wf_img"]), ), (wf_cmap,),"wf_"+fname+"."+format),
        (ds["y_img"].m, ds["x_img"].m, (np.flipud(ds["wf_img"]), np.flipud(ds["laser_spot_img"])),(wf_cmap,laser_cmap),"wfls_"+fname+"."+format),
#         (ds["y_img"][i_ymin:i_ymax].m, ds["x_img"][i_xmin:i_xmax].m, (np.flipud(ds["wf_img"][i_xmin:i_xmax,i_ymin:i_ymax]), ), (wf_cmap,), "wfzoom_"+fname+"."+format),
        (ds["y_img"][i_ymin:i_ymax].m, ds["x_img"][i_xmin:i_xmax].m, (np.flipud(ds["wf_img"][i_xmin:i_xmax,i_ymin:i_ymax]), np.flipud(ds["laser_spot_img"][i_xmin:i_xmax,i_ymin:i_ymax])), (wf_cmap,laser_cmap), "wflszoom_"+fname+"."+format),
        (ds["y"].m, ds["x"].m, (np.flipud(np.transpose(ds["Vsrs_g"].m)), ), (srs_cmap,), "srs_"+fname+"."+format),
    ]
    for X,Y,Z,cmap,fname in img_data:
         save_single_img(X,Y,Z,cmap,fname,fpath=fpath,xlabel="x (μm)",ylabel="y (μm)",cbar=False,cbar_label=None,rc_params=rc_params,format=format,**kwargs)
    return

def save_wf_img(wf_img, fname, cmap = cm.gray, fpath=False):
    """ Plot and save single widefield image"""
    plot_widefield_img(wf_img)
    x_img,y_img = img_spatial_axes(wf_img)
    X = x_img
    Y = y_img
    Z = (wf_img,)
    save_single_img(Y, X, Z, cmap=(cmap,), fname=fname, fpath=fpath, xlabel="x (μm)", ylabel="y (μm)", cbar=False, cbar_label=None)
    return

def save_mat(fname, sample_dir):
    """ Convert dataset (ds_scan (galvo scan), ds_spot (knife scan), ds_spec (spectra)) to .mat file
    Input: .h5 file -> saves .mat file with same name as .h5 file
    """

    ds = load_data_from_file(sample_dir, fname)
    mat_fname = fname[:-2] + 'mat'

    file_dir = os.path.join(data_dir, sample_dir, mat_fname)
    print("saving data to: ")
    print(file_dir)

    if 'GalvoScan' in fname:
        ds_scan = ds
        data = {'wf_img': ds_scan['wf_img'],
                'laser_spot_img': ds_scan['laser_spot_img'],
                'dx_dpix': ds_scan['ds_dpix'].to(u.m).m,
                'x_img': ds_scan['x_img'].to(u.m).m,
                'y_img': ds_scan['y_img'].to(u.m).m,
                'dx_dVx': ds_scan['dx_dVx'].to(u.m/u.V).m,
                'dx_dVy': ds_scan['dx_dVy'].to(u.m/u.V).m,
                'Vx': ds_scan['Vx'].m,
                'Vy': ds_scan['Vy'].m,
                'Vsrs_g': ds_scan['Vsrs_g'].m,
                'x': ds_scan['x'].to(u.m).m,
                'y': ds_scan['y'].to(u.m).m
        }
    elif 'knifeScan' in fname:
        ds_spot = ds
        data = {'scan_length': ds_spot['scan_length'].to(u.m).m,
         'axis': ds_spot['axis'],
         'step_size': ds_spot['step_size'].to(u.m).m,
         'num_avg': ds_spot['num_avg'],
         'pos_arr': ds_spot['pos_arr'].to(u.m).m,
         'pd_arr': ds_spot['pd_arr'].m
         }
    elif 'Spectra' in fname:
        ds_spec = ds
        if 'SpectraSweep' in fname:
            data=  {'t_lia': ds_spec['t_lia'].to(u.s).m,
             'fsamp': ds_spec['fsamp'].m,
             'wav_start': ds_spec['wav_start'].to(u.m).m,
             'wav_stop': ds_spec['wav_stop'].to(u.m).m,
             't_sweep': ds_spec['t_sweep'].to(u.s).m,
             'fixed_wav': ds_spec['fixed_wav'].to(u.m).m,
             'spec': ds_spec['spec'].m,
             'wav_mon': ds_spec['wav_mon'].m
            }
        else:
            data = {'num_avg': ds_spec['num_avg'],
             'fsamp': ds_spec['fsamp'].m,
             'wav_start': ds_spec['wav_start'].to(u.m).m,
             'wav_stop': ds_spec['wav_stop'].to(u.m).m,
             'dwav': ds_spec['Δwav'].to(u.m).m,
             'wav_settle_time': ds_spec['wav_settle_time'].m,
             'wavelengths': ds_spec['wavelengths'].to(u.m).m,
             'fixed_wav': ds_spec['fixed_wav'].to(u.m).m,
             'raman_shift': ds_spec['raman_shift'].m,
             'spec': ds_spec['spec'].m,
             'tap_power': ds_spec['tap_power'].m
             }
    io.savemat(file_dir, data)
    return

def load_data_from_file(sample_dir, filename):
    """
    Load saved hd5f file and return ds
    """
    file_dir = os.path.join(data_dir, sample_dir, filename)
    ds = load_hdf5(fpath=file_dir)
    return ds

"""Calibration Curves"""
def generate_wavvolt(voltage_list, osa_settings, num_avg, sample_dir=None, name=None, delayvolt_file=delayvolt_file):
    """
    Sweeps daq2 + HVA voltages to generate VCSEL tunings curve, reads OSA spectrum
    :param: 
        - voltage_list - list of VCSEL voltages
        - osa_settings - dict of RBW, wav_start, wav_stop, ref_level
        - num_avg - # of voltage reads to average
    :return: ds
    """
    #Initialize to first voltages in sweep
    ramp_VCSEL(voltage_list[0])
    
    #Load delayvolt
    b = io.loadmat(delayvolt_file) # Load delayvolt_file
    VOA_volt = b['VOA_est_interp'][0]*u.V
    VCSEL_volt = b['V_MEMSinterp'][0]*u.V 

    #Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=calib_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='wavvoltdata',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)

    # Configure OSA
    osa = instrument("hp_osa", reopen_policy='reuse')
    osa.set_resolution_bandwidth(osa_settings["rbw"])
    osa.set_reference_level(osa_settings["ref_level"])
    span = osa_settings["wav_stop"] - osa_settings["wav_start"]
    center_wl = np.round(span/2) + osa_settings["wav_start"]
    osa.set_wavelength_span(span)
    osa.set_center_wavelength(center_wl)
    
    # sweep_time = osa.get_sweep_time()
    wavelength, _ = osa.get_spectrum()
    trace_len = wavelength.shape[0]
    
    # Initialize lists for data save
    meas_volt_list = []
    meas_wavmon_list = []
    pk_wl_list = []
    spectrum_array = np.array(np.zeros((len(voltage_list), int(trace_len))))

    # Sweep power supply voltage and get osa trace
    for ind, volt in enumerate(voltage_list):
        # find VOA voltage for VCSEL voltage set
        voa_ind = np.argmin(np.abs(VCSEL_volt.m - volt.m))
        VOA_Vset = VOA_volt[voa_ind]
  
        print(f'VOA Voltage set: {VOA_Vset}')
        print('VCSEL Voltage set: %.4f V...' % volt.to(u.V).m)
        # Set the voltage
        # ramp_VCSEL(volt)
        ch_VCSEL_MEMS.write(HVA_to_daq(volt))
        ch_VOA.write(VOA_Vset)

        # Wait [s]
        time.sleep(1.5)
        meas_volt_rep = []
        meas_wavmon_rep = []
        for iter in range(num_avg):
            meas_volt = Vmon_to_HVA(ch_HVA_Vmon.read())
            meas_wavmon = ch_wav_mon.read()
            # time.sleep(0.3)
            meas_volt_rep.append(meas_volt.to(u.V).m) #[V]
            meas_wavmon_rep.append(meas_wavmon.to(u.V).m) #[V]
        # print(meas_volt_rep)
        meas_volt_list.append(np.mean(meas_volt_rep)) #[V]
        meas_wavmon_list.append(np.mean(meas_wavmon_rep)) #[V]
        print('Voltage measured: %0.4f V' % meas_volt_list[ind])
        
        # Wait [s]
        # time.sleep(0.5)
        # time.sleep(sweep_time.m)

        #Read osa spectrum and store in wavelength_array
        _, spectra = osa.get_spectrum()
        # time.sleep(sweep_time.m)
        spectrum_array[ind, :] = np.reshape(spectra, (1, int(trace_len)))
        pk_ind = np.argmax(spectrum_array[ind,:])
        pk_wl_list.append(wavelength[pk_ind].to(u.m).m)
    spectrum_array = spectrum_array * u.dimensionless
    meas_volt_list = meas_volt_list * u.V
    meas_wavmon_list = meas_wavmon_list * u.V
    pk_wl_list = pk_wl_list * u.m
    
    print(np.shape(spectrum_array))
    print('Finished voltage sweep')
    print('-----------------------------')
    dump_hdf5(osa_settings, fpath, open_mode='x')
    wavvolt_data = {
         'num_avg'          : num_avg,
         'voltage_list'     : voltage_list,
         'meas_volt_list'   : meas_volt_list,
         'meas_wavmon_list' : meas_wavmon_list,
         'pk_wl_list'       : pk_wl_list,
         'spectrum_array'   : spectrum_array,
         'wavelength'       : wavelength
         }
    dump_hdf5(wavvolt_data, fpath)

    ds = load_hdf5(fpath=fpath)

    # Save spectrum data to .mat file
    mat_fname = fpath[:-2] + 'mat'
    file_dir = os.path.join(sample_dir, mat_fname)
    data = {
            'rbw'               : osa_settings['rbw'].to(u.m).m,
            'ref_level'         : osa_settings['ref_level'].m,
            'num_avg'           : num_avg,
            'voltage_list'      : voltage_list.to(u.V).m,
            'spectrum_array'    : spectrum_array.m,
            'wavelength'        : wavelength.to(u.m).m,
            'meas_volt_list'    : meas_volt_list.to(u.V).m,
            'meas_wavmon_list'  : meas_wavmon_list.to(u.V).m,
            'pk_wl_list'        : pk_wl_list.to(u.m).m
            }
    io.savemat(file_dir, data)

    # Save wavvolt file
    # wavvolt_filename = os.path.join(sample_dir, "wavvolt_" + name)
    # save_wavvolt(name, np.array(meas_volt_list), np.array(pk_wl_list))
    return ds
    

def save_wavvolt(ds, invalid_volt: tuple = None, f_interp=5000, name=None,sample_dir=None, cmap=cm.magma, smooth_param=None):
    """
    Interpolates voltage vs peak wavelength curve, saves wavvolt file with variables:
    -ds: dataset from generate_wavvolt()
    -volt_interp: interpolated (measured) voltage
    -wav_interp: interpolated wavelength
    -invalid_volt: (volt_start, volt_end) range of voltages to exclude
    """
    volt = ds["meas_volt_list"].to(u.V).m
    peak_wl = ds["pk_wl_list"].to(u.m).m
    spectrum_array = ds["spectrum_array"].m
    wavelength = ds["wavelength"].m

    volt_interp = np.linspace(volt[0], volt[-1], f_interp) * u.V
    peak_interp = np.interp(volt_interp.m, volt, peak_wl) * u.m

    if invalid_volt is not None:
        invalid_index = (volt_interp >= invalid_volt[0]) & (volt_interp <= invalid_volt[1])
        peak_interp[invalid_index] = np.nan
        # volt_interp = volt_interp[valid_index]
      
    colors = cmap(np.linspace(0, 0.95, spectrum_array.shape[0]))

    fig,ax = plt.subplots(1,2,figsize=(10,3.5), gridspec_kw={"wspace":0.5,"hspace":0}) #,figsize=figsize) #**kwargs)
    for ind in range(spectrum_array.shape[0]):
        ax[0].plot(wavelength, spectrum_array[ind,:], color=colors[ind])
    ax[0].set_xlabel("Wavelength (nm)")
    ax[0].set_ylabel("Power (dBm)")
    ax[1].plot(volt_interp, peak_interp.to(u.nm))
    if smooth_param is not None:
        peak_interp=savgol_filter(peak_interp.m, window_length=smooth_param, polyorder=3, mode='interp')*u.m
        ax[1].plot(volt_interp, peak_interp.to(u.nm))
    ax[1].set_xlabel("Voltage (V)")
    ax[1].set_ylabel("Wavelength (nm)")
    
    if name is not None:
        time_tuple = time.localtime()
        wavvolt_filename = "wavvolt_HVCALIB_%s_%d-%d-%d.mat" % (
            name,
            time_tuple[0],
            time_tuple[1],
            time_tuple[2])
        wavvolt_filename = os.path.join(sample_dir, wavvolt_filename)
        io.savemat(wavvolt_filename, {'volt_select': volt,
                                     'wav_select': peak_wl,
                                      'volt_interp': volt_interp.to(u.V).m,
                                      'peak_interp': peak_interp.to(u.m).m
                                     })


""" Spectral Acquisition """
def initialize_osa(wav_start=1030*u.nm, wav_stop=1280*u.nm, rbw=0.1*u.nm, ref_level=-30*u.dimensionless):
    osa = instrument("hp_osa", reopen_policy='reuse')
    osa.set_resolution_bandwidth(rbw)
    osa.set_reference_level(ref_level)
    span = wav_stop - wav_start
    center_wl = np.round(span/2) + wav_start
    osa.set_wavelength_span(span)
    osa.set_center_wavelength(center_wl)
    return osa
    

def check_valid_wavelength(wavelength_set, wavvolt_file=wavvolt_file):
    """
    For Praevium VCSEL - Checks if set wavelength (scalar) is valid given the wavvolt tuning curve 
    Returns bool 
    """
    # Load wavvolt_file
    a = io.loadmat(wavvolt_file)
    wav_calib = (a['peak_interp'][0] * u.m).to(u.nm)

    valid = False
    if (wavelength_set < np.min(wav_calib)) or (wavelength_set > np.max(wav_calib)) or (
                    wavelength_set > wav_calib[0] and wavelength_set < wav_calib[-1]):
        print(f"Wavelength out of range: {wavelength_set:3.2f}")
    else: 
        valid = True
    return valid
    

def generate_valid_sweep(wav_start, wav_stop, Δwav, wavvolt_file=wavvolt_file):
    """
    For Praevium VCSEL - Checks start and stop wavelengths and generates array of valid wavelengths (omits middle gap)
    """
    # Generate linear array of nominal wavelengths
    wl_arr = np.arange(wav_start.to(u.nm).m, wav_stop.to(u.nm).m + Δwav.to(u.nm).m, Δwav.to(u.nm).m) * u.nm
    valid_wl_arr = []

    for wl in wl_arr:
        if check_valid_wavelength(wl, wavvolt_file=wavvolt_file):
            valid_wl_arr.append(wl.m)
        else:
            pass

    return valid_wl_arr * u.nm
    
    
def HVA_to_daq(HVA_volt, atten=0.09125, volt_limit=88.6*u.V, offset=0.14*u.V):
    # Convert the output HVA voltage (to VCSEL MEMS) to the daq input to the HVA
    # atten - from voltage divider between daq and HVA
    # V_gain = 98.3 # For Trek 2210 (measured)
    V_gain = 98.16
    if HVA_volt > volt_limit:
        print(f"Vset= {HVA_volt:3.2f} exceeds Vlim= {volt_limit:3.2f}. Setting to {volt_limit} V.")
        HVA_volt = volt_limit #0*u.V
    daq_volt = (HVA_volt - offset) / V_gain / atten 
    return daq_volt

def Vmon_to_HVA(daq_volt, calib_offset=0.0023*u.V, scale=100.2): 
    #Convert daq read of Vmon to HVA output (calib_factor corrects for daq analog input negative offset (not constant, but set to 0V offset))
    V_HV = (daq_volt+calib_offset)*scale
    # V_HV = daq_volt*scale*calib_factor
    return V_HV

def HVA_to_wavelength(HVA_set, wavvolt_file=wavvolt_file):
    # Given a HVA set (array or single voltage), find the VCSEL wavelength
    a = io.loadmat(wavvolt_file) # Load wavvolt_file
    wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
    volt_calib = a['volt_interp'][0]*u.V
    tol = 0.5*u.V

    if np.isscalar(HVA_set.m):
        HVA_set = np.array([HVA_set.m])*u.V
    
    VCSEL_wav = np.zeros((1,HVA_set.shape[0]))

    for i, volt in enumerate(HVA_set.to(u.V).m):
        if np.min(np.abs(volt - volt_calib.m)) > tol.m:
            # raise ValueError("Voltage out of range")
            print(f"Voltage {volt} V out of range")
        else:
            ind = np.argmin(np.abs(volt - volt_calib.m))
            VCSEL_wav[i] = wav_calib[ind].to(u.nm).m
        
    return VCSEL_wav * u.nm


def parse_wav_delay(wavelength_set, wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, max_Vstep=1*u.V):
    # Given input wavelength(s), return corresponding MEMS and VOA voltages, daq set to HVA for MEMS voltage
    # Input: array or scalar (with units), sort array by increasing MEMS voltage
    # Output wavelength_set: sorted in order of increasing voltage (same as HV_set)
    a = io.loadmat(wavvolt_file) # Load wavvolt_file
    wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
    volt_calib = a['volt_interp'][0]*u.V
        
    if delayvolt_file is None:
        # No delayvolt_file (CW sweep), set VOA to 5V
        VOA_volt = np.ones(wav_calib.shape) * 5*u.V
        VCSEL_volt = volt_calib
    else:
        b = io.loadmat(delayvolt_file) # Load delayvolt_file
        VOA_volt = b['VOA_est_interp'][0]*u.V
        VCSEL_volt = b['V_MEMSinterp'][0]*u.V 

    # If input scalar, put into array
    if np.isscalar(wavelength_set.m):
        wavelength_set = np.array([wavelength_set.m])*u.nm

    # Initialize arrays
    VOA_Vset = [] # VOA Voltage
    HVA_Vset = [] # VMEMS Voltage
    HVA_Vunsort = [] # Discontinuous MEMS voltage from linear wavelength sweep
    daq_HVset = [] # MEMS Voltage (input to HVA)
    wav_full = [] # Wavelength set after filling in voltage gaps

    # Map wavelength to HVA voltage (VCSEL MEMS)
    for i, wav in enumerate(wavelength_set):
        if check_valid_wavelength(wav, wavvolt_file): #somewhat redundant, if input wavelength_set already checked by generate_valid_sweep()
            ind = np.argmin(np.abs(wav - wav_calib))
            HVA_Vunsort.append(volt_calib[ind].to(u.V).m)
        else:
            raise ValueError("Set value outside range")
    HVA_Vunsort = np.array(HVA_Vunsort)
    
    # Sort wavelengths by increasing voltage
    Vsort_ind = np.argsort(HVA_Vunsort)
    HVA_Vsort = HVA_Vunsort[Vsort_ind] * u.V
    # wav_sort = wavelength_set[Vsort_ind]
    
    #If wavelength_set crosses discontinuity, pad to minimize discontinuity
    wav_disc = wav_calib[-1]
    if (wav_disc > wavelength_set[0]) and (wav_disc < wavelength_set[-1]):
        if HVA_Vsort[-1].m < volt_calib[-1].m:
            print(f'Filling wavelength discontinuity')
            HVA_Vsort = np.append(HVA_Vsort.m, volt_calib[-1].m) * u.V
    
    #If step between voltages exceeds max_Vstep, fill increments with max Vstep
    if HVA_Vsort.shape[0] > 1:
        for i in range(HVA_Vsort.shape[0] - 1):
            if np.abs(HVA_Vsort[i+1] - HVA_Vsort[i]) > max_Vstep:
                if HVA_Vsort[i+1] > HVA_Vsort[i]:
                    Vfill = np.arange(HVA_Vsort[i].to(u.V).m, HVA_Vsort[i+1].to(u.V).m, max_Vstep.to(u.V).m)
                elif HVA_Vsort[i+1] < HVA_Vsort[i]:
                    Vfill = np.arange(HVA_Vsort[i].to(u.V).m, HVA_Vsort[i+1].to(u.V).m, -max_Vstep.to(u.V).m)
                HVA_Vset.extend(Vfill)
            else:
                HVA_Vset.append(HVA_Vsort[i].to(u.V).m)
        HVA_Vset.append(HVA_Vsort[-1].to(u.V).m)
    else:
        HVA_Vset.append(HVA_Vsort.m)
    HVA_Vset = HVA_Vset*u.V
    
    #Correct for error in HVA set and measured voltage
    # HVA_Vset = calibrate_HVAset(HVA_Vset, calib_fpath=HVAcalib_file, verbose=False)

    # Scale HVA voltage to daq output voltage and Remap new HVA_Vset to wavelength, Find VOA voltage corresponding to VCSEL MEMS voltage set
    for i, HVA_volt in enumerate(HVA_Vset):
        daq_HVset.append(HVA_to_daq(HVA_volt).to(u.V).m)
        ind = np.argmin(np.abs(HVA_volt - volt_calib)) #for wavvolt
        wav_full.append(wav_calib[ind].to(u.nm).m)
        ind1 = np.argmin(np.abs(HVA_volt.m - VCSEL_volt.to(u.V).m)) #for delayvolt
        VOA_Vset.append(VOA_volt[ind1].to(u.V).m) 
    daq_HVset = daq_HVset * u.V
    # wavelength_set = np.sort(wav_full)*u.nm  #removed 10/25/25
    wavelength_set = wav_full * u.nm
    VOA_Vset = VOA_Vset * u.V
        
    return daq_HVset, VOA_Vset, HVA_Vset, wavelength_set
   

def set_VCSEL_wavelength(wavelength_set, wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file):
    # Set VCSEL wavelength with VOA delay compensation - Use ramp_VCSEL instead (safer)
    # Input - number with units
    daq_HVset, VOA_Vset, HVA_Vset, wavelength_set = parse_wav_delay(wavelength_set, wavvolt_file, delayvolt_file)
    # Write daq voltages 
    ch_VCSEL_MEMS.write(daq_HVset[0][0])
    ch_VOA.write(VOA_Vset[0])


def ramp_VCSEL(wav_or_V_set, ΔV=0.1*u.V, wait_time=100*u.us):
    # Gentler wavelength set than set_VCSEL_wavelength - Reads current MEMS voltage, ramps VCSEL wavelength with delay compensation
    # Input - wavelength or HVA voltage scalar with units
    current_daqV = ch_VCSEL_MEMS.read()
    current_VOAV = ch_VOA.read()
        
    if wav_or_V_set.u == u.V:  # Set value given in volts
        wav_or_V_set = HVA_to_wavelength(wav_or_V_set)[0]

    daq_HVset, VOA_Vset, _, _ = parse_wav_delay(wav_or_V_set, wavvolt_file, delayvolt_file)
    daq_HVset = daq_HVset[0] # take out of array
    VOA_Vset = VOA_Vset[0] # take out of array

    # Generate array of daq voltages (VOA and HV) for ramp
    if current_daqV == daq_HVset:
        pass
    else:
        if current_daqV > daq_HVset: #ramp down
            daq_HVarr = np.arange(current_daqV.to(u.V).m, daq_HVset.to(u.V).m, -ΔV.to(u.V).m)
        elif current_daqV < daq_HVset:  #ramp up
            daq_HVarr = np.arange(current_daqV.to(u.V).m, daq_HVset.to(u.V).m, ΔV.to(u.V).m)
        daq_HVarr = daq_HVarr * u.V
        daq_VOAarr = np.linspace(current_VOAV, VOA_Vset, daq_HVarr.shape[0])
        # Ramp voltage 
        for ind, volt in enumerate(daq_HVarr):
            ch_VCSEL_MEMS.write(volt) 
            ch_VOA.write(daq_VOAarr[ind])
            time.sleep(wait_time.to(u.s).m)
        #Final wavelength set (should be close, if not already there)
        set_VCSEL_wavelength(wav_or_V_set)


def turn_VCSEL_off(ΔV=0.1*u.V):
    # Ramps MEMS voltage to 0 and VOA voltage to 5V
    current_daqV = ch_VCSEL_MEMS.read()
    current_VOAV = ch_VOA.read()

    VOA_off = 5*u.V
    daq_HVoff = 0*u.V

    if current_daqV == daq_HVoff:
        pass
    else:
        if current_daqV > daq_HVoff: #ramp down
            daq_HVarr = np.arange(current_daqV.to(u.V).m, daq_HVoff.to(u.V).m, -ΔV.to(u.V).m)
        elif current_daqV < daq_HVoff:  #ramp up
            daq_HVarr = np.arange(current_daqV.to(u.V).m, daq_HVoff.to(u.V).m, ΔV.to(u.V).m)
        daq_HVarr = daq_HVarr * u.V
        daq_VOAarr = np.linspace(current_VOAV, VOA_off, daq_HVarr.shape[0])
        # Ramp voltage 
        for ind, volt in enumerate(daq_HVarr):
            ch_VCSEL_MEMS.write(volt) 
            ch_VOA.write(daq_VOAarr[ind])
        #Final wavelength set (should be close, if not already there)
        ch_VCSEL_MEMS.write(daq_HVoff) 
        ch_VOA.write(VOA_off)
    
    
def VCSEL_sweep_volts(daq_Varr, num_sweep):
    # Given the daq voltages for a single wavelength (forward) sweep, concatenate an array for num_sweep sweeps (forward + back)
    # 1 sweep is either forward or backward sweep (not full period)
    if num_sweep == 1:
        V_sweep = daq_Varr
    elif num_sweep %2 == 0: # num_sweep even 
        V_sweep = np.tile(np.concatenate((daq_Varr.m,daq_Varr.m[::-1])), num_sweep // 2)*u.volt
    else: # num_sweep odd, > 1
        V_sweep = np.tile(np.concatenate((daq_Varr.m,daq_Varr.m[::-1])), num_sweep // 2)*u.volt
        V_sweep = np.concatenate((V_sweep.m, daq_Varr.m))*u.V #append one more forward sweep
                                 
    # Repeat final value in sweep (since analog input read lags analog output write) 
    # -> Moved to configure_vcsel_sweep()
    # V_sweep = np.concatenate((V_sweep, [V_sweep[-1]]))
    return V_sweep


def find_raman(raman_pk, sweep_bw, t_lia, sens_lia, fixed_wav, Δwav=0.1*u.nm, num_sweep=10, figsize=(6,4), wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, wavvolt_HVCALIB=wavvolt_HVCALIB):
    """
    Given nominal raman peak (cm^-1), sweep in neighborhood of peak, extract exact voltage of peak location, set voltage to peak
    """
    remove_bs()

    # Assign pump and Stokes wavelengths
    pump_wav = fixed_wav
    
    # Nominal peak wavelength
    pump_wav = fixed_wav
    stokes_pk = 1 / (1/pump_wav - raman_pk)
    wav_stop = 1 / (1/pump_wav - (raman_pk + np.round(sweep_bw / 2)))
    wav_start = 1 / (1/pump_wav - (raman_pk - np.round(sweep_bw / 2)))
    
    # Create array of valid wavelengths
    wavelength_set = generate_valid_sweep(wav_start, wav_stop, Δwav, wavvolt_file)
    stokes_wav = wavelength_set
    raman_shift = (1 / pump_wav  - 1 / stokes_wav).to(1 / u.cm)

    # Configure HVA and VOA for sweep
    daq_HVset, VOA_Vset, HVA_Vset, wavelength_Vset = parse_wav_delay(wavelength_set, wavvolt_file, delayvolt_file)
    V_MEMS_sweep = VCSEL_sweep_volts(daq_HVset, num_sweep)
    V_VOA_sweep = VCSEL_sweep_volts(VOA_Vset, num_sweep)
    
    num_samp = V_VOA_sweep.shape[0]
    fsamp = (1 / (τ_settle * t_lia)).to(u.Hz)

    #Initialize to first voltages in sweep
    ramp_VCSEL(HVA_Vset[0])

    write_data = {
        ch_VCSEL_MEMS_str: V_MEMS_sweep,
        ch_VOA_str: V_VOA_sweep
    }
    # Create DAQ task
    sweep_task = Task(
        ch_Vsrs_2,
        ch_HVA_Vmon,
        ch_wav_mon,
        ch_VCSEL_MEMS,
        ch_VOA
    )
    # Set DAQ sampling rate and number of samples to write/read (for averaging)
    sweep_task.set_timing(fsamp=fsamp, n_samples=num_samp)

    # Print calculated sweep time
    sweep_time = (1 / fsamp).to(u.second) * num_samp
    start_time = time.time()
    end_time = start_time + sweep_time.m
    print(f"sweep time: {sweep_time:3.2f}")
    print(f"start time: {time.ctime(start_time):s}")
    print(f"stop time: {time.ctime(end_time):s}")

    read_data = sweep_task.run(write_data)
    proc_data = unwrap_sweep(read_data, num_sweep, wavelength_Vset, wavvolt_HVCALIB)

    # Calculate raman shift
    raman_shift = raman_shift[:-1]
    offset = 0*u.V
    Vsrs_arr = (proc_data["Vsrs_arr"] / 10 + offset).to(u.V).m * sens_lia.to(u.V)

    Vsrs_raw_av = np.mean(Vsrs_arr, axis=0)
    mind = np.argmax(Vsrs_raw_av)
    HV_raw_av = np.mean(proc_data["HV_arr"], axis=0)
    HV_pk = HV_raw_av[mind]

    # Unreserve daq
    sweep_task.unreserve()

    # Set voltage to peak location
    ramp_VCSEL(HV_pk)

    Vsrs_interp_arr = calibrate_sweepSpectra(wavelength_Vset[:-1], Vsrs_arr[:,:-1], proc_data["HV_arr"][:,:-1], HVA_Vset[:-1], wavvolt_HVCALIB)
    print(Vsrs_interp_arr.shape)
    Vsrs_av = np.mean(Vsrs_interp_arr, axis=0)
    mind = np.argmax(Vsrs_av)
    print("Peak at {:2.3f}".format(raman_shift[mind]))
    print("LIA voltage: {:2.3f}".format(Vsrs_raw_av[mind]))
    print("Stokes wavelength: {:2.3f}".format(wavelength_Vset[mind]))
    print("MEMS voltage at {:2.3f}".format(HV_pk))
    
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.plot(raman_shift, Vsrs_av.to(u.uV))
    ax.set_xlabel("Raman Shift $(cm^{-1})$")
    ax.set_ylabel("V_{srs} $(\mu V)$")


def configure_VCSEL_sweep(wav_start, wav_stop, Δwav, fixed_wav, num_sweep, t_lia, wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, ch_sync=None, trig_params=None, num_pix=1, pad_galvo_endpts=1, τ_settle=5):
    #Create and return a task for VCSEL wavelength sweep (with VOA delay compensation)
    # - num_pix - if taking a hyperspectral image, tile each waveform sweep for num_pix pixels
    # - pad_galvo_endpts = 1 - pads sweep endpoints where galvos move with specified # of samples
    # for num_pix = 1, doesn't pad 5 values at front and end of array (to maintain backward compatibility with VCSEL_sweep_spectrum())
    
    # Create array of valid wavelengths
    wavelength_set = generate_valid_sweep(wav_start, wav_stop, Δwav, wavvolt_file=wavvolt_file)

    # Assign pump and Stokes wavelengths
    stokes_wav = wavelength_set
    pump_wav = fixed_wav


    if trig_params is None:
        fsamp = (1 / (τ_settle * t_lia)).to(u.Hz)
    else:
        fsamp = trig_params['freq']

    daq_HVset, VOA_Vset, HVA_Vset, wavelength_set = parse_wav_delay(wavelength_set, wavvolt_file, delayvolt_file)
    
    V_MEMS_sweep = VCSEL_sweep_volts(daq_HVset, num_sweep)

    V_VOA_sweep = VCSEL_sweep_volts(VOA_Vset, num_sweep)
    # print(f'V_MEMS_sweep 1: {V_MEMS_sweep.shape[0]}')
    # print(f'V_VOA_sweep 1: {V_VOA_sweep.shape[0]}')

    # test-------------
    # waveform_base = np.array((1,0))
    # waveform = np.tile(waveform_base, int(V_VOA_sweep.shape[0]//2))*u.V
    # if V_VOA_sweep.shape[0] %2 != 0: #if odd
    #     waveform = np.append(waveform.m,[1]) * u.V
    # print(f'waveform: {waveform.shape[0]}')

    #test ----------------
    # Pad end of array since ai lags ao
    V_MEMS_pad_fwd = np.append(V_MEMS_sweep, V_MEMS_sweep[-1]*np.ones(pad_galvo_endpts))
    V_MEMS_pad_bkd = np.append(V_MEMS_sweep[::-1], V_MEMS_sweep[0]*np.ones(pad_galvo_endpts))
    V_VOA_pad_fwd = np.append(V_VOA_sweep, V_VOA_sweep[-1]*np.ones(pad_galvo_endpts))
    V_VOA_pad_bkd = np.append(V_VOA_sweep[::-1], V_VOA_sweep[0]*np.ones(pad_galvo_endpts))
    # print(V_MEMS_pad_fwd)
    # print(V_MEMS_pad_bkd)
    
    if num_pix > 1:
        # waveform = np.append(V_MEMS_sweep[0]*np.ones(pad_galvo_endpts), waveform)
        V_MEMS_tmp = np.tile(np.concatenate((V_MEMS_pad_fwd.m, V_MEMS_pad_bkd.m)), num_pix // 2) * u.V
        V_VOA_tmp = np.tile(np.concatenate((V_VOA_pad_fwd.m, V_VOA_pad_bkd.m)), num_pix // 2) * u.V

        if num_pix %2 != 0: # odd num_pix
            V_MEMS_sweep = np.concatenate((V_MEMS_tmp.m, V_MEMS_pad_fwd.m)) * u.V #append one more forward sweep
            V_VOA_sweep = np.concatenate((V_VOA_tmp.m, V_VOA_pad_fwd.m)) * u.V
        else: # even
            V_MEMS_sweep = V_MEMS_tmp
            V_VOA_sweep = V_VOA_tmp
            # V_MEMS_sweep = np.tile(V_MEMS_sweep, num_pix )
            # V_VOA_sweep = np.tile(V_VOA_sweep, num_pix)
            # waveform = np.tile(waveform, num_pix)
            
        # print(f'V_MEMS_sweep 2: {V_MEMS_sweep.shape[0]}')
        # print(f'V_VOA_sweep 2: {V_VOA_sweep.shape[0]}')

        # 5 sample delay between DAQ2 and DAQ1 start - add 5 sample buffer at start of DAQ2
        pad = 5 
        num_samp = V_VOA_sweep.shape[0] + pad*2
        V_VOA_sweep = np.append(V_VOA_sweep[0]*np.ones(pad), V_VOA_sweep)
        V_MEMS_sweep = np.append(V_MEMS_sweep[0]*np.ones(pad), V_MEMS_sweep)
        # waveform = np.append(waveform[0]*np.ones(pad), waveform)
        
        # 5 sample pad at end of DAQ2 AO write
        V_VOA_sweep = np.append(V_VOA_sweep, V_VOA_sweep[-1]*np.ones(pad))
        V_MEMS_sweep = np.append(V_MEMS_sweep, V_MEMS_sweep[-1]*np.ones(pad))
            
    else: # Single pixel wavelength sweep (i.e. galvos stationary)
        # Repeat final value in sweep (since analog input read lags analog output write) 
        V_MEMS_sweep = V_MEMS_pad_fwd
        V_VOA_sweep = V_VOA_pad_fwd
        num_samp = V_VOA_sweep.shape[0] #discards first value of ai read when unrapping sweep
    
    print(f'V_MEMS_sweep: {V_MEMS_sweep.shape[0]}')
    print(f'V_MEMS_pad_fwd: {V_MEMS_pad_fwd.shape[0]}')
    print(f'V_VOA_sweep: {V_VOA_sweep.shape[0]}')
    print(f'num_samp: {num_samp}')
    
    write_data = {
        ch_VCSEL_MEMS_str: V_MEMS_sweep,
        ch_VOA_str: V_VOA_sweep
    }
    
    # Create DAQ task
    if ch_sync is not None:
        sweep_task = Task( 
            ch_VCSEL_MEMS,
            ch_VOA,
            ch_Vsrs_2,
            ch_HVA_Vmon,
            ch_wav_mon,
            ch_sync,
            trig_params = trig_params
        )
    else:
        sweep_task = Task(
            ch_Vsrs_2,
            ch_HVA_Vmon,
            ch_wav_mon,
            ch_VCSEL_MEMS,
            ch_VOA
        )
        
    # Set DAQ sampling rate and number of samples to write/read (for averaging)
    sweep_task.set_timing(fsamp=fsamp, n_samples=num_samp)
    
    # Print calculated sweep time
    sweep_time = (1 / fsamp).to(u.second) * num_samp
    start_time = time.time()
    end_time = start_time + sweep_time.m
    print(f"sweep time: {sweep_time:3.2f}")
    print(f"start time: {time.ctime(start_time):s}")
    print(f"stop time: {time.ctime(end_time):s}")
    
    record_data = {
        "wavelength_set": wavelength_set,
        "pump_wav": fixed_wav,
        "HVA_Vset": HVA_Vset,
        "VOA_Vset": VOA_Vset
    }
    
    return sweep_task, write_data, record_data
    
    
def VCSEL_sweep_spectrum(wav_start, wav_stop, Δwav, num_sweep, t_lia, sens_lia, fixed_wav,sample_dir=None, name=None, wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, ch_sync=None, trig_params=None, τ_settle=5):
    """
    Acquire spectrum by continuously sweeping VCSEL wavelength and VOA voltage over specified range (faster acquisition)
        -VCSEL wavlength tuning with DAQ + HVA
        -VOA delay compenstion with DAQ
    No active wavelength monitoring
    param: 
        -wavvolt_file - .mat file with voltage to wavelength calibration
        -delayvolt_file - .mat file with VOA voltage per VCSEL MEMS voltage set
        -num_sweep - number of full period sweeps (forward + backward sweep)
        -ch_sync - channel object (counter output) of sync output
        -trig_params - needs to be provided if ch_sync is not None
    """
    remove_bs()
    
    # Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    spath = new_path(name=name, data_dir=sample_dir, ds_type='Spectra', extension='h5', timestamp=True)
    print("saving data to: ")
    print(spath)
    
    sweep_task, write_data, record_data = configure_VCSEL_sweep(wav_start, wav_stop, Δwav, fixed_wav, num_sweep, t_lia, wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file, ch_sync=ch_sync, trig_params=trig_params, τ_settle=τ_settle)

    # Assign pump and Stokes wavelengths
    stokes_wav = record_data["wavelength_set"]
    pump_wav = fixed_wav

    #Initialize to first voltages in sweep
    ramp_VCSEL(record_data["HVA_Vset"][0])

    # save sweep parameters to hdf5
    dump_hdf5(
        {'num_sweep': num_sweep,
         't_lia': t_lia,
         'sens_lia': sens_lia,
         'wav_start': wav_start,
         'wav_stop': wav_stop,
         'Δwav': Δwav,
         'wavelength_set': record_data["wavelength_set"], #sorted by increasing HV voltage, same as HV_set (see parse_wav_delay)
         'pump_wav': pump_wav
         },
        spath,
        open_mode='x',
    )

    dump_hdf5(write_data, spath)
    read_data = sweep_task.run(write_data)
    dump_hdf5(read_data, spath)
    proc_data = unwrap_sweep(read_data, num_sweep, record_data["wavelength_set"], wavvolt_HVCALIB)
    dump_hdf5(proc_data, spath)
    
    # Unreserve daq
    sweep_task.unreserve()

    # Calculate raman shift
    raman_shift = (1 / pump_wav  - 1 / stokes_wav).to(1 / u.cm)

    # Save sweep data to hdf5
    sweep_data = {
        'HVA_Vraw': read_data[ch_HVA_Vmon_str],
        'Vsrs_Vraw': read_data[ch_Vsrs_2_str],
        'VCSEL_wavmon_raw': read_data[ch_wav_mon_str],
        'HVA_Vset': record_data["HVA_Vset"],
        'VOA_Vset': record_data["VOA_Vset"],
        'raman_shift': raman_shift,
    }
    dump_hdf5(sweep_data, spath)
    ds_spec = load_hdf5(fpath=spath)

    # Save data to .mat file
    mat_fname = spath[:-2] + 'mat'
    file_dir = os.path.join(data_dir, sample_dir, mat_fname)
    data = {
            't_lia'             : ds_spec['t_lia'].to(u.s).m,
            'sens_lia'          : ds_spec['sens_lia'].to(u.V).m,
            'num_sweep'         : ds_spec['num_sweep'],
            'wav_start'         : ds_spec['wav_start'].to(u.m).m,
            'wav_stop'          : ds_spec['wav_stop'].to(u.m).m,
            'dwav'              : ds_spec['Δwav'].to(u.m).m,
            'pump_wav'          : ds_spec['pump_wav'].to(u.m).m,
            'wavelength_set'    : ds_spec['wavelength_set'].to(u.m).m,
            'Vsrs_arr'          : ds_spec['Vsrs_arr'].to(u.V).m,
            'HV_arr'            : ds_spec['HV_arr'].to(u.V).m,
            'VCSEL_wavmon_arr'  : ds_spec['VCSEL_wavmon_arr'].to(u.V).m,
            # 'Vsrs_interp_arr': ds_spec['Vsrs_interp_arr'].to(u.V).m,
            'raman_shift'       : ds_spec['raman_shift'].to(1/u.cm).m,
            'VOA_Vset'          : ds_spec['VOA_Vset'].to(u.V).m,
            'HVA_Vset'          : ds_spec['HVA_Vset'].to(u.V).m,
            'HVA_Vraw'          : ds_spec['HVA_Vraw'].to(u.V).m,
            'Vsrs_Vraw'         : ds_spec['Vsrs_Vraw'].to(u.V).m,
            'VCSEL_wavemon_raw' : ds_spec['VCSEL_wavmon_raw'].to(u.V).m
            }
    io.savemat(file_dir, data)
    return ds_spec

    
def unwrap_sweep(read_data, num_sweep, wavelength_set, wavvolt_file, HVA_gain=100):
    # Input: 1d wrapped spectra from daq
    # Return: proc_data struct with 2d arrays (num_sweep rows by spectra length columns)
    # Vsrs_arr: columns sorted by increasing HV set (not increasing wavelength)
   
    Vsrs = read_data[ch_Vsrs_2_str][1:]  # Discard 1st analog input read (taken before analog output settles)
    HV = Vmon_to_HVA(read_data[ch_HVA_Vmon_str][1:]) # Discard 1st analog input read (taken before analog output settles)
    VCSEL_wavmon = read_data[ch_wav_mon_str][1:] # Discard 1st analog input read (taken before analog output settles)

    # Unwrap sweeps to 2d array
    Vsrs_arr = np.reshape(np.array(Vsrs.to(u.V).m), (num_sweep, len(wavelength_set)))
    HV_arr = np.reshape(np.array(HV.to(u.V).m), (num_sweep, len(wavelength_set)))
    VCSEL_wavmon_arr = np.reshape(np.array(VCSEL_wavmon.to(u.V).m), (num_sweep, len(wavelength_set)))
    
    # wav_est_arr = np.zeros(HV_arr.shape)
    # Vsrs_interp_arr = np.zeros(HV_arr.shape)
    
    # Odd rows are backward sweeps - flip
    for row in range(Vsrs_arr.shape[0]):
        if row % 2 != 0:
            Vsrs_arr[row,:] = Vsrs_arr[row,::-1]
            HV_arr[row,:] = HV_arr[row,::-1]
            VCSEL_wavmon_arr[row,:] = VCSEL_wavmon_arr[row,::-1]
    
    # Calibrate voltage to wavelength
    # a = io.loadmat(wavvolt_file)
    # wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
    # volt_calib = a['volt_interp'][0]*u.V

    # Find wavelengths corresponding to measured voltage 
    # for sweep_iter in range(HV_arr.shape[0]):
    #     for wl in range(HV_arr.shape[1]):
    #         ind = np.argmin(np.abs(HV_arr[sweep_iter, wl] - volt_calib.m))
    #         wav_est_arr[sweep_iter, wl] = wav_calib[ind].m
    #     # Interpolate wavelength vs spectra to uniformly sample in wavelength
    #     Vsrs_interp_arr[sweep_iter] = np.interp(wavelength_set.to(u.nm).m, wav_est_arr[sweep_iter], Vsrs_arr[sweep_iter])
    
    proc_data = {
        "Vsrs_arr": Vsrs_arr * u.V,
        "HV_arr": HV_arr * u.V,
        "VCSEL_wavmon_arr": VCSEL_wavmon_arr * u.V
        # "wav_est_arr": wav_est_arr * u.nm,
        # "Vsrs_interp_arr": Vsrs_interp_arr * u.V
    }
    return proc_data


# def calibrate_HVAset(HVA_Vset, calib_fpath, verbose=False):
#     """
#     Calibrate HVA set voltage to correct for measured offset error
#     """
#     # fpath = os.path.join(calib_dir, calib_fname)
#     # print(f'fpath: {fpath}')
    
#     ds = load_hdf5(fpath=calib_fpath)

#     def line(x,a,b):
#         return a*x + b

#     def invert_line(y,a,b):
#         return (y-b)/a

#     HVA_mean = np.mean(ds['HV_arr'].transpose(), axis=1)

#     # Linear fit of measured HVA voltage
#     popt,_ = curve_fit(line, ds["HVA_Vset"].to(u.V).m, HVA_mean)
#     HVA_linfit = line(ds["HVA_Vset"].m, popt[0], popt[1])

#     # For each voltage in HVA Vset, calculate the corrected set voltage to achieve the actual set value
#     HVA_corrset = invert_line(HVA_Vset.m, popt[0], popt[1]) * u.V

#     if verbose:
#         fig, ax = plt.subplots(1,1, figsize=(5,4), tight_layout=True)
#         ax.plot(ds["HVA_Vset"], HVA_mean, 'b', label='mean')
#         ax.plot(ds["HVA_Vset"], ds["HVA_Vset"], 'k', label='set')
#         ax.plot(ds["HVA_Vset"], HVA_linfit, 'r', label='lin fit')
#         ax.plot(HVA_Vset, HVA_corrset, 'g', label='corr set')
#         ax.set_xlabel("HVA set (V)")
#         ax.set_ylabel("HVA meas (V)")
#         plt.legend()
        
#     return HVA_corrset


def calibrate_sweepSpectra(wavelength_set, Vsrs_arr, HV_arr, HVA_Vset, wavvolt_HVCALIB=wavvolt_HVCALIB):
    """
    Calibrate daq VCSEL sweep using HVA monitor.  Return calibrated Vsrs_interp_arr (wavelength interpolated to original wavelength set for consistent
    Raman shifts between iterations)
    wavelength_set: sorted by increasing voltage (same as HV_set) - see parse_wav_delay()
    """
    def line(x,a,b):
        return a*x + b
    
    # Calibrate voltage to wavelength
    a = io.loadmat(wavvolt_HVCALIB)
    wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
    volt_calib = a['volt_interp'][0]*u.V

    # Initialize arrays
    HV_filt = np.array(np.zeros(HV_arr.shape))
    wav_calib_arr = np.array(np.zeros(HV_arr.shape))
    wav_calib_sort = np.array(np.zeros(HV_arr.shape))
    Vsrs_interp_arr = np.array(np.zeros(HV_arr.shape))
    Vsrs_arr_sort = np.array(np.zeros(HV_arr.shape))

    
    #sort set wavelength by increasing wavelength ------------------
    wavset_sort = np.sort(wavelength_set)
    dwav = np.mean(np.diff(wavset_sort))
    #-----------------
        
    for spec in range(HV_arr.shape[0]):
        popt,_ = curve_fit(line,HVA_Vset.to(u.V).m,HV_arr[spec].to(u.V).m)
        HV_filt[spec] = line(HVA_Vset.m, popt[0], popt[1])
    HV_filt = HV_filt*u.V 
    
    # Find wavelengths corresponding to measured voltage 
    # fig, ax = plt.subplots(2,1)
    for sweep_iter in range(HV_filt.shape[0]):
        for wl in range(HV_filt.shape[1]):
            ind = np.nanargmin(np.abs(HV_filt[sweep_iter, wl].m - volt_calib.m))
            wav_calib_arr[sweep_iter, wl] = wav_calib[ind].m
            
        #sort extracted wavelength from HV mon by increasing wavelength
        wlsort_ind = np.argsort(wav_calib_arr[sweep_iter])
        wav_calib_sort[sweep_iter] = wav_calib_arr[sweep_iter, wlsort_ind]
        Vsrs_arr_sort[sweep_iter] = Vsrs_arr[sweep_iter, wlsort_ind]
        
        # Interpolate wavelength vs spectra to uniformly sample in wavelength
        Vsrs_interp_arr[sweep_iter,:] = np.interp(wavset_sort.to(u.nm).m, wav_calib_sort[sweep_iter,:], Vsrs_arr_sort[sweep_iter,:])

        # Remove discontinuity
        if np.max(np.diff(wav_calib_sort[sweep_iter,:])) > dwav.to(u.nm).m*2:
            bad_ind = np.where(np.diff(wav_calib_sort[sweep_iter,:]) > dwav.to(u.nm).m*2)# | np.diff(wav_calib_sort[sweep_iter,:]) == 0)
            bad_ind2 = np.where(np.diff(wav_calib_sort[sweep_iter,:]) == 0)
            Vsrs_interp_arr[sweep_iter, bad_ind] = np.nan
            Vsrs_interp_arr[sweep_iter, bad_ind2] = np.nan
        # ax[0].plot(range(wavset_sort.shape[0]), wav_calib_arr[sweep_iter], color='blue')
        # ax[0].plot(range(wavset_sort.shape[0]), wav_calib_sort[sweep_iter], color='red')
        # ax[0].set_xlabel("Index")
        # ax[0].set_ylabel("Wav calib")
        # ax[1].plot(rs_set,  Vsrs_interp_arr[sweep_iter,:])
        # ax[1].set_xlabel("Raman Shift")
        # ax[1].set_ylabel("Vsrs interp")
    return Vsrs_interp_arr*u.V
    

def plot_daq_sweepSpectra(ds0, savefig=False, fname=None, fpath=None, figsize=(5,6), wavvolt_HVCALIB=wavvolt_HVCALIB):
    #First point in sweep already removed in unwrap_sweep()
    HVA_Vset = ds0["HVA_Vset"]
    wavelength_set = ds0["wavelength_set"]
    HV_arr = ds0["HV_arr"]
    raman_shift = ds0["raman_shift"] #sorted in order of increasing voltage

    rs_sort = np.sort(raman_shift) #sorted by ascending wavelength (ascending raman_shift for tuning Stokes wavelength)

    offset = 0*u.V
    Vsrs_arr = (ds0["Vsrs_arr"] / 10 + offset).to(u.V).m * ds0["sens_lia"].to(u.V)

    Vsrs_interp_arr = calibrate_sweepSpectra(wavelength_set, Vsrs_arr, HV_arr, HVA_Vset, wavvolt_HVCALIB=wavvolt_HVCALIB)
    VCSEL_wavmon_arr = ds0["VCSEL_wavmon_arr"]

    Vsrs_av = np.mean(Vsrs_interp_arr, axis=0)
    uncal_Vsrs_av = np.mean(Vsrs_arr, axis=0)
    
    mind = np.nanargmax(Vsrs_av)
    mind_uncal = np.nanargmax(uncal_Vsrs_av)
    
    print("Calib Peak at {:2.3f}".format(rs_sort[mind]))
    print(f"Uncal Peak at {raman_shift[mind_uncal] :2.3f}")

    fig, ax = plt.subplots(3, 1, figsize=figsize, gridspec_kw={"wspace":0,"hspace":0.3})
    for spec in range(Vsrs_arr.shape[0]):
        ax[0].plot(raman_shift, Vsrs_arr[spec].to(u.uV))
        ax[1].plot(rs_sort, Vsrs_interp_arr[spec].to(u.uV))
      
    ax[2].plot(rs_sort, Vsrs_av.to(u.uV))
    ax[2].plot(rs_sort[mind].m, Vsrs_av[mind].to(u.uV).m, 'x')
    # ax[2].plot(raman_shift, np.mean(Vsrs_arr, axis=0).to(u.uV), 'k')
    ax[0].set_ylabel("Voltage $(\mu V)$")
    ax[0].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
    ax[1].set_ylabel("Voltage $(\mu V)$")
    ax[1].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
    ax[2].set_xlabel("Raman Shift (1/cm)")
    ax[2].set_ylabel("Voltage $(\mu V)$")
    ax[2].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
    
    if savefig:
        fname=os.path.normpath(os.path.join(fpath,fname))
        plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
            orientation='portrait', transparent=True, bbox_inches=None, pad_inches=0.5)
    return fig


#------------------------------------------------
# Initialize VCSEL to off
turn_VCSEL_off()
print("VOA initialized to {:2.3}".format(ch_VOA.read()))

     
#-------------------------------------------------
"""Old Deprecated Functions"""
#-------------------------------------------------
# def continuous_spectrum(t_lia, sens_lia, wav_start, wav_stop, fixed_wav, t_sweep=60*u.s,sample_dir=None, name=None):
#     """
#     Acquire spectrum by continuously sweeping wavelength for a specified time interval
#     Faster acquisition (i.e. for O-E land) - requires short LIA time constants
#     """
#     fsamp = (1 / (4 * t_lia)).to(u.Hz)
#     num_samp = int(t_sweep.m / (1 / fsamp).m)

#     # Specify location of data save
#     sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
#     spath = new_path(name=name, data_dir=sample_dir, ds_type='SpectraSweep', extension='h5', timestamp=True)
#     print("saving data to: ")
#     print(spath)

#     # save sweep parameters to hdf5
#     dump_hdf5(
#         {'t_lia': t_lia,
#          'sens_lia': sens_lia,
#          'fsamp': fsamp,
#          'wav_start': wav_start,
#          'wav_stop': wav_stop,
#          't_sweep': t_sweep,
#          'fixed_wav': fixed_wav,
#          },
#         spath,
#         open_mode='x',
#     )
#     # Create DAQ task
#     sweep_task = Task(
#         ch_Vsrs,
#         ch_Vmon
#     )
#     # Set DAQ sampling rate and number of samples to acquire
#     sweep_task.set_timing(fsamp=fsamp, n_samples=num_samp)

#     # Print calculated sweep time
#     sweep_time = ((1 / fsamp).to(u.second) * num_samp)
#     print(f"sweep time: {sweep_time:3.2f}")
#     start_time = time.time()
#     end_time = start_time + sweep_time.m
#     print(f"start time: {time.ctime(start_time):s}")
#     print(f"stop time: {time.ctime(end_time):s}")

# #     remove_bs()

#     read_data = sweep_task.run()  # take num_avg daq readings, append average

#     # Unreserve daq
#     sweep_task.unreserve()

#     # Save sweep data to hdf5
#     sweep_data = {
#         'spec': read_data[ch_Vsrs_str],
#         'wav_mon': read_data[ch_Vmon_str]
#     }

#     dump_hdf5(sweep_data, spath)
#     ds_spec = load_hdf5(fpath=spath)

#     # Save data to .mat file
#     mat_fname = spath[:-2] + 'mat'
#     file_dir = os.path.join(data_dir, sample_dir, mat_fname)

#     data = {'t_lia': ds_spec['t_lia'].to(u.s).m,
#             'sens_lia': ds_spec['sens_lia'].to(u.V).m,
#             'fsamp': ds_spec['fsamp'].m,
#             'wav_start': ds_spec['wav_start'].to(u.m).m,
#             'wav_stop': ds_spec['wav_stop'].to(u.m).m,
#             't_sweep': ds_spec['t_sweep'].to(u.s).m,
#             'fixed_wav': ds_spec['fixed_wav'].to(u.m).m,
#             'spec': ds_spec['spec'].m,
#             'wav_mon': ds_spec['wav_mon'].m
#             }
#     io.savemat(file_dir, data)
#     return ds_spec


# def acquire_point(t_lia, n_rep, pump_wav, stokes_wav, sample_dir=None, name=None):
#     """
#     Acquire n_rep readings at single wavelength point with fsamp determined by LIA integration time.
#     Simultaneously acquire tap readings from pump and stokes lasers.
#     """
#     fsamp = (1 / (4 * t_lia)).to(u.Hz)

#     # Specify location of data save
#     sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
#     spath = new_path(name=name, data_dir=sample_dir, ds_type='WavePoint', extension='h5', timestamp=True)
#     print("saving data to: ")
#     print(spath)

#     # save sweep parameters to hdf5
#     dump_hdf5(
#     {'t_lia': t_lia,
#          'fsamp': fsamp,
#          'pump_wav': pump_wav,
#          'stokes_wav': stokes_wav
#          # 'pump_VW': pump_VW, #pump photodiode V/W @ pump
#          # 'stokes_VW': stokes_VW #stokes photodiode V/W @ stokes
#          },
#         spath,
#         open_mode='x',
#     )

#     # Create DAQ task
#     point_task = Task(
#         ch_Vsrs,
#         # ch_stokes_tap,
#         # ch_pump_tap
#     )

#     # Set DAQ sampling rate and number of samples to acquire
#     point_task.set_timing(fsamp=fsamp, n_samples=n_rep)

#     # Print calculated acquisition time
#     acquisition_time = t_lia * n_rep * 4
#     print(f"acquisition time: {acquisition_time:3.2f}")
#     start_time = time.time()
#     end_time = start_time + acquisition_time.m
#     print(f"start time: {time.ctime(start_time):s}")
#     print(f"stop time: {time.ctime(end_time):s}")

#     remove_bs()

#     read_data = point_task.run()  # take num_avg daq readings, append average

#     # Unreserve daq
#     point_task.unreserve()

#     # Save point data to hdf5
#     point_data = {
#         'srs': read_data[ch_Vsrs_str],
#         # 'pump_tap': read_data[ch_pump_tap_str],
#         # 'stokes_tap': read_data[ch_stokes_tap_str],
#     }

#     dump_hdf5(point_data, spath)
#     ds_point = load_hdf5(fpath=spath)

#     # Save data to .mat file
#     mat_fname = spath[:-2] + 'mat'
#     file_dir = os.path.join(data_dir, sample_dir, mat_fname)

#     data = {'t_lia': ds_point['t_lia'].to(u.s).m,
#             'fsamp': ds_point['fsamp'].m,
#             'pump_wav': ds_point['pump_wav'].to(u.m).m,
#             'stokes_wav': ds_point['stokes_wav'].to(u.m).m,
#             'srs': ds_point['srs'].m,
#             # 'pump_tap': ds_point['pump_tap'].m,
#             # 'stokes_tap': ds_point['stokes_tap'].m
#             }
#     io.savemat(file_dir, data)
#     return ds_point


# def VCSEL_step_spectrum(osa, num_avg, t_lia, sens_lia, wav_start, wav_stop, Δwav, fixed_wav, wav_settle_time=1*u.s,sample_dir=None, name=None,  wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file):
#     """
#     Acquire spectrum by stepping laser wavelength to new wavelength in sweep range (at a fixed spatial point)
#         -VCSEL wavlength tuning with DAQ + HVA
#         -VOA delay compenstion with DAQ
#         -osa read at each step
#     Slower acquisition (for VCSEL with sourcemeter)- sets wavelength, waits for wavelength to settle before acquiring data
#     param: 
#         -wavvolt_file - .mat file with voltage to wavelength calibration
#         -delayvolt_file - .mat file with VOA voltage per VCSEL MEMS voltage set
#     """
#     remove_bs()
#     HVA_gain = 100

#     # Specify location of data save
#     sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
#     spath = new_path(name=name, data_dir=sample_dir, ds_type='Spectra', extension='h5', timestamp=True)
#     print("saving data to: ")
#     print(spath)

#     fsamp = (1 / (4 * t_lia)).to(u.Hz)

#     # Read fixed pump wavelength
#     span = 1090*u.nm - 1030*u.nm
#     center_wl = np.round(span/2) + 1030*u.nm
#     osa.set_wavelength_span(span)
#     osa.set_center_wavelength(center_wl)
#     [pk_wls, _] = osa.get_peak_info()
    
#     # Create array of valid wavelengths
#     wavelength_set = generate_valid_sweep(wavvolt_file, wav_start, wav_stop, Δwav)
#     pump_wl_meas = pk_wls[0] #fixed
#     stokes_wl_meas = []
#     daq_Vset = [] # MEMS Voltage (input to HVA)
#     HVA_Vset = [] # MEMS Voltage
#     V_mon = [] #HVA scaled Vmon
#     VOA_Vset = [] # VOA Voltage
    
#     # Load wavvolt_file
#     a = io.loadmat(wavvolt_file)
#     wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
#     volt_calib = a['volt_interp'][0]*u.V

#     # Load delayvolt_file
#     b = io.loadmat(delayvolt_file)
#     VOA_volt = b['VOA_est_interp'][0]*u.V
#     VCSEL_volt = b['V_MEMSinterp'][0]*u.V 

#     # Find voltages corresponding to wavelength_set
#     for wav in wavelength_set.to(u.nm).m:
#         ind = np.argmin(np.abs(wav - wav_calib.to(u.nm).m))
#         HVA_Vset.append(volt_calib[ind].to(u.V).m)
#         daq_Vset.append(HVA_to_daq(volt_calib[ind]).to(u.V).m)
#     daq_Vset = daq_Vset * u.V
#     HVA_Vset = HVA_Vset * u.V

#     # Find VOA voltage corresponding to VCSEL MEMS voltage set
#     for volt in HVA_Vset.to(u.V):
#         ind1 = np.argmin(np.abs(volt.m - VCSEL_volt.m))
#         VOA_Vset.append(VOA_volt[ind1].m)
#     VOA_Vset = VOA_Vset * u.V

#     # save sweep parameters to hdf5
#     dump_hdf5(
#         {'num_avg': num_avg,
#          't_lia': t_lia,
#          'sens_lia': sens_lia,
#          'wav_start': wav_start,
#          'wav_stop': wav_stop,
#          'Δwav': Δwav,
#          'wav_settle_time': wav_settle_time,
#          'wavelength_set': wavelength_set,
#          'fixed_wav': fixed_wav
#          },
#         spath,
#         open_mode='x',
#     )

#     spec= []
#     tuning_time = 1*u.s #estimated wavelength tuning time

#     # Create DAQ task
#     sweep_task = Task(
#         ch_Vsrs_2,
#         ch_HVA_Vmon,
#     )

#     # Set DAQ sampling rate and number of samples to write/read (for averaging)
#     sweep_task.set_timing(fsamp=fsamp, n_samples=num_avg)

#     # Print calculated sweep time
#     sweep_time = ((1 / fsamp).to(u.second) * num_avg + tuning_time) * wavelength_set.shape[0]
#     start_time = time.time()
#     end_time = start_time + sweep_time.m
#     print(f"sweep time: {sweep_time:3.2f}")
#     print(f"start time: {time.ctime(start_time):s}")
#     print(f"stop time: {time.ctime(end_time):s}")

#     #Shift OSA window around Stokes tuning range
#     span = (1330*u.nm) - (1230*u.nm)
#     center_wl = np.round(span/2) + 1230*u.nm
#     osa.set_wavelength_span(span)
#     osa.set_center_wavelength(center_wl)

#     # Iterate over wavelengths
#     for (ind,wav) in enumerate(wavelength_set.m):
#         ch_VCSEL_MEMS.write(daq_Vset[ind])
#         ch_VOA.write(VOA_Vset[ind])
#         time.sleep(wav_settle_time.m)  # Wait for wavelength to settle
#         read_spec = sweep_task.run() #take num_avg daq readings, append average
#         [pk_wls, _] = osa.get_peak_info()
#         time.sleep((1/fsamp).m*num_avg)  #Wait for daq to acquire readings
#         spec.append(np.mean(read_spec[ch_Vsrs_2_str].to(u.V).m))
#         V_mon.append(np.mean(daq_to_HVA(read_spec[ch_HVA_Vmon_str]).to(u.V).m))
#         stokes_wl_meas.append(pk_wls[0].m)  # Crop window around Stokes tuning, measure maximum peak
#     stokes_wl_meas = stokes_wl_meas*u.m
#     V_mon = V_mon*u.V
    
#     # Unreserve daq
#     sweep_task.unreserve()

#     # Identify pump and stokes wavelengths
#     if np.max(wavelength_set.m) > fixed_wav.m:
#         stokes_wav = wavelength_set
#         pump_wav = fixed_wav
#     elif np.max(wavelength_set.m) < fixed_wav.m:
#         stokes_wav = fixed_wav
#         pump_wav = wavelength_set

#     # Calculate raman shift
#     raman_shift = (1 / pump_wav  - 1 / stokes_wav).to(1 / u.cm)

#     # Save sweep data to hdf5
#     sweep_data = {
#         'spec': spec * u.volt,
#         'daq_Vset': daq_Vset, #daq output
#         'HVA_Vset': HVA_Vset, #Set HVA output
#         'VOA_Vset': VOA_Vset,
#         'V_mon': V_mon, #voltage mon
#         'raman_shift': raman_shift,
#         'pump_wl_meas': pump_wl_meas,
#         'stokes_wl_meas': stokes_wl_meas
#     }
#     dump_hdf5(sweep_data, spath)
#     ds_spec = load_hdf5(fpath=spath)

#     # Save data to .mat file
#     mat_fname = spath[:-2] + 'mat'
#     file_dir = os.path.join(data_dir, sample_dir, mat_fname)
#     data = {
#             't_lia': ds_spec['t_lia'].to(u.s).m,
#             'sens_lia': ds_spec['sens_lia'].to(u.V).m,
#             'num_avg': ds_spec['num_avg'],
#             'wav_start': ds_spec['wav_start'].to(u.m).m,
#             'wav_stop': ds_spec['wav_stop'].to(u.m).m,
#             'dwav': ds_spec['Δwav'].to(u.m).m,
#             'fixed_wav': ds_spec['fixed_wav'].to(u.m).m,
#             'pump_wl_meas': ds_spec['pump_wl_meas'].to(u.m).m,
#             'stokes_wl_meas': ds_spec['stokes_wl_meas'].to(u.m).m,
#             'wav_settle_time': ds_spec['wav_settle_time'].to(u.s).m,
#             'wavelength_set': ds_spec['wavelength_set'].to(u.m).m,
#             'daq_Vset': ds_spec['daq_Vset'].to(u.V).m,
#             'HVA_Vset': ds_spec['HVA_Vset'].to(u.V).m,
#             'V_mon': ds_spec['V_mon'].to(u.V).m,
#             'VOA_Vset': ds_spec['VOA_Vset'].to(u.V).m,
#             'spec': ds_spec['spec'].to(u.V).m,
#             'raman_shift': ds_spec['raman_shift'].to(1/u.cm).m
#             }
#     io.savemat(file_dir, data)
#     return ds_spec

# def acquire_spectrum(osa, num_avg, t_lia, sens_lia, wav_start, wav_stop, Δwav, fixed_wav, wav_settle_time=1*u.s,sample_dir=None, name=None,  wavvolt_file=wavvolt_file, delayvolt_file=delayvolt_file):
#     """
#     Acquire spectrum by setting laser wavelength to new wavelength in sweep range (at a fixed spatial point)
#         -Source meter for VCSEL wavelength tuning
#         -Power supply for VOA delay compensation
#         -osa read at each step
#     Slower acquisition (for VCSEL with sourcemeter)- sets wavelength, waits for wavelength to settle before acquiring data
#     param: wavvolt_file - .mat file with voltage to wavelength calibration
#          delayvolt_file - .mat file with VOA voltage per VCSEL MEMS voltage set
#     """
#     remove_bs()

#     # Specify location of data save
#     sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
#     spath = new_path(name=name, data_dir=sample_dir, ds_type='Spectra', extension='h5', timestamp=True)
#     print("saving data to: ")
#     print(spath)

#     fsamp = (1 / (4 * t_lia)).to(u.Hz)

#     # Read fixed pump wavelength
#     span = 1090*u.nm - 1030*u.nm
#     center_wl = np.round(span/2) + 1030*u.nm
#     osa.set_wavelength_span(span)
#     osa.set_center_wavelength(center_wl)
#     [pk_wls, _] = osa.get_peak_info()
    
#     # Create array of valid wavelengths
#     wavelength_set = generate_valid_sweep(wavvolt_file, wav_start, wav_stop, Δwav)
#     pump_wl_meas = pk_wls[0] #fixed
#     stokes_wl_meas = []
#     volt_set = [] # MEMS Voltage
#     volt_meas = [] # Measured MEMS Voltage
#     VOA_set = [] # VOA Voltage
    
#     # Load wavvolt_file
#     a = io.loadmat(wavvolt_file)
#     wav_calib =  (a['peak_interp'][0] * u.m).to(u.nm)
#     volt_calib = a['volt_interp'][0]*u.V

#     # Load delayvolt_file
#     b = io.loadmat(delayvolt_file)
#     VOA_volt = b['VOA_est_interp'][0]*u.V
#     VCSEL_volt = b['V_MEMSinterp'][0]*u.V 

#     # Find voltages corresponding to wavelength_set
#     for wav in wavelength_set.m:
#         ind = np.argmin(np.abs(wav - wav_calib.m))
#         volt_set.append(volt_calib[ind].m)
#     volt_set = volt_set * u.V

#     # Find VOA voltage corresponding to VCSEL MEMS voltage set
#     for volt in volt_set.m:
#         ind1 = np.argmin(np.abs(volt - VCSEL_volt.m))
#         VOA_set.append(VOA_volt[ind1].m)
#     VOA_set = VOA_set * u.V

#     # save sweep parameters to hdf5
#     dump_hdf5(
#         {'num_avg': num_avg,
#          't_lia': t_lia,
#          'sens_lia': sens_lia,
#          'wav_start': wav_start,
#          'wav_stop': wav_stop,
#          'Δwav': Δwav,
#          'wav_settle_time': wav_settle_time,
#          'wavelength_set': wavelength_set,
#          'fixed_wav': fixed_wav
#          },
#         spath,
#         open_mode='x',
#     )

#     spec= []
#     tuning_time = 1*u.s #estimated wavelength tuning time

#     # Create DAQ task
#     sweep_task = Task(
#         ch_Vsrs
#     )

#     # Set DAQ sampling rate and number of samples to write/read (for averaging)
#     sweep_task.set_timing(fsamp=fsamp, n_samples=num_avg)

#     # Print calculated sweep time
#     sweep_time = ((1 / fsamp).to(u.second) * num_avg + tuning_time) * wavelength_set.shape[0]
#     start_time = time.time()
#     end_time = start_time + sweep_time.m
#     print(f"sweep time: {sweep_time:3.2f}")
#     print(f"start time: {time.ctime(start_time):s}")
#     print(f"stop time: {time.ctime(end_time):s}")

#     #Shift OSA window around Stokes tuning range
#     span = (1330*u.nm) - (1230*u.nm)
#     center_wl = np.round(span/2) + 1230*u.nm
#     osa.set_wavelength_span(span)
#     osa.set_center_wavelength(center_wl)

#     # Iterate over wavelengths
#     for (ind,wav) in enumerate(wavelength_set.m):
#         sm.set_voltage(volt_set[ind])
#         ps.set_voltage(VOA_set[ind])
#         time.sleep(wav_settle_time.m)  # Wait for wavelength to settle
#         volt_meas.append(sm.measure_voltage().m) #read actual wavelength
#         read_spec = sweep_task.run() #take num_avg daq readings, append average
#         [pk_wls, _] = osa.get_peak_info()
#         time.sleep((1/fsamp).m*num_avg)  #Wait for daq to acquire readings
#         spec.append(np.mean(read_spec[ch_Vsrs_str].m))
    
#         stokes_wl_meas.append(pk_wls[0].m)  # Crop window around Stokes tuning, measure maximum peak
#     stokes_wl_meas = stokes_wl_meas*u.m
    
#     # Unreserve daq
#     sweep_task.unreserve()

#     # Identify pump and stokes wavelengths
#     if np.max(wavelength_set.m) > fixed_wav.m:
#         stokes_wav = wavelength_set
#         pump_wav = fixed_wav
#     elif np.max(wavelength_set.m) < fixed_wav.m:
#         stokes_wav = fixed_wav
#         pump_wav = wavelength_set

#     # Calculate raman shift
#     raman_shift = (1 / pump_wav  - 1 / stokes_wav).to(1 / u.cm)
#     print(volt_meas*u.V)

#     # Save sweep data to hdf5
#     sweep_data = {
#         'spec': spec * u.volt,
#         'volt_meas': volt_meas * u.V,
#         'volt_set': volt_set,
#         'raman_shift': raman_shift,
#         'pump_wl_meas': pump_wl_meas,
#         'stokes_wl_meas': stokes_wl_meas
#     }
#     dump_hdf5(sweep_data, spath)
#     ds_spec = load_hdf5(fpath=spath)

#     # Save data to .mat file
#     mat_fname = spath[:-2] + 'mat'
#     file_dir = os.path.join(data_dir, sample_dir, mat_fname)
#     data = {
#             't_lia': ds_spec['t_lia'].to(u.s).m,
#             'sens_lia': ds_spec['sens_lia'].to(u.V).m,
#             'num_avg': ds_spec['num_avg'],
#             'wav_start': ds_spec['wav_start'].to(u.m).m,
#             'wav_stop': ds_spec['wav_stop'].to(u.m).m,
#             'dwav': ds_spec['Δwav'].to(u.m).m,
#             'fixed_wav': ds_spec['fixed_wav'].to(u.m).m,
#             'pump_wl_meas': ds_spec['pump_wl_meas'].to(u.m).m,
#             'stokes_wl_meas': ds_spec['stokes_wl_meas'].to(u.m).m,
#             'wav_settle_time': ds_spec['wav_settle_time'].to(u.s),
#             'wavelength_set': ds_spec['wavelength_set'].to(u.m).m,
#             'spec': ds_spec['spec'].to(u.V).m,
#             'volt_meas': ds_spec['volt_meas'].to(u.V).m,
#             'raman_shift': ds_spec['raman_shift'].to(1/u.cm).m
#             }
#     io.savemat(file_dir, data)
#     return ds_spec

# def acquire_spectrum(num_avg, fsamp, wav_start, wav_stop, Δwav, fixed_wav, wav_settle_time=1*u.s,sample_dir=None, name=None):
#     """
#     Acquire spectrum by setting laser wavelength to new wavelength in sweep range (at a fixed spatial point)
#     Slower acquisition (i.e. for Solstis) - sets wavelength, waits for wavelength to settle before acquiring data
#     """
#     # Specify location of data save
#     sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
#     spath = new_path(name=name, data_dir=sample_dir, ds_type='Spectra', extension='h5', timestamp=True)
#     print("saving data to: ")
#     print(spath)
#
#     # Create 1d array of wavelengths
#     wavelength_set = np.arange(wav_start.m, wav_stop.m + Δwav.m, Δwav.m) * u.nm
#     wavelength_meas = []
#
#
#     # save sweep parameters to hdf5
#     dump_hdf5(
#         {'num_avg': num_avg,
#          'fsamp': fsamp,
#          'wav_start': wav_start,
#          'wav_stop': wav_stop,
#          'Δwav': Δwav,
#          'wav_settle_time': wav_settle_time,
#          'wavelength_set': wavelength_set,
#          'fixed_wav': fixed_wav
#          },
#         spath,
#         open_mode='x',
#     )
#
#     spec, tap_power = [], []
#     tuning_time = 15*u.s #estimated wavelength tuning time
#
#     # Create DAQ task
#     sweep_task = Task(
#         ch_Vsrs
#     )
#
#     # Set DAQ sampling rate and number of samples to write/read (for averaging)
#     sweep_task.set_timing(fsamp=fsamp, n_samples=num_avg)
#
#     # Print calculated sweep time
#     sweep_time = ((1 / fsamp).to(u.second) * num_avg + tuning_time) * wavelength_set.shape[0]
#     start_time = time.time()
#     end_time = start_time + sweep_time.m
#     print(f"sweep time: {sweep_time:3.2f}")
#     print(f"start time: {time.ctime(start_time):s}")
#     print(f"stop time: {time.ctime(end_time):s}")
#
#     remove_bs()
#
#     # Iterate over wavelengths
#     for wav in wavelength_set.m:
#         set_wavelength(wav*u.nm) #Set powermeter wavelength
#         laser.set_wavelength_instrumental(float(wav)) #Set laser wavelength
#         time.sleep(wav_settle_time.m)  # Wait for wavelength to settle
#         wavelength_meas.append(laser.get_wavelength()) #read actual wavelength
#         read_spec = sweep_task.run() #take num_avg daq readings, append average
#         time.sleep((1/fsamp).m*num_avg)  #Wait for daq to acquire readings
#         spec.append(np.mean(read_spec[ch_Vsrs_str].m))
#         power = get_power()
#         tap_power.append(power.m)
#
#     # Unreserve daq
#     sweep_task.unreserve()
#     wavelength_meas = wavelength_meas*u.nm
#
#     # Identify pump and stokes wavelengths
#     if np.max(wavelength_set.m) > fixed_wav.m:
#         stokes_wav = wavelength_meas
#         pump_wav = fixed_wav
#     elif np.max(wavelength_set.m) < fixed_wav.m:
#         stokes_wav = fixed_wav
#         pump_wav = wavelength_meas
#
#     # Calculate raman shift
#     raman_shift = (1 / pump_wav - 1 / stokes_wav).to(1 / u.cm)
#
#     # Save sweep data to hdf5
#     sweep_data = {
#         'spec': spec * u.volt,
#         'wavelength_meas': wavelength_meas,
#         'raman_shift': raman_shift,
#         'tap_power': tap_power * u.W
#     }
#     dump_hdf5(sweep_data, spath)
#
#     ds_spec = load_hdf5(fpath=spath)
#     return ds_spec

#def plot_spectra(ds_spec, figsize=(10,4.5), sg_win_len=50, sg_p_order=2):
#     """
#     Plot step spectra with OSA pump and stokes wavelength measurements
#     """
#     # raman_shift = ds_spec["raman_shift"]
#     pump_wl = np.mean(ds_spec["pump_wl_meas"].to(u.m).m)*u.m
#     stokes_wl = savgol_filter(ds_spec["stokes_wl_meas"].to(u.m).m, sg_win_len, sg_p_order)*u.m
#     raman_shift = (1 / pump_wl  - 1 / stokes_wl).to(1 / u.cm)
#     spec = ds_spec["spec"]
#     sensitivity = ds_spec["sens_lia"]
#     offset = 0 * u.V
#     spec_calib = (spec / 10 + offset) * (sensitivity).to(u.V).m
#     # tap_power = ds_spec["tap_power"]
#     wavelength_set = ds_spec["wavelength_set"]
#     # wavelength_meas = ds_spec["wavelength_meas"]

#     # Correct for wavelength-dependent power
#     # power_corr = tap_power.m / tap_power[0].m
#     # spec_corr = spec * power_corr

#     fig, ax = plt.subplots(1, 1, figsize=figsize)
#     ax.plot(raman_shift.m, spec_calib.m)
#     ax.set_xlabel("Raman Shift [1/cm]")
#     ax.set_ylabel("Voltage [V]")
#     ax.set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))

#     # ax[1].plot(wavelength_meas.m, spec.m)
#     # ax[1].set_xlabel("Wavelength [nm]")
#     # ax[1].set_ylabel("Voltage [V]")
#     # ax[1].set_xlim((np.min(wavelength_meas.m), np.max(wavelength_meas.m)))
#     #
#     # ax[2].plot(wavelength_set.m, wavelength_meas.m)
#     # ax[2].set_xlabel("Set Wavelength [nm]")
#     # ax[2].set_ylabel("Measured Wavelength [nm]")
#     # ax[2].set_xlim((np.min(wavelength_set.m), np.max(wavelength_set.m)))
#     return fig

