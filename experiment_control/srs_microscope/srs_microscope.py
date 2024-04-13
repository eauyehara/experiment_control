import os
import time
import numpy as np
import sys
import clr

sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.FilterFlipperCLI")

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.interpolate import griddata
from scipy.optimize import curve_fit
from scipy.stats import norm
from scipy import io

# import stuff from instrumental
from instrumental import instrument
from instrumental.drivers.daq.ni import Task # NIDAQ,
from instrumental.drivers.motion.filter_flipper import Position
from photonmover.instruments.Lasers.M2_solstis import M2_Solstis
# from instrumental.drivers.lasers import m2_solstis
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
ff = instrument("Thorlabs_FilterFlipper", reopen_policy='reuse')
cam = instrument('Thorlabs_camera', reopen_policy='reuse')
stage = instrument("NanoMax_stage", reopen_policy='reuse')
laser = M2_Solstis()
laser.initialize()

# Directory for data save
# data_dir = os.path.join(home_dir,"Documents","data","srs_microscope")
data_dir = os.path.join(home_dir,"Dropbox (MIT)","POE","srs_microscope_data","srs_microscope_scans")

# Configure DAQ output channels for differential (0V-centered) control of x and y galvo mirrors
ch_Vx_p, ch_Vx_p_str = daq.ao0, 'Dev2/ao0'
ch_Vx_n, ch_Vx_n_str = daq.ao1, 'Dev2/ao1'
ch_Vy_p, ch_Vy_p_str = daq.ao2, 'Dev2/ao2'
ch_Vy_n, ch_Vy_n_str = daq.ao3, 'Dev2/ao3'

# Configure DAQ input channels
ch_Vsrs, ch_Vsrs_str = daq.ai0, 'Dev2/ai0'
ch_Vx_meas, ch_Vx_meas_str = daq.ai2, 'Dev2/ai2'
ch_Vy_meas, ch_Vy_meas_str = daq.ai3, 'Dev2/ai3'

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

""" Pump Laser Power """
# def get_excitation_power(center=True):
#     if center:
#         Vx_init, Vy_init = get_spot_pos()
#         center_spot()
#     P = get_power() / pm_attn
#     if center:
#         move_spot(Vx_init,Vy_init)
#     return P.to(u.mW)

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
def scan_single_axis(scan_length, axis, step_size, wait=1 * u.s, fsamp = 3*u.Hz, num_avg=10):
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
    print(f"scan time: {scan_time:3.2f}")

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


def knife_edge_scan(scan_length, axis, step_size, wait=1*u.s, num_avg=10, sample_dir=None, name=None):
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
    [pos_arr, pd_arr] = scan_single_axis(scan_length, axis, step_size, wait=wait, num_avg=num_avg)

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
    fig = plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.binary)
    return fig


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


def configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp):
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

    # Create DAQ task
    scan_task = Task(
        ch_Vx_p,
        ch_Vx_n,
        ch_Vy_p,
        ch_Vy_n,
        ch_Vsrs,
        ch_Vx_meas,
        ch_Vy_meas
    )

    # Set DAQ sampling rate and number of samples to write/read
    scan_task.set_timing(fsamp=fsamp,n_samples=nx*ny)

    # Print calculated scan time
    scan_time = (1/fsamp).to(u.second)*nx*ny
    print(f"scan time: {scan_time:3.2f}")

    # Create dictionary of data to write to each DAQ output channel
    write_data = {
        ch_Vx_p_str :   Vx_scan / Vmeas_Vwrite,
        ch_Vx_n_str :   -Vx_scan / Vmeas_Vwrite,
        ch_Vy_p_str :   Vy_scan / Vmeas_Vwrite,
        ch_Vy_n_str :   -Vy_scan / Vmeas_Vwrite,
    }

    return scan_task, write_data


def collect_Rscan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,name=None,sample_dir=None,wf_exposure_time=10*u.ms):
    """
    Collects reflection scan. 
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
    scan_task, write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp)
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


def collect_Tscan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,wf_img,laser_spot_img,name=None,sample_dir=None,wf_exposure_time=10*u.ms):
    """
    Collects trasmission scan. (No trasmission flipper yet - manually acquire widefield/laser spot image beforehand).
    Runs DAQ task - writes voltage arrays to galvos and reads srs signal / galvo scanner position. Processes data and dumps write_data, read_data, and proc_data to hdf5 file.
    Saves png image of scan. Loads hdf5 file and returns dataset ds. Recenters spot after scan
    :return: ds
    """
    #Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='GalvoScan',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)

#     wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time=wf_exposure_time)
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
    scan_task, write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp)
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


def process_scan(read_data,nx,ny,ΔVx,ΔVy,Vx0=Vx0,Vy0=Vy0):
    """
    Parses read_data dict and writes into variables.  Creates meshgrids of set Vx and Vy write scan voltages and interpolates Vsrs data at these points from measured Vx and Vy.
    Converts galvo voltages to position in microns (x, y).
    :return: proc_data: dictionary of processed data
    """
    t = read_data['t']
    Vsrs = read_data[ch_Vsrs_str]
    # Vsrs_y = read_data[ch_Vsrs_y_str]
    # Vpm  = read_data[ch_Vpm_str]
    Vx_meas = read_data[ch_Vx_meas_str]  #J6P1 (scanner position) on x galvo board
    Vy_meas = read_data[ch_Vy_meas_str]  #J6P1 (scanner position) on y galvo board
    # Vx_scan = write_data[ch_Vx_p_str] - write_data[ch_Vx_n_str]
    # Vy_scan = write_data[ch_Vy_p_str] - write_data[ch_Vy_n_str]
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    Vx_g, Vy_g = np.meshgrid(Vx.m,Vy.m)
    Vsrs_g = griddata((Vx_meas.m, Vy_meas.m), Vsrs.m, (Vx_g, Vy_g)) * u.volt
    # Vshg_y_g = griddata((Vx_meas.m,Vy_meas.m),Vshg_y.m,(Vx_g,Vy_g))*u.volt  #quadrature output of lock-in

    x = ((Vx-Vx0)*dx_dVx).to(u.um)
    y = ((Vy-Vy0)*dy_dVy).to(u.um)
    # Pave_shg = (Pave_per_Vx_ref * Vshg_x_g).to(u.picowatt)

    proc_data = {
        "Vx"      : Vx,
        "Vy"      : Vy,
        "dx_dVx"  : dx_dVx,
        "dy_dVy"  : dy_dVy,
        "Vsrs_g": Vsrs_g,
        # "Vshg_y_g": Vshg_y_g,
        "x"       : x,
        "y"       : y,
        # "Pave_shg"       : Pave_shg,
    }
    return proc_data


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
    pd_arr = ds_spot["pd_arr"].m

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
def img_max_pixel_inds(img):
    """
    Return (x,y) indices for laser spot location
    """
    return np.unravel_index(np.argmax(img),img.shape)


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


def plot_scan_data(ds,wf_cmap=cm.binary,laser_cmap=cm.Reds, srs_cmap=cm.inferno):
    """
    Plot 2x1 subplots with [0] laser spot superimposed on cropped widefield image, and [1] SRS image
    :param ds: from collect_scan()
    :return: fig with (2) subplots
    """
    laser_cmap = transparent_cmap(laser_cmap)
    fig, ax = plt.subplots(2,1, figsize = (10,10))
    
    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    x_off = 10
    y_off = 40
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
    p0 = ax[1].pcolormesh(ds["y"].m, ds["x"].m, np.flipud(np.transpose(ds["Vsrs_g"].m)), cmap=srs_cmap)
    cb1 = plt.colorbar(p0, ax=ax[1])
    ax[1].set_aspect("equal")

    plt.show()
    return fig


def plot_widefield_img(img, wf_cmap=cm.binary):
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


def plot_laser_widefield_img(wf_img, laser_spot_img, wf_cmap=cm.binary, laser_cmap=cm.Reds):
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


def plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.binary, laser_cmap=cm.Reds):
    """
    Plot widefield image with laser spot (before acquiring scan data) cropped to scan area, axis centered around laser spot
    :param laser_spot_img: from laser_spot_images(); Vx, Vy: from scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes(laser_spot_img)
    
    # Find wf image indices corresponding to scan area, add manual offset to match scan area
    i_xmax, i_xmin, i_ymax, i_ymin = scan_volt_to_wf_inds(Vx, Vy, laser_spot_img)
    x_off = 10
    y_off = 40
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
        plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
            orientation='portrait', papertype=None, format=format,
            transparent=True, bbox_inches=None, pad_inches=0.5)
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
    x_off = 10
    y_off = 40
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
    plot_widefield_img(img)
    x_img,y_img = img_spatial_axes(img)
    X = x_img
    Y = y_img
    Z = (img,)
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

""" Spectral Acquisition """
def acquire_spectrum(sample_dir, name, num_avg, fsamp, wav_start, wav_stop, Δwav, fixed_wav, wav_settle_time=30*u.s):
    """
    Acquire spectra by sweeping laser wavelength at a single point
    If averaging multiple measurements at each wavelength,
    """
    # Specify location of data save
    sample_dir = resolve_sample_dir(sample_dir, data_dir=data_dir)
    spath = new_path(name=name, data_dir=sample_dir, ds_type='Spectra', extension='h5', timestamp=True)
    print("saving data to: ")
    print(spath)

    # Create 1d array of wavelengths
    wavelengths = np.arange(wav_start.m, wav_stop.m + Δwav.m, Δwav.m) * u.nm

    # Identify pump and stokes wavelengths
    if np.max(wavelengths.m) > fixed_wav.m:
        stokes_wav = wavelengths
        pump_wav = fixed_wav
    elif np.max(wavelengths.m) < fixed_wav.m:
        stokes_wav = fixed_wav
        pump_wav = wavelengths

    # Calculate raman shift
    raman_shift = (1 / pump_wav - 1 / stokes_wav).to(1 / u.cm)

    # save sweep parameters to hdf5
    dump_hdf5(
        {'num_avg': num_avg,
         'fsamp': fsamp,
         'wav_start': wav_start,
         'wav_stop': wav_stop,
         'Δwav': Δwav,
         'wav_settle_time': wav_settle_time,
         'wavelengths': wavelengths,
         'fixed_wav': fixed_wav,
         'raman_shift': raman_shift,
         },
        spath,
        open_mode='x',
    )

    spec, tap_power = [], []

    # Create DAQ task
    sweep_task = Task(
        ch_Vsrs
    )

    # Set DAQ sampling rate and number of samples to write/read (for averaging)
    sweep_task.set_timing(fsamp=fsamp, n_samples=num_avg)

    # Print calculated sweep time
    sweep_time = ((1 / fsamp).to(u.second) * num_avg + wav_settle_time) * wavelengths.shape[0]
    print(f"sweep time: {sweep_time:3.2f}")

    # Iterate over wavelengths
    for wav in wavelengths.m:
        set_wavelength(wav*u.nm) #Set powermeter wavelength
        laser.set_wavelength_instrumental(float(wav)) #Set laser wavelength
        time.sleep(1)  # Wait for wavelength to settle
        read_spec = sweep_task.run() #take num_avg daq readings, append average
        time.sleep((1/fsamp).m*num_avg)  #Wait for daq to acquire readings
        spec.append(np.mean(read_spec[ch_Vsrs_str].m))
        power = get_power()
        tap_power.append(power.m)

    # Unreserve daq
    sweep_task.unreserve()

    # Save sweep data to hdf5
    sweep_data = {
        'spec': spec * u.volt,
        'tap_power': tap_power * u.W
    }
    dump_hdf5(sweep_data, spath)

    ds_spec = load_hdf5(fpath=spath)
    return ds_spec

def plot_spectra(ds_spec, figsize=(7,4.5)):
    raman_shift = ds_spec["raman_shift"]
    spec = ds_spec["spec"]
    tap_power = ds_spec["tap_power"]
    wavelengths = ds_spec["wavelengths"]

    # Correct for wavelength-dependent power
    power_corr = tap_power.m / tap_power[0].m
    spec_corr = spec * power_corr

    fig, ax = plt.subplots(3, 1, figsize=figsize)
    ax[0].plot(raman_shift.m, spec_corr.m)
    ax[0].set_xlabel("Raman Shift [1/cm]")
    ax[0].set_ylabel("Voltage [V]")
    ax[0].set_xlim((np.min(wavelengths), np.max(wavelengths)))

    ax[1].plot(raman_shift.m, spec.m)
    ax[1].set_xlabel("Raman Shift [1/cm]")
    ax[1].set_ylabel("Voltage [V]")
    ax[1].set_xlim((np.min(wavelengths), np.max(wavelengths)))

    ax[2].plot(wavelengths.m, spec.m)
    ax[2].set_xlabel("Wavelengths [nm]")
    ax[2].set_ylabel("Voltage [V]")
    ax[2].set_xlim((np.min(wavelengths), np.max(wavelengths)))
    return fig