import os
import time
import numpy as np
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.interpolate import griddata
from scipy.optimize import curve_fit
from scipy.stats import norm
from scipy import io

from ..util.units import Q_, u
from ..util.io import *         # hdf5 utilites

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
        sx = ax[0, 0].scatter(X, Z_xcut, )
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


def plot_scan_data(ds, wf_cmap=cm.binary, laser_cmap=cm.Reds):
    """
    Plot 2x1 subplots with [0] laser spot superimposed on cropped widefield image, and [1] SRS image
    :param ds: from collect_scan()
    :return: fig with (2) subplots
    """
    laser_cmap = transparent_cmap(laser_cmap)
    fig, ax = plt.subplots(2, 1, figsize=(10, 10))

    # [0] Laser spot + cropped widefield image
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    im0 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                           ds["wf_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=wf_cmap)
    im1 = ax[0].pcolormesh(ds["y_img"][i_ymin:i_ymax], ds["x_img"][i_xmin:i_xmax],
                           ds["laser_spot_img"][i_xmax:i_xmin:-1, i_ymin:i_ymax], cmap=laser_cmap)
    cb0 = plt.colorbar(im1, ax=ax[0])
    ax[0].set_aspect("equal")

    # [1] SRS (galvo) image
    p0 = ax[1].pcolormesh(ds["y"].m, ds["x"].m, np.flipud(np.transpose(ds["Vsrs_g"].m)))
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
    (3) Laser spot superimposed on cropped widefield image
    (4) SRS image
    """
    i_xmax, i_xmin, i_ymax, i_ymin = wf_img_inds(ds)
    laser_cmap = transparent_cmap(laser_cmap)
    img_data = [
        (
        ds["x_img"].m, ds["y_img"].m, (np.fliplr(ds["wf_img"].transpose()),), (wf_cmap,), "wf_" + fname + "." + format),
        (ds["x_img"].m, ds["y_img"].m,
         (np.fliplr(ds["wf_img"].transpose()), np.fliplr(ds["laser_spot_img"].transpose())), (wf_cmap, laser_cmap),
         "wfls_" + fname + "." + format),
        (ds["x_img"][i_xmin:i_xmax].m, ds["y_img"][i_ymin:i_ymax].m,
         (np.fliplr(ds["wf_img"][i_xmin:i_xmax, i_ymin:i_ymax].transpose()),), (wf_cmap,),
         "wfzoom_" + fname + "." + format),
        (ds["x_img"][i_xmin:i_xmax].m, ds["y_img"][i_ymin:i_ymax].m, (
        np.fliplr(ds["wf_img"][i_xmin:i_xmax, i_ymin:i_ymax].transpose()),
        np.fliplr(ds["laser_spot_img"][i_xmin:i_xmax, i_ymin:i_ymax].transpose()),), (wf_cmap, laser_cmap),
         "wflszoom_" + fname + "." + format),
        (ds["x"].m, ds["y"].m, (np.flip(ds["Vsrs_g"].m, (0, 1)),), (srs_cmap,), "srs_" + fname + "." + format),
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
