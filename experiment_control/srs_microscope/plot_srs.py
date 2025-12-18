import os
import time
import numpy as np
import sys
import xarray as xr

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.interpolate import griddata
from scipy.optimize import curve_fit
from scipy.stats import norm
from scipy import io
from copy import deepcopy

from ..util.units import Q_, u
from ..util.io import *         # hdf5 utilites

mpl.rcParams.update({'axes.labelsize': 20,'font.size': 16 , 'font.family': "arial", "font.style": "normal", "font.weight": "bold", "axes.labelweight": "bold", "lines.linewidth": 2})#, 'font.serif': "cm"})
mpl.rc('xtick', labelsize=16) 
mpl.rc('ytick', labelsize=16)

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

# Directory for data save
data_dir = os.path.join(home_dir,"Dropbox (MIT)","POE","srs_microscope_data","srs_microscope_scans")
calib_dir = os.path.join(home_dir, "Documents", "Github","experiment_control","calibration_data","VCSEL_calibration")

# wavvolt_file = os.path.join(calib_dir, "wavvolt16_dev1b_15C_OE1076_0.00mW_2025-11-1.mat") #For wavelength set
# wavvolt_HVCALIB = os.path.join(calib_dir, "wavvolt_HVCALIB_GSdev1b_delayvolt16_BOA700mA_2025-11-2.mat") #For post-acquisition wavelength calibration
# wavvolt_sweepcal = os.path.join(calib_dir, "wavvolt16_sweepcal.mat") #For post-acquisition wavelength calibration
# delayvolt_file =os.path.join(calib_dir, "delayvolt16.mat")
# wavamp_file = os.path.join(calib_dir, 'wavamp_dev1b_delayvolt16P3_2025-12-10-22.h5' )
# wavamp_file2 = os.path.join(calib_dir, 'wavamp_dev1b_delayvolt16P3_2025-12-09-22-34-51.h5' )

wavvolt_HVCALIB = os.path.join(calib_dir, "wavvolt_HVCALIB_dev1b_15C_OE1076_2025-12-13_delayvolt17.mat") #For post-acquisition wavelength calibration
wavvolt_file = wavvolt_HVCALIB #For wavelength set
wavvolt_sweepcal = wavvolt_file
# wavvolt_sweepcal = os.path.join(calib_dir, "wavvolt17_sweepcal.mat") #For post-acquisition wavelength calibration
delayvolt_file =os.path.join(calib_dir, "delayvolt17D.mat")
wavamp_file = os.path.join(calib_dir, 'wavamp_dev1b_delayvolt16P3_2025-12-10-22.h5' )

# wavamp_file = os.path.join(calib_dir, 'wavamp_dev1b_delayvolt17D_2025-12-.h5' )


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


""" Laser Spot Analysis """

def spotzoom_inds(ds, Dxy=10 * u.um):
    """
    Crops widefield laser spot image to size Dxy and returns min and max indices of zoomed in x and y axis
    x_img, y_img: indicies of widefield image cropped to galvo scan area
    """
    ix0, iy0 = [np.nanargmin(np.abs(xx)) for xx in
                [ds["x_img"], ds["y_img"]]]  # Find indices of min x and min y values (at center)
    npix_half = np.round((Dxy / 2. / ds["dx_dpix"]).m_as(u.dimensionless))  # Find (number of pixels)/2 making up Dxy
    ix_min, ix_max = int((ix0 - npix_half)), int(
        (ix0 + npix_half))  # Shift min and max pixel indices to boundary set by Dxy
    iy_min, iy_max = int((iy0 - npix_half)), int((iy0 + npix_half))
    return ix_min, ix_max, iy_min, iy_max


def gaussian(x, w, x0, A):
    return A * np.exp(-2 * (x - x0) ** 2 / w ** 2)


def plot_spotzoom(ds, Dxy=10 * u.um, figsize=(4.5, 4.5), laser_cmap=cm.winter,
                  x_wtext=-3, y_wtext=-3, rc_params=srs_rc_params):
    laser_cmap = transparent_cmap(laser_cmap)
    ix_min_sz, ix_max_sz, iy_min_sz, iy_max_sz = spotzoom_inds(ds, Dxy=Dxy)
    ix0 = int(np.round((ix_min_sz + ix_max_sz) / 2.)) - ix_min_sz  # Center around 0
    iy0 = int(np.round((iy_min_sz + iy_max_sz) / 2.)) - iy_min_sz  # Center around 0
    X = ds["x_img"][ix_min_sz:ix_max_sz]  # Cropped x axis
    Y = ds["y_img"][iy_min_sz:iy_max_sz]  # Cropped y axis
    Z_bg = ds["laser_spot_img"].min()  # Intensity background
    Z = ds["laser_spot_img"][ix_min_sz:ix_max_sz,
        iy_min_sz:iy_max_sz] - Z_bg  # Subtract off intensity background of cropped laser spot image
    Z_xcut = (1.0 * Z[:, iy0]) / Z.max()  # X-slice of laser_spot_image normalized to laser spot intensity
    Z_ycut = (1.0 * Z[ix0, :]) / Z.max()  # Y-slice of laser_spot_image normalized to laser spot intensity
    p_x, pcov_x = curve_fit(gaussian, X.m_as(u.um), Z_xcut, [1.0, 0.0, 1.0])
    p_y, pcov_y = curve_fit(gaussian, Y.m_as(u.um), Z_ycut, [1.0, 0.0, 1.0])
    wx, x0_fit, I0x = p_x
    wy, y0_fit, I0y = p_y
    x_fit = np.linspace(X.m_as(u.um).min(), X.m_as(u.um).max(), 100)
    y_fit = np.linspace(Y.m_as(u.um).min(), Y.m_as(u.um).max(), 100)
    Z_xcut_fit = gaussian(x_fit, wx, x0_fit, I0x)
    Z_ycut_fit = gaussian(y_fit, wy, y0_fit, I0y)
    fwhm = np.max(wx, wy) * np.sqrt(2 * np.log(2))
    with mpl.rc_context(rc_params):
        fig, ax = plt.subplots(2, 2,
                               figsize=figsize,
                               sharex="col",
                               sharey="row",
                               gridspec_kw={"wspace": 0, "hspace": 0, "width_ratios": [1, 0.2],
                                            "height_ratios": [0.2, 1]},
                               )
        p0 = ax[1, 0].pcolormesh(X, Y, np.fliplr(Z.T), cmap=laser_cmap)
        ax[1, 0].set_aspect("equal")
        ly_fit = ax[1, 1].plot(Z_ycut_fit, y_fit, 'k--')
        lx_fit = ax[0, 0].plot(x_fit, Z_xcut_fit, 'k--')
        sy = ax[1, 1].scatter(Z_ycut, Y)
        sx = ax[0, 0].scatter(X, Z_xcut)
        ax[1, 0].set_xlabel("x (μm)")
        ax[1, 0].set_ylabel("y (μm)")
        ax[1, 0].text(x_wtext, y_wtext, f"x waist: {wx:2.2f} μm" + "\n" + f"y waist: {wy:2.2f} μm")
        ax[1, 0].set_title("FWHM: %2.2f μm" % fwhm)
    return fig, ax

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
        ax[1,0].text(x_wtext, y_wtext, f"x waist: {wx:2.2f} μm" + "\n" + f"y waist: {wy:2.2f} μm")
        ax[0, 0].set_title("FWHM: %2.2f μm" % fwhm)
    return fig, ax


def plot_knife_scan(ds_spot, figsize=(4.5,4.5),rc_params=srs_rc_params):
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
    print("σ = %2.2fμm" %sigma)

    with mpl.rc_context(rc_params):
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
    return np.unravel_index(np.argmax(img), img.shape)


def img_spatial_axes(laser_spot_img, dx_dpix=dx_dpix):
    """
    Return x axis and y axis (in microns) of laser spot widefield image, centered around laser spot
    :param laser_spot_img: [2d array]
    :param dx_dpix: pixel to position conversion
    :return: x_img, y_img [1d arrays]
    """
    x_pix_laser, y_pix_laser = img_max_pixel_inds(laser_spot_img)  # Find indices of laser spot
    npix_x, npix_y = laser_spot_img.shape  # Dimensions of laser spot image
    x_img, y_img = dx_dpix * (np.arange(npix_x) - x_pix_laser), dx_dpix * (np.arange(
        npix_y) - y_pix_laser)  # Convert pixel to microns and shift image center to laser spot position
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

    x_img, y_img = img_spatial_axes(laser_spot_img)  # find indices of laser spot

    i_xmax = np.nanargmin(np.abs(x_img - x.max()))
    i_xmin = np.nanargmin(np.abs(x_img - x.min()))
    i_ymax = np.nanargmin(np.abs(y_img - y.max()))
    i_ymin = np.nanargmin(np.abs(y_img - y.min()))
    return i_xmax, i_xmin, i_ymax, i_ymin

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

def HVA_to_daq(HVA_volt, atten=0.09125, volt_limit=88.6*u.V, offset=0.15*u.V):
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

"""Processing Scan"""
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


""" Plotting """
def transparent_cmap(cmap):
    """
    Generate colormap `cmap_tr` with graded transparency (transparent at 0, opaque
    at maximum) from input colormap `cmap` for 2D heatmap overlays
    """
    cmap_tr = cmap(np.arange(cmap.N))
    cmap_tr[:, -1] = np.linspace(0, 1, cmap.N)
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


def plot_widefield_img(img, wf_cmap=cm.binary):
    """
    Plot widefield image without scan data or laser
    :param img: from wf_image())
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes_nolaser(img)
    fig, ax = plt.subplots()
    im0 = ax.pcolormesh(y_img, x_img, img[::-1, :], cmap=wf_cmap)
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
    im0 = ax.pcolormesh(y_img, x_img, wf_img[::-1, :], cmap=wf_cmap)
    im1 = ax.pcolormesh(y_img, x_img, laser_spot_img[::-1, :], cmap=laser_cmap)
    cb1 = plt.colorbar(im1, ax=ax)
    ax.set_aspect("equal")
    plt.show
    return fig


def plot_laser_widefield_img_zoom(wf_img, laser_spot_img, Vx, Vy, wf_cmap=cm.binary, laser_cmap=cm.Reds):
    """
    Plot widefield image with laser spot (no scan data) cropped to scan area, axis centered around laser spot
    :param laser_spot_img: from laser_spot_images(); Vx, Vy: from scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
    :return: fig with (1) subplot
    """
    x_img, y_img = img_spatial_axes(laser_spot_img)
    i_xmax, i_xmin, i_ymax, i_ymin = scan_volt_to_wf_inds(Vx, Vy, laser_spot_img)

    fig, ax = plt.subplots()
    im0 = ax.pcolormesh(y_img[i_ymin:i_ymax], x_img[i_xmin:i_xmax],
                        np.flipud(wf_img[i_xmin:i_xmax, i_ymin:i_ymax]), cmap=wf_cmap)
    im1 = ax.pcolormesh(y_img[i_ymin:i_ymax], x_img[i_xmin:i_xmax],
                        np.flipud(laser_spot_img[i_xmin:i_xmax, i_ymin:i_ymax]), cmap=transparent_cmap(laser_cmap))

    cb1 = plt.colorbar(im1, ax=ax)
    ax.set_aspect("equal")
    plt.show()
    return fig

"""Plot hyperspectral scan"""
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
    return fig, ax


def plot_daqsweep_wavmon(ds, ds_type='sweep', id_sweep_dir=False, colors=['b','g'], ax=None, fig=None, figsize=(6,4)):
    """
    ds_type: 'sweep': single point daq sweeps, 'hs_im': hyperspectral image
    """
    #Load FFP peaks from calibration file
    fpath = os.path.join(calib_dir,'FFP-I_peaks')
    FFP_cal_pks = load_hdf5(fpath=fpath)
    cal_pks = FFP_cal_pks["peaks"]
    
    
    #restrict FFP_cal_pks to tuning range
    FFP_cal = cal_pks[(cal_pks >= np.nanmin(ds['wavelength_set'])) & (cal_pks <= np.nanmax(ds['wavelength_set']))] 
    FFP_cal = FFP_cal[~((FFP_cal > ds['wavelength_set'][0]) & (FFP_cal < ds['wavelength_set'][-1]))]

    if ds_type == 'sweep':
        wavset_sort, s_ind = np.unique(ds["wavelength_set"].to(u.nm).m, return_index=True)
        wavset_sort = wavset_sort * u.nm
        wavmon_arr = ds["VCSEL_wavmon_arr"][:, s_ind]
    elif ds_type == 'hs_image':
        wavset_sort = ds["wavset_sort"]
        wavmon_arr = ds["VCSEL_wavmon_pix"]
    else:
        raise ValueError("Specify ds_type='hs_image' or 'sweep'")
    #Plotting
    even_color = colors[0]
    odd_color = even_color
    if id_sweep_dir:
        odd_color=colors[1]
    
    if ax is None:
        fig, ax = plt.subplots(1,1, figsize=figsize, tight_layout=True)
        
    # for row in range(4):
    #     if row %2 != 0:
    #         ax.plot(wavset_sort, ds["VCSEL_wavmon_arr"][row][s_ind], '.-', color=odd_color)
    #     else:
    #         ax.plot(wavset_sort, ds["VCSEL_wavmon_arr"][row][s_ind], '.-', color=even_color)
    for row in range(4):
        if row %2 != 0:
            ax.plot(wavset_sort, wavmon_arr[row], '.-', color=odd_color)
        else:
            ax.plot(wavset_sort, wavmon_arr[row], '.-', color=even_color)
    #ax.set_xlim((0,1))

    for wn in FFP_cal.m:
        plt.axvline(wn, color='k', linestyle='--')
    return fig, ax


def plot_daq_sweepSpectra(ds0, savefig=False, fname=None, fpath=None, figsize=(5,6), wavvolt_HVCALIB=wavvolt_HVCALIB, verbose=True, fig=None, ax=None, disc_tol=5, label=None):
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

    if ax is None:
        if verbose:
            fig, ax = plt.subplots(3, 1, figsize=figsize, tight_layout=True)
        else:
            fig, ax = plt.subplots(1, 1, figsize=figsize, tight_layout=True)
    
    if verbose:
        for spec in range(Vsrs_arr.shape[0]):
            ax[0].plot(raman_shift, Vsrs_arr[spec].to(u.uV))
            ax[1].plot(rs_sort, Vsrs_interp_arr[spec].to(u.uV))
        
        ax[2].plot(rs_sort, Vsrs_av.to(u.uV))
        ax[2].plot(rs_sort[mind].m, Vsrs_av[mind].to(u.uV).m, 'x', label=label)
        # ax[2].plot(raman_shift, np.mean(Vsrs_arr, axis=0).to(u.uV), 'k')
        ax[0].set_ylabel("Voltage $(\mu V)$")
        ax[0].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
        ax[1].set_ylabel("Voltage $(\mu V)$")
        ax[1].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
        ax[2].set_xlabel("Raman Shift (1/cm)")
        ax[2].set_ylabel("Voltage $(\mu V)$")
        ax[2].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
    else:
        ax.plot(rs_sort, Vsrs_av.to(u.uV), label=label)
        ax.set_xlabel("Raman Shift (1/cm)")
        ax.set_ylabel("Voltage $(\mu V)$")
        ax.set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))
    
    if savefig:
        fname=os.path.normpath(os.path.join(fpath,fname))
        plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
            orientation='portrait', transparent=True, bbox_inches=None, pad_inches=0.5)
    return fig, ax


def calibrate_sweepSpectra(wavelength_set, Vsrs_arr, HV_arr, HVA_Vset, wavvolt_HVCALIB=wavvolt_HVCALIB, disc_tol=5):
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
        if np.max(np.diff(wav_calib_sort[sweep_iter,:])) > dwav.to(u.nm).m*disc_tol:
            bad_ind = np.where(np.diff(wav_calib_sort[sweep_iter,:]) > dwav.to(u.nm).m*disc_tol)# | np.diff(wav_calib_sort[sweep_iter,:]) == 0)
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


"""Calibration Curves"""

def find_peak_delay(ds0, sgolay_winlen, sgolay_polyord):
    """
    For generating wavamp_file
    """
    smoothed = np.zeros(ds0['trace_aray'].shape)
    pks_val = []
    pks_loc = []

    #shift to center at first peak
    pk0_i = np.argmax(ds0['trace_aray'][0,:])
    time = ds0['x_axis'] - ds0['x_axis'][pk0_i]
    for ind in range(ds0['trace_aray'].shape[0]):
        smoothed[ind, :] = savgol_filter(ds0['trace_aray'][ind,:], window_length=sgolay_winlen, polyorder=sgolay_polyord)
        Mind = np.argmax(smoothed[ind,:])
        pks_val.append(smoothed[ind, Mind])
        pks_loc.append(time[Mind].m) 
    pks_loc = np.array(pks_loc)*u.s
    pks_norm = pks_val/ np.max(pks_val)
    fig,ax0 = plt.subplots(1,1, figsize=(6,4), tight_layout=True)
    ax0.plot(time.to(u.ps), smoothed.T)
    ax0.scatter(pks_loc.to(u.ps), pks_val, marker='x', color='r')
    ax0.set_xlabel("Time [ps]")
    ax0.set_ylabel("Voltage [V]")
    
    return pks_val, pks_loc, pks_norm


def save_wavvolt(ds, volt_stop=None, f_interp=5000, name=None,sample_dir=None, cmap=cm.magma, smooth_param=None):
    """
    Interpolates voltage vs peak wavelength curve, saves wavvolt file with variables:
    -ds: dataset from generate_wavvolt()
    -volt_interp: interpolated (measured) voltage
    -wav_interp: interpolated wavelength
    """
    volt = ds["meas_volt_list"].to(u.V).m
    peak_wl = ds["pk_wl_list"].to(u.m).m
    spectrum_array = ds["spectrum_array"].m
    wavelength = ds["wavelength"].m

    volt_interp = np.linspace(volt[0], volt[-1], f_interp) * u.V
    peak_interp = np.interp(volt_interp.m, volt, peak_wl) * u.m

    if volt_stop is not None:
        peak_interp = peak_interp[volt_interp < volt_stop]
        volt_interp = volt_interp[volt_interp < volt_stop]
      
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
    ax[0].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))

    ax[1].plot(raman_shift.m, spec.m)
    ax[1].set_xlabel("Raman Shift [1/cm]")
    ax[1].set_ylabel("Voltage [V]")
    ax[1].set_xlim((np.min(raman_shift.m), np.max(raman_shift.m)))

    ax[2].plot(wavelengths.m, spec.m)
    ax[2].set_xlabel("Wavelengths [nm]")
    ax[2].set_ylabel("Voltage [V]")
    ax[2].set_xlim((np.min(wavelengths.m), np.max(wavelengths.m)))
    return fig


""" Saving Images """

def save_single_img(X, Y, Z, cmap, fname, fpath=False, xlabel="x (μm)", ylabel="y (μm)", cbar=False, cbar_label=None,
                    figsize=(4, 6), format='png', rc_params=srs_rc_params, **kwargs):
    """
    Given X,Y,Z arrays, plot and save figure
    """
    with mpl.rc_context(rc_params):
        fig, ax = plt.subplots(1, 1)  # ,figsize=figsize) #**kwargs)
        ps = [ax.pcolormesh(X, Y, zz, cmap=ccmm, vmin=0, vmax=np.nanmax(zz)) for (zz, ccmm) in zip(Z, cmap)]
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if cbar:
            cb = plt.colorbar(ps[-1], ax=ax, label=cbar_label)
        ax.set_aspect("equal")
        # fig.tight_layout()
        if fpath:
            fname = os.path.normpath(os.path.join(fpath, fname))
        plt.savefig(fname, dpi=None, facecolor=None, edgecolor=None,
                    orientation='portrait', papertype=None, format=format,
                    transparent=True, bbox_inches=None, pad_inches=0.5)
    return fig


def save_scan_images(ds, fname, fpath=False, wf_cmap=cm.binary_r, laser_cmap=cm.winter, srs_cmap=cm.inferno,
                     rc_params=srs_rc_params, format='png', **kwargs):
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
        (
        ds["y_img"].m, ds["x_img"].m, (np.flipud(ds["wf_img"]), np.flipud(ds["laser_spot_img"])), (wf_cmap, laser_cmap),
        "wfls_" + fname + "." + format),
        #         (ds["y_img"][i_ymin:i_ymax].m, ds["x_img"][i_xmin:i_xmax].m, (np.flipud(ds["wf_img"][i_xmin:i_xmax,i_ymin:i_ymax]), ), (wf_cmap,), "wfzoom_"+fname+"."+format),
        (ds["y_img"][i_ymin:i_ymax].m, ds["x_img"][i_xmin:i_xmax].m, (
        np.flipud(ds["wf_img"][i_xmin:i_xmax, i_ymin:i_ymax]),
        np.flipud(ds["laser_spot_img"][i_xmin:i_xmax, i_ymin:i_ymax])), (wf_cmap, laser_cmap),
         "wflszoom_" + fname + "." + format),
        (ds["y"].m, ds["x"].m, (np.flipud(np.transpose(ds["Vsrs_g"].m)),), (srs_cmap,), "srs_" + fname + "." + format),
    ]
    for X, Y, Z, cmap, fname in img_data:
        save_single_img(X, Y, Z, cmap, fname, fpath=fpath, xlabel="x (μm)", ylabel="y (μm)", cbar=False,
                        cbar_label=None, rc_params=rc_params, format=format, **kwargs)
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
            data = {'t_lia': ds_spec['t_lia'].to(u.s).m,
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

""" Importing hdf5 """

def load_data_from_file(sample_dir, filename):
    """
    Load saved hd5f file and return ds
    """
    file_dir = os.path.join(data_dir, sample_dir, filename)
    ds = load_hdf5(fpath=file_dir)
    return ds
