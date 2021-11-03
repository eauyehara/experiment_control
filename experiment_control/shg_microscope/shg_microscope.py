
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.interpolate import griddata
from scipy.optimize import curve_fit

# import stuff from instrumental
from instrumental import instrument
from instrumental.drivers.daq.ni import Task # NIDAQ,
from instrumental.drivers.motion.filter_flipper import Position
from instrumental.drivers.lockins import sr844
# from instrumental.drivers.motion.filter_flipper import FilterFlipper

from ..util.units import Q_, u
from ..util.io import *
from .zelux import grab_image
from .powermeter import get_power

daq     = instrument("NIDAQ_USB-6259")
# daq2    = instrument('DAQ2_NIDAQ_USB-6259_21146242')
ff      = instrument("Thorlabs_FilterFlipper_1")
lockin  = instrument("SRS844")
pol_hwp = instrument("Thorlabs_TDC001")
pow_hwp = instrument('KDC101')

# data_dir = os.path.join(home_dir,"data","shg_microscope")
data_dir = os.path.join(home_dir,"Dropbox (MIT)","data","shg_microscope")

# Configure DAQ output channels for differential (0V-centered) control of x and y galvo mirrors
ch_Vx_p, ch_Vx_p_str = daq.ao0, 'Dev1/ao0'
ch_Vx_n, ch_Vx_n_str = daq.ao1, 'Dev1/ao1'
ch_Vy_p, ch_Vy_p_str = daq.ao2, 'Dev1/ao2'
ch_Vy_n, ch_Vy_n_str = daq.ao3, 'Dev1/ao3'

daq.port0.as_output()


# Configure DAQ input channels
ch_Vshg_x, ch_Vshg_x_str   = daq.ai0, 'Dev1/ai0'
ch_Vshg_y, ch_Vshg_y_str   = daq.ai1, 'Dev1/ai1'
ch_Vx_meas, ch_Vx_meas_str = daq.ai2, 'Dev1/ai2'
ch_Vy_meas, ch_Vy_meas_str = daq.ai3, 'Dev1/ai3'
ch_Vpm, ch_Vpm_str         = daq.ai4, 'Dev1/ai4'
ch_Vcw, ch_Vcw_str         = daq.ai7, 'Dev1/ai7'

#

### calibration data (manual for now) ###
## galvo voltages for centered output beam, given centered input beam
Vx0, Vy0    =   2.665*u.volt   ,       1.427*u.volt

## Galvo scan distance/voltage calibrations ##
# using Nikon 20x objective with cover slip, 1deg/V galvo setting and 4um period poling electrodes, 09/06/2021
dx_dVx =  174.7178 * u.um / u.volt
dy_dVy = 172.72 * u.um / u.volt
dx_dpix =  0.3651 * u.um # per pixel

## silver 90° prism transmission attenuation for power meter head above objective turret
P_pmcal_prism_in_875nm_bg = 1.04558 * u.nW
P_pmcal_prism_in_875nm =  58.87976 * u.nW
P_pmcal_prism_out_875nm =  50.7934 * u.mW
pm_attn = ((P_pmcal_prism_in_875nm-P_pmcal_prism_in_875nm_bg) / P_pmcal_prism_out_875nm).to(u.dimensionless).m
# pm_attn =  1.1386e-6 # @ 875nm

# Excitation Power HWP orientation
θ_pow_hwp_min = 53*u.degree
θ_pow_hwp_max = θ_pow_hwp_min + 45*u.degree


## SHG detection gain
# using Thorlabs APD430A2 DC-400MHz APD
resp_APD430A2 = 28 * u.ampere/u.watt # at 437.5nm
tia_gain_APD430A2 = 10 * u.kilovolt / u.ampere
gain_SR445A = 25
# lockin voltage at Mira fundamental (875nm) for 1uW ave power input measured
# with the same detector/gain (APD430A2 @ max (100x) avalanche gain) and analog
# amplification (25x,SR445A) and 2x BBP-70+ 70-80MHz band pass filters before
# lockin input. Vpp measured directly scope @ ~1.45V.
# Reference waveforms saved.
Vx_ref_1uWave = 0.696 * u.volt
Vpeak_ref_1uWave = 1.45 * u.volt
Vave_ref_1uWave = 170*u.mV
Vpeak_per_Vx_lia =  (Vpeak_ref_1uWave / Vx_ref_1uWave).to(u.dimensionless).m
Vpeak_per_Vave_scope =  (Vpeak_ref_1uWave / Vave_ref_1uWave).to(u.dimensionless).m
Pave_per_Vx_ref = (1 * u.uW) / Vx_ref_1uWave


# trans_BP70plus
VperW_shg = (gain_SR445A*tia_gain_APD430A2*resp_APD430A2).to(u.volt/u.watt)

def_lockin_config = {
    "ReferenceSource": sr844.ReferenceSource.external,
    "Sensitivity": sr844.Sensitivity.x300uV,
    "TimeConstant": sr844.TimeConstant.x300us,
    "LowPassSlope": sr844.LowPassSlope.six_dB_per_octave,
    "Ch1OutputSource": sr844.Ch1OutputSource.X,
    "Ch2OutputSource": sr844.Ch2OutputSource.Y,
    "ScanMode": sr844.ScanMode.loop,
    "TriggerStartScanMode": sr844.TriggerStartScanMode.no,
    "ReserveMode": sr844.ReserveMode.on,
    # "WideReserveMode": sr844.WideReserveMode.low_noise,
    # "CloseReserveMode": sr844.CloseReserveMode.low_noise,
    # "AlarmMode": sr844.AlarmMode.off,
    # "ExpandSelector": sr844.ExpandSelector.x1,
}

def configure_lockin(conf=def_lockin_config):
    lockin.set_reference_source(conf["ReferenceSource"])
    lockin.set_sensitivity(conf["Sensitivity"])
    lockin.set_time_constant(conf["TimeConstant"])
    lockin.set_low_pass_slope(conf["LowPassSlope"])
    lockin.set_ch1_output_source(conf["Ch1OutputSource"])
    lockin.set_ch2_output_source(conf["Ch2OutputSource"])
    # lockin.set_scan_mode(conf["ScanMode"])
    # lockin.set_trigger_start_scan_mode(conf["TriggerStartScanMode"])
    lockin.set_reserve_mode(conf["ReserveMode"])
    # lockin.set_wide_reserve(conf["WideReserveMode"])
    # lockin.set_close_reserve(conf["CloseReserveMode"])
    # lockin.set_reference_source(conf["AlarmMode"])
    # lockin.set_reference_source(conf["ExpandSelector"])
    return

"""
Query lockin time constant twice, as it seems to have bugs
"""
def lockin_time_constant(wait=10*u.ms):
    tc0 = Q_(lockin.get_time_constant().name[1:])
    time.sleep(wait.to(u.second).m)
    tc1 = Q_(lockin.get_time_constant().name[1:])
    return tc1

# configure filter flipper positions
ff_pos_out = Position.one
ff_pos_in  = Position.two

## SHG microscope data i/o
,data_dir=data_dir
# def resolve_sample_dir(sample_dir,data_dir=data_dir):
#     if sample_dir is None:
#         return newest_subdir(data_dir)
#     elif not(os.path.isdir(sample_dir)):
#         newest = newest_subdir(data_dir=data_dir,filter=("_".join(["Sample",sample_dir])+'*'))
#         if newest:
#             sample_dir = newest
#         else:
#             sample_dir = new_path(name=sample_dir,ds_type="Sample",data_dir=data_dir)
#             os.mkdir(sample_dir)
#         return sample_dir
#     else:
#         return sample_dir
#
# def resolve_fpath(filter,fpath,sample_dir,data_dir=data_dir):
#     if fpath is None:
#         if sample_dir is None:
#             return newest_file(data_dir=newest_subdir(data_dir),filter=filter)
#         else:
#             return newest_file(data_dir=sample_dir,filter=filter)
#     else:
#         return fpath



## Widefield imaging ##

def remove_bs():
    ff.move_and_wait(ff_pos_out)

def insert_bs():
    ff.move_and_wait(ff_pos_in)

def wf_illum_on():
    daq.port0.write(0x01)

def wf_illum_off():
    daq.port0.write(0x00)

def wf_image(exposure_time=3*u.ms,laser_spot=False):
    wf_illum_init = daq.port0.read()
    θ_pow_hwp_init = pow_hwp.position
    wf_illum_on()
    if laser_spot:
        maximize_excitation_power()
    else:
        minimize_excitation_power()
    insert_bs()
    img = grab_image(exposure_time)
    remove_bs()
    pow_hwp.move_to(θ_pow_hwp_init,wait=True)
    if not wf_illum_init:
        wf_illum_off()
    return img

def laser_spot_image(exposure_time=3*u.ms):
    wf_illum_init = daq.port0.read()
    θ_pow_hwp_init = pow_hwp.position
    maximize_excitation_power()
    insert_bs()
    wf_illum_off()
    img = grab_image(exposure_time)
    remove_bs()
    if wf_illum_init:
        wf_illum_on()
    pow_hwp.move_to(θ_pow_hwp_init,wait=True)
    return img

def wf_and_laser_spot_images(exposure_time=3*u.ms):
    wf_illum_init = daq.port0.read()
    θ_pow_hwp_init = pow_hwp.position
    maximize_excitation_power()
    insert_bs()
    wf_illum_off()
    laser_spot_img = grab_image(exposure_time)
    wf_illum_on()
    minimize_excitation_power()
    wf_img = grab_image(exposure_time)
    remove_bs()
    if not wf_illum_init:
        wf_illum_off()
    pow_hwp.move_to(θ_pow_hwp_init,wait=True)
    return wf_img, laser_spot_img

def img_max_pixel_inds(img):
    return np.unravel_index(np.argmax(img),img.shape)

def img_spatial_axes(laser_spot_img,dx_dpix=dx_dpix):
    x_pix_laser, y_pix_laser = img_max_pixel_inds(laser_spot_img)
    npix_x,npix_y = laser_spot_img.shape
    x_img, y_img = dx_dpix*(np.arange(npix_x)-x_pix_laser), dx_dpix*(np.arange(npix_y)-y_pix_laser)
    return x_img, y_img

## Excitation Laser Power ##

def get_excitation_power(center=True):
    if center:
        Vx_init, Vy_init = get_spot_pos()
        center_spot()
    P = get_power() / pm_attn
    if center:
        move_spot(Vx_init,Vy_init)
    return P.to(u.mW)

def pow_hwp_scan(n_angles=100):
    center_spot()
    old_pol_angle = pow_hwp.position
    θ = np.linspace(1,359,n_angles)*u.degree
    P = np.zeros(len(θ))*u.watt
    for tind,tt in enumerate(θ):
        print(f"moving to θ = {tt.m:3.2f} deg...")
        t_start = time.time()
        pow_hwp.move_to(tt,wait=True)
        dt = time.time() - t_start
        print(f"...moved to θ = {tt.m:3.2f} deg in {dt:2.2f} seconds")
        print(f"collecting P_excitation...")
        t_start = time.time()
        P[tind] = get_excitation_power(center=False)
        dt = time.time() - t_start
        print(f"...collected P_excitation = {P[tind].m_as(u.watt):3.2g} W in {dt:2.1g} seconds")
    pow_hwp.move_to(old_pol_angle,wait=False)
    return θ, P

def minimize_excitation_power(wait=True):
    pow_hwp.move_to(θ_pow_hwp_min,wait=wait)

def maximize_excitation_power(wait=True):
    pow_hwp.move_to(θ_pow_hwp_max,wait=wait)

## SHG Power ##

def get_shg_Vx(n_samples=100,time_constant=None):
    if time_constant is None:
        time_constant = lockin_time_constant()
    out = ch_Vshg_x.read(
        fsamp=(1/lockin_time_constant()).to(u.Hz),
        n_samples=n_samples,
        )
    return (out[ch_Vshg_x_str].mean()/(10*u.volt)).to(u.dimensionless) * lockin.sensitivity

def get_shg_Vy(n_samples=100,time_constant=None):
    if time_constant is None:
        time_constant = lockin_time_constant()
    out = ch_Vshg_y.read(
        fsamp=(1/lockin_time_constant()).to(u.Hz),
        n_samples=n_samples,
        )
    return (out[ch_Vshg_y_str].mean()/(10*u.volt)).to(u.dimensionless) * lockin.sensitivity


## Polarization ##

def polarization_scan(n_angles=100,n_samples=50,time_constant=3*u.ms,wait=100*u.ms):
    center_spot()
    old_pol_angle = pol_hwp.get_position()
    old_time_constant = lockin.get_time_constant()
    lockin.time_constant = time_constant
    # assert lockin_time_constant() == time_constant
    time.sleep(wait.to(u.second).m)
    tc_check = lockin_time_constant()
    print(f"lockin time constant: {tc_check:3.1g}")
    θ = np.linspace(1,359,n_angles)*u.degree
    Pshg = np.zeros(len(θ))*u.watt
    for tind,tt in enumerate(θ):
        print(f"moving to θ = {tt.m:3.2f} deg...")
        t_start = time.time()
        pol_hwp.move_and_wait(tt)
        dt = time.time() - t_start
        print(f"...moved to θ = {tt.m:3.2f} deg in {dt:2.2f} seconds")
        print(f"collecting Vx average...")
        t_start = time.time()
        Pshg[tind] = (get_shg_Vx(n_samples=n_samples,time_constant=time_constant) / VperW_shg).to(u.pW)
        dt = time.time() - t_start
        print(f"...collected Pshg = {Pshg[tind].m:3.2g} pW in {dt:2.1g} seconds")
    lockin.set_time_constant(old_time_constant)
    pol_hwp.move_and_wait(old_pol_angle)
    return θ, Pshg


def collect_polarization_scan(sample_dir=None,n_angles=100,n_samples=50,time_constant=3*u.ms,wait=100*u.ms):
    sample_dir = resolve_sample_dir(sample_dir,data_dir=data_dir)
    fpath = new_path(dir=sample_dir,identifier_string="PolScan",extension='.csv')
    # fname = "pol_scan_" + timestamp() + ".csv"
    # fpath = os.path.normpath(os.path.join(shg_data_dir,sample_dir,fname))
    θ, Pshg = polarization_scan(n_angles=n_angles,n_samples=n_samples,time_constant=time_constant,wait=wait)
    print("saving pol. scan data:")
    print("\t"+fpath)
    np.savetxt(fpath,(θ.m,Pshg.to(u.watt).m),delimiter=',')
    return θ, Pshg

def load_polarization_scan(fpath=None,sample_dir=None):
    θ_deg, Pshg_W = np.loadtxt(resolve_fpath("PolScan*.csv",fpath,sample_dir,data_dir=data_dir),delimiter=',')
    return θ_deg*u.degree, Pshg_W*u.watt

def pol_dep(x,a,x0):
     return a * np.cos(2*np.deg2rad(x + x0))**4

def find_sample_axes(sample_dir=None,n_angles=100,n_samples=50,time_constant=3*u.ms,wait=100*u.ms):
    θ_meas, Pshg_meas = collect_polarization_scan(sample_dir=sample_dir,n_angles=n_angles,n_samples=n_samples,time_constant=time_constant,wait=wait)
    popt,pcov = curve_fit(pol_dep,θ_meas.m,Pshg_meas.m,p0=[Pshg_meas.m.max(),180.0])
    Pshg_fit = Q_(popt[0],Pshg_meas.units)
    θsamp_fit = popt[1] * u.degree
    print(f"θsamp_fit = {θsamp_fit.m:3.1f}°")
    #plt.plot(th2.m,P2.m); plt.plot(th_fit,pol_dep(th_fit,*popt)); plt.show()
    return θsamp_fit


## Galvo Motion ##

def move_spot(Vx,Vy,Vx0=Vx0,Vy0=Vy0,wait=True,Verr=0.001*u.volt,t_polling=10*u.ms):
    Vx_target, Vy_target = (Vx+Vx0), (Vy+Vy0)
    ch_Vx_p.write(Vx_target/2)
    ch_Vx_n.write(-Vx_target/2)
    ch_Vy_p.write(Vy_target/2)
    ch_Vy_n.write(-Vy_target/2)
    if wait:
        time.sleep(t_polling.m_as('s'))
        # while abs(ch_Vx_meas.read()-Vx_target)>Verr or abs(ch_Vy_meas.read()-Vy_target)>Verr:
        #     time.sleep(t_polling.m_as('s'))
    return

def center_spot(Vx0=Vx0,Vy0=Vy0):
    move_spot(0*u.volt,0*u.volt,Vx0=Vx0,Vy0=Vy0)
    return

def get_spot_pos(Vx0=Vx0,Vy0=Vy0):
    Vx = 2*ch_Vx_p.read() - Vx0
    Vy = 2*ch_Vy_p.read() - Vy0
    return Vx, Vy

## Scanning SHG image acquisition ##

def scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0):
    Vx0V = Vx0.to(u.volt).m
    ΔVxV = ΔVx.to(u.volt).m
    Vy0V = Vy0.to(u.volt).m
    ΔVyV = ΔVy.to(u.volt).m
    Vx = np.linspace(Vx0V-(ΔVxV/2.0),Vx0V+(ΔVxV/2.0),nx)*u.volt
    Vy = np.linspace(Vy0V-(ΔVyV/2.0),Vy0V+(ΔVyV/2.0),ny)*u.volt
    return Vx, Vy

def raster_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0):
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    Vx_scan = np.tile(np.concatenate((Vx.m,Vx.m[::-1])),ny//2)*u.volt
    Vy_scan = np.repeat(Vy.m,nx)*u.volt
    return Vx_scan, Vy_scan

def configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp):
    Vx_scan, Vy_scan = raster_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    scan_task = Task(
        ch_Vx_p,
        ch_Vx_n,
        ch_Vy_p,
        ch_Vy_n,
        ch_Vshg_x,
        ch_Vshg_y,
        ch_Vx_meas,
        ch_Vy_meas,
        # ch_Vpm,
    )
    scan_task.set_timing(fsamp=fsamp,n_samples=nx*ny)

    scan_time = (1/fsamp).to(u.second)*nx*ny
    print(f"scan time: {scan_time:3.2f}")

    write_data = {
        ch_Vx_p_str :   Vx_scan/2,
        ch_Vx_n_str :   -Vx_scan/2,
        ch_Vy_p_str :   Vy_scan/2,
        ch_Vy_n_str :   -Vy_scan/2,
    }

    return scan_task, write_data

def process_scan(read_data,nx,ny,ΔVx,ΔVy,Vx0=Vx0,Vy0=Vy0):
    t = read_data['t']
    Vshg_x = read_data[ch_Vshg_x_str]
    Vshg_y = read_data[ch_Vshg_y_str]
    # Vpm  = read_data[ch_Vpm_str]
    Vx_meas = read_data[ch_Vx_meas_str]
    Vy_meas = read_data[ch_Vy_meas_str]
    # Vx_scan = write_data[ch_Vx_p_str] - write_data[ch_Vx_n_str]
    # Vy_scan = write_data[ch_Vy_p_str] - write_data[ch_Vy_n_str]
    Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    Vx_g, Vy_g = np.meshgrid(Vx.m,Vy.m)
    Vshg_x_g = griddata((Vx_meas.m,Vy_meas.m),Vshg_x.m,(Vx_g,Vy_g))*u.volt
    Vshg_y_g = griddata((Vx_meas.m,Vy_meas.m),Vshg_y.m,(Vx_g,Vy_g))*u.volt
    proc_data = {
        "Vx"      : Vx,
        "Vy"      : Vy,
        "dx_dVx"  : dx_dVx,
        "dy_dVy"  : dy_dVy,
        "x"       : ((Vx-Vx0)*dx_dVx).to(u.um),
        "y"       : ((Vy-Vy0)*dy_dVy).to(u.um),
        "Vshg_x_g": Vshg_x_g,
        "Vshg_y_g": Vshg_y_g,
    }
    return proc_data

def collect_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp,name=None,sample_dir=None,wf_exposure_time=3*u.ms):
    maximize_excitation_power()
    sample_dir = resolve_sample_dir(sample_dir,data_dir=data_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='GalvoScan',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)
    θ_pow_hwp   = pow_hwp.position
    θ_pol_hwp   = pol_hwp.get_position()
    P_ex        = get_excitation_power()
    wf_img, laser_spot_img = wf_and_laser_spot_images(exposure_time=wf_exposure_time)
    x_img,y_img = img_spatial_axes(laser_spot_img)
    dump_hdf5(
        {   'wf_img': wf_img.astype("int"),
            'laser_spot_img': laser_spot_img.astype("int"),
            'dx_dpix': dx_dpix,
            'x_img': x_img,
            'y_img': y_img,
            'θ_pow_hwp': θ_pow_hwp,
            'θ_pol_hwp': θ_pol_hwp,
            'P_ex': P_ex,
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
    return ds

## Plotting ##

"""
generate colormap `cmap_tr` with graded transparency (transparent at 0, opaque
at maximum) from input colormap `cmap` for 2D heatmap overlays
"""
def transparent_cmap(cmap):
    cmap_tr = cmap(np.arange(cmap.N))
    cmap_tr[:,-1] = np.linspace(0, 1, cmap.N)
    cmap_tr = ListedColormap(cmap_tr)
    return cmap_tr

def wf_img_inds(ds):
    i_xmax = np.nanargmin(np.abs(ds['x_img'] - ds['x'].max()))
    i_xmin = np.nanargmin(np.abs(ds['x_img'] - ds['x'].min()))
    i_ymax = np.nanargmin(np.abs(ds['y_img'] - ds['y'].max()))
    i_ymin = np.nanargmin(np.abs(ds['y_img'] - ds['y'].min()))
    return i_xmax, i_xmin, i_ymax, i_ymin

def plot_scan_data(ds,wf_cmap=cm.binary,laser_cmap=cm.Reds):
    laser_cmap = transparent_cmap(laser_cmap)
    fig, ax = plt.subplots(2,2)
    im0 = ax[0,0].pcolormesh(ds["x_img"],ds["y_img"],ds["wf_img"].transpose(),cmap=wf_cmap)
    im1  = ax[0,0].pcolormesh(ds["x_img"],ds["y_img"],ds["laser_spot_img"].transpose(),cmap=laser_cmap)
    # cb1 = plt.colorbar(im1,ax=ax[1,0])
    ax[0,0].set_aspect("equal")
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    p0 = ax[0,1].pcolormesh(ds["x"].m,ds["y"].m,ds["Vshg_x_g"].m)
    cb0 = plt.colorbar(p0,ax=ax[0,1])
    ax[0,1].set_aspect("equal")
    im2 = ax[1,1].pcolormesh(ds["x_img"][i_xmin:i_xmax],ds["y_img"][i_ymin:i_ymax],ds["wf_img"][i_xmin:i_xmax,i_ymin:i_ymax].transpose(),cmap=wf_cmap)
    im3  = ax[1,1].pcolormesh(ds["x_img"][i_xmin:i_xmax],ds["y_img"][i_ymin:i_ymax],ds["laser_spot_img"][i_xmin:i_xmax,i_ymin:i_ymax].transpose(),cmap=laser_cmap)
    cb3 = plt.colorbar(im3,ax=ax[1,1])
    ax[1,1].set_aspect("equal")
    plt.show()
    return fig
