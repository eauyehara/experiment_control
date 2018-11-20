import numpy as np
from instrumental import instrument, Q_, u
from glob import glob
from os import path
import os, sys
import pickle
import matplotlib.pyplot as plt
import  matplotlib.cm as cm
from matplotlib.colors import Normalize
from datetime import datetime
from time import sleep
from pathlib import Path


# parameters that might need to be updated for my libraries to work
lia_address = 'ASRL9::INSTR'
scope_address = 'USB0::0x0699::0x0374::C010960::INSTR'
default_data_dir = 'C:/Users/Lab/Google Drive/data/'
github_dir = "C:/Users/Lab/Lab Software/GitHub/experiment_control"
# temp_mon_dir = "C:/Users/Lab/Lab Software/GitHub/experiment_control/temp_monitor"
DAQ_server='171.64.84.21' # DAQ-server IP address
DAQ_name = 'PCI-6713' # daq's instrumental saved instrument name on DAQ-server


# import my libraries
if github_dir not in sys.path:
    sys.path.append(github_dir)
# if temp_mon_dir not in sys.path:
#     sys.path.append(temp_mon_dir)

from xantrex import xhr_write # control function for Xantrex XHR 300V supply via LabJack
import ipg_sftl_lib as ipg
from experiment_utilities import print_statusline
from sample_mount_temp_control import set_temp_and_wait, get_meas_temp
from plotting_imports import plt

# initialize IPG SFTL
ipg.init()

# connect to scope
scope = instrument(module='scopes.tektronix', classname='MSO_DPO_4000', visa_address=scope_address)

# connect ot NI DAQ for analog outputs on remote DAQ-server
daq = instrument(DAQ_name,server=DAQ_server)

# connect to tektronix AFG
afg_visa_address = 'USB0::0x0699::0x0343::C022130::INSTR'
afg = instrument({'visa_address':afg_visa_address,'module':'funcgenerators.tektronix'})


### connect to SR850 Lock-in Amplifier
from instrumental.drivers.lockins import sr850 # import driver for Enum constants
lia = instrument(module='lockins.sr850',classname='SR850',visa_address=lia_address)
## configure LIA
lia.clear_registers()
# configure reference frequency
lia.set_reference_source(sr850.ReferenceSource.external) # use chopper reference out as lock-in reference signal
lia.set_reference_slope(sr850.ReferenceSlope.ttl_rising)
# configure inputs
lia.set_input_coupling(sr850.InputCoupling.AC)
lia.set_input_ground(sr850.InputGround.floating)
lia.set_input_configuration(sr850.InputConfiguration.I)
# lia.set_current_gain(sr850.CurrentGain.oneMegaOhm)
# lia.set_line_filter_status(sr850.LineFilter.line_notch)
# # configure gain, time constant, sensitivity
# lia.set_sensitivity(sr850.Sensitivity.x5uV_pA)
# lia.set_time_constant(sr850.TimeConstant.x1s)


def set_Vrb(V,V_max=8.6*u.volt):
    if ((V>=(0*u.volt)) and (V<=V_max)):
        daq.ao3.write(V)
    else:
        print(f'Warning: invalid Vrb set voltage: {V.m:3.3f} V')

def set_V_ring(V,V_max=10.1*u.volt):
    if ((V>=(0*u.volt)) and (V<=V_max)):
        daq.ao1.write(V)
    else:
        print(f'Warning: invalid V_ring set voltage: {V.m:3.3f} V')


def P_24_measurements(set_up_measurements=True,wait=False,wait_time=2*u.second,
                    P_24_trans_ch=1,P_24_ref_ch=3,P_24_trans_meas_num=1,
                    P_24_ref_meas_num=2):
    if set_up_measurements:
        scope.set_measurement_params(P_24_trans_meas_num,'amplitude',P_24_trans_ch)
        sleep(0.3)
        scope.set_measurement_params(P_24_ref_meas_num,'amplitude',P_24_ref_ch)
        sleep(0.3)
    if wait:
        sleep(wait_time.to(u.second).m)
    V_P_24_trans = scope.read_measurement_value(P_24_trans_meas_num)
    sleep(0.1)
    V_P_24_ref = scope.read_measurement_value(P_24_ref_meas_num)
    sleep(0.1)
    return V_P_24_trans,V_P_24_ref

def collect_shg_wavelength_sweep(lm_set,name='',data_dir=default_data_dir,n_pts_per_setpoint=1,
    time_constant=sr850.TimeConstant.x3s,settle_time=10*u.second,autogain=True,color='C3',
    P_24_trans_ch=1,P_24_ref_ch=3,return_fpath=True,live_plot=True,fig=None,ax=None):
    lia.set_time_constant(time_constant)
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'SHG_wavelength_sweep_' + name + '_' + timestamp_str+'.npz'
    fpath = path.normpath(path.join(data_dir,fname))
    print('saving to '+fpath)
    V_R = np.zeros((len(lm_set),n_pts_per_setpoint))*u.volt
    theta = np.zeros((len(lm_set),n_pts_per_setpoint))*u.degree
    lm_meas = np.zeros((len(lm_set),n_pts_per_setpoint))*u.nm
    V_P_24_trans = np.zeros((len(lm_set),n_pts_per_setpoint))*u.volt
    V_P_24_ref = np.zeros((len(lm_set),n_pts_per_setpoint))*u.volt
    V_P_24_data_init = P_24_measurements(set_up_measurements=True,
                                         wait=True,
                                         P_24_trans_ch=P_24_trans_ch,
                                         P_24_ref_ch=P_24_ref_ch)

    if live_plot:
        #xlimits = [lm_set.to(u.nm).min().m-2., lm_set.to(u.nm).max().m+2.]
        if not ax:
            fig,ax=plt.subplots(1,1,figsize=(12,8))
        ax.set_xlabel('Wavelength [nm]')
        ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
        #ax.set_xlim(xlimits)
        plt.subplots_adjust(right=0.7,bottom=0.3)

    for lind, ll in enumerate(lm_set):
        ipg.set_wavelength(ll,tune_SHG=False)
        if autogain:
            lia.auto_gain()
        for nn in range(n_pts_per_setpoint):
            lm_meas[lind,nn] = ipg.get_lm()
            sleep(settle_time.to(u.second).m)
            V_P_24_data = P_24_measurements(set_up_measurements=False,P_24_trans_ch=P_24_trans_ch,P_24_ref_ch=P_24_ref_ch)
            V_P_24_trans[lind,nn] = V_P_24_data[0]
            V_P_24_ref[lind,nn] = V_P_24_data[1]
            V_R[lind,nn] = lia.read_output(sr850.OutputType.R)
            theta[lind,nn] = lia.read_output(sr850.OutputType.theta)
            np.savez(Path(fpath),lm_set=lm_set.m,
                                    lm_meas=lm_meas.m,
                                    V_R=V_R.m,
                                    theta=theta.m,
                                    V_P_24_trans=V_P_24_trans.m,
                                    V_P_24_ref=V_P_24_ref.m)
            if live_plot:
                ax.plot(lm_meas[lind,nn],V_R[lind,nn]/V_P_24_trans[lind,nn]**2,'o',color=color)
                fig.canvas.draw()
    plt.subplots_adjust(right=0.9,bottom=0.1)
    if return_fpath:
        return fpath,fig,ax
    else:
        return fig,ax


def collect_shg_open_loop_wavelength_sweep(lm_start,steps_per_point,n_pts,
    name='',data_dir=default_data_dir,n_pts_per_setpoint=1,norm_with_P_trans=True,
    settle_time=10*u.second,autogain=True,color='C3',short_name=False,n_line=0,
    P_24_trans_ch=1,P_24_ref_ch=3,return_fpath=True,live_plot=True,fig=None,ax=None):
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    if short_name:
        fname = name+'.npz'
    else:
        fname = 'SHG_wavelength_sweep_' + name + '_' + timestamp_str+'.npz'
    fpath = path.normpath(path.join(data_dir,fname))
    #print('saving to '+fpath)
    V_R = np.zeros((n_pts,n_pts_per_setpoint))*u.volt
    theta = np.zeros((n_pts,n_pts_per_setpoint))*u.degree
    lm_meas = np.zeros((n_pts,n_pts_per_setpoint))*u.nm
    V_P_24_trans = np.zeros((n_pts,n_pts_per_setpoint))*u.volt
    V_P_24_ref = np.zeros((n_pts,n_pts_per_setpoint))*u.volt
    # V_P_24_data_init = P_24_measurements(set_up_measurements=True,
    #                                      wait=True,
    #                                      P_24_trans_ch=P_24_trans_ch,
    #                                      P_24_ref_ch=P_24_ref_ch)

    if live_plot:
        #xlimits = [lm_set.to(u.nm).min().m-2., lm_set.to(u.nm).max().m+2.]
        if not ax:
            fig,ax=plt.subplots(1,1,figsize=(11,6))
            ax.set_xlabel('Wavelength [nm]')
            ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
            #ax.set_xlim(xlimits)
            plt.subplots_adjust(right=0.7,bottom=0.3)

    ipg.set_wavelength(lm_start,tune_SHG=False)
    sm = ipg.sm
    for lind in range(n_pts):
        curr_pos_steps = sm.get_current_position(unitful=False)
        relative_move = steps_per_point
        target_pos_steps = curr_pos_steps + relative_move
        if not(sm.limit_switch_1_pos<target_pos_steps<sm.limit_switch_2_pos):
            print('Warning: bad target_pos_steps: {:2.1g}, lm_meas:{:7.3f}\n'.format(target_pos_steps,float(lm_meas.magnitude)))
            target_pos_steps = 0
        sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)

        # if autogain:
            # lia.auto_gain()
        for nn in range(n_pts_per_setpoint):
            sleep(settle_time.to(u.second).m)
            pct_complete = 100. * float(lind*n_pts_per_setpoint+nn) / float(n_pts_per_setpoint*n_pts)
            print_statusline(f'step {lind+1} of {n_pts}, point {nn+1} of {n_pts_per_setpoint}, {pct_complete:3.2f}% complete')
            lm_meas[lind,nn] = ipg.get_lm()
            if norm_with_P_trans:
                V_P_24_data = P_24_measurements(set_up_measurements=False,P_24_trans_ch=P_24_trans_ch,P_24_ref_ch=P_24_ref_ch)
                V_P_24_trans[lind,nn] = V_P_24_data[0]
                V_P_24_ref[lind,nn] = V_P_24_data[1]
            V_R[lind,nn] = lia.read_output(sr850.OutputType.X) # changed to X now that I figured out the right phase (currently 10.7 degree). keeping 'V_R' name for backwards compatibility
            #theta[lind,nn] = lia.read_output(sr850.OutputType.theta) # no need for theta any more, just save zeros also for  backwards compatibility
            if norm_with_P_trans:
                np.savez(Path(fpath),
                            lm_meas=lm_meas.m,
                            V_R=V_R.m,
                            theta=theta.m,
                            V_P_24_trans=V_P_24_trans.m,
                            V_P_24_ref=V_P_24_ref.m)
            else:
                np.savez(Path(fpath),
                            lm_meas=lm_meas.m,
                            V_R=V_R.m,
                            theta=theta.m)
            if live_plot:
                x = lm_meas[np.nonzero(V_R)]
                if norm_with_P_trans:
                    V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
                    y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
                else:
                    # V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
                    # y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
                    y = V_R[np.nonzero(V_R)]
                if not(( nn==0 ) and ( lind==0 ) ):
                    line = ax.lines[n_line]
                    line.set_xdata(x)
                    line.set_ydata(y)
                    ax.relim()
                    ax.autoscale_view(True,True,True)
                    # y_lim = ax.get_ylim()
                    # ax.set_ylim([min(4e-14,ax.get_ylim()[1]])
                else:
                    ax.semilogy(x,y,'.',color=color)
                fig.canvas.draw()
    plt.subplots_adjust(right=0.9,bottom=0.1)
    if return_fpath:
        return fpath,fig,ax
    else:
        return fig,ax



def load_shg_wavelength_sweep(name='',data_dir=default_data_dir,verbose=False,
                     fpath=None,metadata=False,exact_name=False):
    if fpath:
        if verbose:
            print_statusline('Loading data from file: ' + path.basename(path.normpath(fpath)))
        data_npz = np.load(Path(fpath))
    else:
        file_list =  glob(path.normpath(data_dir)+path.normpath('/'+ 'SHG_wavelength_sweep_' + name + '*'))
        latest_file = max(file_list,key=path.getctime)
        if verbose:
            print_statusline('Loading ' + name +' data from file: ' + path.basename(path.normpath(latest_file)))
        data_npz = np.load(latest_file)
    lm_meas = data_npz['lm_meas'] * u.nm
    V_R = data_npz['V_R'] * u.volt
    theta = data_npz['theta'] * u.degree
    try:
        V_P_24_trans = data_npz['V_P_24_trans'] * u.volt
        V_P_24_ref = data_npz['V_P_24_ref'] * u.volt
        ds = {'lm_meas':lm_meas,
                'V_P_24_trans':V_P_24_trans,
                'V_P_24_ref':V_P_24_ref,
                'V_R':V_R,
                'theta':theta}
    except:
        ds = {'lm_meas':lm_meas,
                'V_R':V_R,
                'theta':theta}
    return ds

def plot_shg_wavelength_sweep(ds,ax=None,color='C1'):
    if not ax:
        fig,ax = plt.subplots(1,1,figsize=(12,8))
    ax.plot(ds['lm_meas'],ds['V_R']/ds['V_P_24_trans']**2,'o',color=color)
    xlimits = [ds['lm_set'].to(u.nm).min().m-2., ds['lm_set'].to(u.nm).max().m+2.]
    ax.set_xlabel('Wavelength [nm]')
    ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
    ax.set_xlim(xlimits)
    return ax



def collect_SHG_V_wavelength_sweep(V,set_V_fn,lm_start,steps_per_point,n_pts,name='',autogain=False,data_dir=default_data_dir,
                                norm_with_P_trans=False,n_pts_per_setpoint=1,settle_time=0.2*u.second,
                                cmap=cm.viridis):
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    # create/enter sweep directory
    set_name = 'SHG_V_wavelength_sweep_' + name + '_' + timestamp_str
    set_dir = path.normpath(path.join(data_dir,set_name))
    if not os.path.exists(set_dir):
        os.makedirs(set_dir)
    sweep_data = {'V':V}
    sweep_fname = 'sweep_data_' + timestamp_str +'.dat'
    sweep_fpath = path.join(set_dir,sweep_fname)
    with open(sweep_fpath, 'wb') as f:
        pickle.dump(sweep_data,f)


    fig,ax = plt.subplots(1,1,figsize=(10,6))
    ax.set_xlabel('Wavelength [nm]')
    ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
    #ax.set_xlim(xlimits)
    plt.subplots_adjust(right=0.7,bottom=0.3)

    # colormap for plotting
    norm = Normalize(V.min().m,V.max().m)
    sm = cm.ScalarMappable(norm, cmap)
    sm.set_array([]) # You have to set a dummy-array for this to work...

    cbar = plt.colorbar(sm,ax=ax)
    cbar.set_label('Voltage [V]')

    for Vind,VV in enumerate(V):
        set_V_fn(VV)
        V_dir = path.normpath(path.join(set_dir,f'{VV.m:3.2f}V'))
        if not os.path.exists(V_dir):
            os.makedirs(V_dir)
        fpath,fig_in,ax_in = collect_shg_open_loop_wavelength_sweep(lm_start,
                                              steps_per_point,
                                              n_pts,
                                             name=f'{VV.m:3.2f}V',
                                             short_name=True,
                                             data_dir=V_dir,
                                             autogain=autogain,
                                             norm_with_P_trans=norm_with_P_trans,
                                             n_pts_per_setpoint=n_pts_per_setpoint,
                                             settle_time=settle_time,
                                             n_line=Vind,
                                             color=cmap(norm(VV.m)),
                                             fig=fig,
                                             ax=ax)


def load_SHG_V_wavelength_sweep(name='',data_dir=default_data_dir,verbose=False,set_dir=None,
                                metadata=False,exact_name=False):
    if set_dir:
        if verbose:
            print_statusline('Loading data from dir: ' + path.basename(path.normpath(set_dir)))
    else:
        file_list =  glob(path.normpath(data_dir)+path.normpath('/'+ 'SHG_V_wavelength_sweep_' + name + '*'))
        set_dir = path.normpath(max(file_list,key=path.getctime))
        if verbose:
            print_statusline('Loading data from dir: ' + path.basename(set_dir))
    sweep_file_list =  glob(path.normpath(set_dir)+path.normpath('/'+ 'sweep_data' + '*'))
    latest_sweep_file = path.normpath(max(sweep_file_list,key=path.getctime))
    with open(latest_sweep_file, "rb" ) as f:
        ds = pickle.load(f)
    for Vind,VV in enumerate(ds['V']):
        V_dir = path.normpath(path.join(set_dir,f'{VV.m:3.2f}V'))
        V_ds = load_shg_wavelength_sweep(fpath=path.join(V_dir,f'{VV.m:3.2f}V.npz'))
        if Vind==0:
            n_lm = V_ds['lm_meas'].shape[0]
            n_pts_per_setpoint = V_ds['lm_meas'].shape[1]
            lm_meas = np.zeros((n_lm,n_pts_per_setpoint,len(ds['V']))) * u.nm
            V_R = np.zeros((n_lm,n_pts_per_setpoint,len(ds['V']))) * u.volt
            theta = np.zeros((n_lm,n_pts_per_setpoint,len(ds['V']))) * u.degree
        lm_meas[:,:,Vind] = V_ds['lm_meas']
        V_R[:,:,Vind] = V_ds['V_R']
        theta[:,:,Vind] = V_ds['theta']
    ds['lm_meas'] = lm_meas
    ds['V_R'] = V_R
    ds['theta'] = theta
    return ds


def collect_shg_temperature_sweep(T_set,name='',data_dir=default_data_dir,
    settle_time=10*u.second,autogain=True,
    P_24_trans_ch=1,P_24_ref_ch=3,return_fpath=True,live_plot=True,
    n_T_samples=4,dt_T_sample=0.5*u.second,n_pts_per_setpoint=1):
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'SHG_temperature_sweep_' + name + '_' + timestamp_str+'.npz'
    fpath = path.normpath(path.join(data_dir,fname))
    print('saving to '+fpath)
    V_R = np.zeros((len(T_set),n_pts_per_setpoint))*u.volt
    theta = np.zeros((len(T_set),n_pts_per_setpoint))*u.degree
    lm_meas = np.zeros((len(T_set),n_pts_per_setpoint))*u.nm
    T_meas = np.zeros((len(T_set),n_pts_per_setpoint)) # Celsius is too annoying with pint
    V_P_24_trans = np.zeros((len(T_set),n_pts_per_setpoint))*u.volt
    V_P_24_ref = np.zeros((len(T_set),n_pts_per_setpoint))*u.volt
    V_P_24_data_init = P_24_measurements(set_up_measurements=True,
                                         wait=True,
                                         P_24_trans_ch=P_24_trans_ch,
                                         P_24_ref_ch=P_24_ref_ch)

    if live_plot:
        xlimits = [T_set.min()-1., T_set.max()+1.]
        fig,ax=plt.subplots(1,1)
        ax.set_xlabel('Temperature [C]')
        ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
        ax.set_xlim(xlimits)
        plt.show()

    for Tind,TT in enumerate(T_set):
        T_meas_temp = set_temp_and_wait(TT,
                                        n_samples=n_T_samples,
                                        dt_sample=dt_T_sample)
        if autogain:
            lia.auto_gain()
        for nn in range(n_pts_per_setpoint):
            lm_meas[Tind,nn] = ipg.get_lm()
            T_meas[Tind,nn] = get_meas_temp()
            sleep(settle_time.to(u.second).m)
            V_P_24_data = P_24_measurements(set_up_measurements=False,
                                            P_24_trans_ch=P_24_trans_ch,
                                            P_24_ref_ch=P_24_ref_ch)
            V_P_24_trans[Tind,nn] = V_P_24_data[0]
            V_P_24_ref[Tind,nn] = V_P_24_data[1]
            V_R[Tind,nn] = lia.read_output(sr850.OutputType.R)
            theta[Tind,nn] = lia.read_output(sr850.OutputType.theta)
            np.savez(Path(fpath),
                        T_set=T_set,
                        T_meas=T_meas,
                        lm_meas=lm_meas.m,
                        V_R=V_R.m,
                        theta=theta.m,
                        V_P_24_trans=V_P_24_trans.m,
                        V_P_24_ref=V_P_24_ref.m)
            if live_plot:
                ax.plot(T_meas[Tind,nn],V_R[Tind,nn]/V_P_24_trans[Tind,nn]**2,'C0')
                fig.canvas.draw()
                plt.show()
    if return_fpath:
        return fpath

def load_shg_temperature_sweep(name='',data_dir=default_data_dir,verbose=False,
                     fpath=None,metadata=False,exact_name=False):
    if fpath:
        if verbose:
            print_statusline('Loading data from file: ' + path.basename(path.normpath(fpath)))
        data_npz = np.load(Path(fpath))
    else:
        file_list =  glob(path.normpath(data_dir)+path.normpath('/'+ 'SHG_temperature_sweep_' + name + '*'))
        latest_file = max(file_list,key=path.getctime)
        if verbose:
            print_statusline('Loading ' + name +' data from file: ' + path.basename(path.normpath(latest_file)))
        data_npz = np.load(latest_file)
    T_set = Q_(data_npz['T_set'],u.degC)
    T_meas = Q_(data_npz['T_meas'],u.degC)
    lm_meas = data_npz['lm_meas'] * u.nm
    V_P_24_trans = data_npz['V_P_24_trans'] * u.volt
    V_P_24_ref = data_npz['V_P_24_ref'] * u.volt
    V_R = data_npz['V_R'] * u.volt
    theta = data_npz['theta'] * u.volt
    ds = {'T_set':T_set,
            'T_meas':T_meas,
            'lm_meas':lm_meas,
            'V_P_24_trans':V_P_24_trans,
            'V_P_24_ref':V_P_24_ref,
            'V_R':V_R,
            'theta':theta}
    return ds

def plot_shg_temperature_sweep(ds,ax=None,):
    if not ax:
        fig,ax = plt.subplots(1,1,figsize=(12,8))
    ax.plot(ds['T_meas'],ds['V_R']/ds['V_P_24_trans']**2,'o',color=color)
    xlimits = [ds['T_meas'].min().m-1., ds['T_meas'].max().m+1.]
    ax.set_xlabel('Temperature [C]')
    ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
    ax.set_xlim(xlimits)
    return ax
