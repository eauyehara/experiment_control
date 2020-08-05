"""
Module for software control of IPG SFTL-Cr-Sn/Se-2300-500-3000 using spectra
measured using Bristol 721 FTIR (scanning Michelson) optical spectrum analyzer
and the grating stepper-motor (USMC, Standa) and piezo stages (Thorlabs APT)
inside the laser.
"""

from instrumental import instrument, Q_, u
from instrumental.drivers.motion import USMC
from instrumental.drivers.spectrometers import bristol
from instrumental.drivers.tempcontrollers import covesion
from instrumental.drivers.spectrometers.bristol import ignore_stderr
from datetime import datetime
import numpy as np
from scipy.interpolate import interp1d
from os import path
from glob import glob
from sys import stdout
import threading
from time import sleep
import matplotlib.pyplot as plt
###############################################
#                 Parameters                  #

# Standa motor inside IPG 2um laser
motor_id = 0
travel_per_microstep = 156 * u.nm # from looking at motor model on Standa website
step_divisor=8 # reported by motor in uSMC test application. This worked previously
# Bristol 721
bristol_port = 4
bristol_params={'module':'spectrometers.bristol','classname':'Bristol_721','port':bristol_port}
# Covesion OC1 PPLN oven temperature controller
oc_visa_address = u'ASRL4::INSTR'

# Thorlabs PM100D power meter
pwrmtr_visa_address = u'USB0::0x1313::0x8078::P0005908::INSTR'

# IPG 2um SFTL tuning calibration save location
sm_calibration_save_dir = 'C:/Users/Lab/Lab Software/GitHub/experiment_control/calibration_data/sm_calibration'
grating_calibration_save_dir = 'C:/Users/Lab/Lab Software/GitHub/experiment_control/calibration_data/grating_calibration'
SHG_calibration_save_dir = 'C:/Users/Lab/Lab Software/GitHub/experiment_control/calibration_data/SHG_calibration'
spectra_save_dir = 'C:/Users/Lab/Lab Software/GitHub/experiment_control/calibration_data/spectra'
dlm_dstep = 0.1 * u.nm / 13 # change in wavelength per stepper motor step measured by yours truly near 2300nm

# import SHG tuning data provided by covesion and generate interpolation functions
covesion_SHG_data_fname = 'MSHG2600data_formatted.csv'
data_cov = np.genfromtxt(path.normpath(path.join(SHG_calibration_save_dir,covesion_SHG_data_fname)),delimiter=',',filling_values=np.nan,unpack=True)
temp_cov = Q_(data_cov[0,:],u.degC)
lm_cov = data_cov[1:,:] * u.nm
LM_cov = np.array([34,34.8,35.5,35.8,35.97]) * u.um # poling periods of MSHG2600-1.0-40 PPLN crystal

## import my own SHG calibration data
current_poling_region = 1 # should be fixed when we have a stage to move the PPLN crystal between poling regions.
###############################################



### Open instruments
#spec = instrument(**bristol_params) can't do this here or you get tons of error messages
sm = instrument(module='motion.USMC',classname='USMC',id=0,version=b'2504',serial=b'0000000000006302')
#oc = instrument('OC')
oc = instrument(module='tempcontrollers.covesion',classname='OC',visa_address='ASRL4::INSTR')
#pwrmtr = instrument({'visa_address':pwrmtr_visa_address,'module':'powermeters.thorlabs'})



### function definitions

print_statusline = covesion.print_statusline

## define a decorator function to allow me to keep the Bristol open throughout
## functions defined here rather than openning and closing it over and over
## again.


# def use_bristol(f):
#     @ignore_stderr
#     def wrapper(*args,**kwargs):
#         spec = instrument(**bristol_params)
#         return f(*args,**kwargs)
#         spec.close()
#     return wrapper

class bristol_temp:
    def __enter__(self):
        spec = instrument(**bristol_params)
        self.inst = spec
        return spec
    def __exit__(self,type,value,thing):
        self.inst.close()


def calibrate_stepper_motor():
    # grab encoder values of limit switch positions from standa stepper motor controller IPG SFTL grating
    ls1_pos, ls2_pos = sm.initialize_calibration()
    # save calibration data
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'IPG_SFTL_sm_calibration_' + timestamp_str + '.txt'
    np.savetxt(path.normpath(path.join(sm_calibration_save_dir,fname)),
                np.array([ls1_pos,ls2_pos]))

def load_newest_stepper_motor_calibration(verbose=False):
    file_list =  glob(path.normpath(sm_calibration_save_dir)+path.normpath('/IPG_SFTL_sm_calibration*'))
    latest_file = max(file_list,key=path.getctime)
    if verbose:
        print_statusline('Loading sm calibration file: ' + path.basename(path.normpath(latest_file)))
    sm_ls1_pos, sm_ls2_pos = np.loadtxt(latest_file)
    sm.limit_switch_1_pos = sm_ls1_pos
    sm.limit_switch_2_pos = sm_ls2_pos
    sm.calibration = True
    return sm_ls1_pos, sm_ls2_pos


@ignore_stderr
def get_wavelength():
    spec = instrument(**bristol_params)
    lm = spec.get_wavelength()
    spec.close()
    return lm

@ignore_stderr
def get_spectrum(plot=True,save=True):
    spec = instrument(**bristol_params)
    lm, psd = spec.get_spectrum()
    spec.close()
    lm = lm.to(u.um)
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'IPG_SFTL_spectrum_' + timestamp_str + '.txt'
    if save:
        np.savetxt(path.normpath(path.join(spectra_save_dir,fname)),
                np.stack((lm.magnitude,psd)))
    if plot:
        fig = plt.figure(figsize=(12,12))
        ax = fig.add_subplot(111)
        ax.plot(lm,psd,'C3')
        ax.grid()
        ax.set_xlabel('$\lambda$ [$\mu$m]')
        ax.set_ylabel('PSD [dBm/spectral bin]')
        if save:
            ax.set_title('data saved to file:\n'+fname)
        fig.tight_layout()
        plt.show()
    return lm,psd

@ignore_stderr
def calibrate_grating(speed=3000,x_min=0*u.mm,x_max=None,nx=10):
    spec = instrument(**bristol_params)
    # prepare data arrays
    if not x_max:
        x_max = (sm.limit_switch_2_pos - sm.limit_switch_1_pos) * sm.travel_per_microstep

    x_comm = np.linspace(x_min.to(u.mm).magnitude,x_max.to(u.mm).magnitude,nx) * u.mm
    lm = np.empty(len(x_comm)) * u.nm
    # collect data
    for xind, x in enumerate(x_comm):
        print('Acquiring wavelength {} of {}...'.format(xind+1,len(x_comm)))
        sm.go_and_wait(x,speed=speed)
        lm[xind] = spec.get_wavelength()
        print('...found to be {:7.3f} nm'.format(lm[xind].to(u.nm).magnitude))
    # close spectrometer to end errors
    spec.close()

    # generate interpolation function
    grating_tuning_model = interp1d(lm,x_comm)

    # save data
    timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'IPG_SFTL_grating_calibration_' + timestamp_str + '.txt'
    np.savetxt(path.normpath(path.join(grating_calibration_save_dir,fname)),
                np.stack((x_comm.magnitude,lm.magnitude)))

    return x_comm, lm, grating_tuning_model

@ignore_stderr
def init(speed=1000,nx=30,recalibrate=False):
    if recalibrate:
        sm.go_and_wait(0)
        sm.initialize_calibration()
        calibrate_grating(speed=speed,nx=nx)
    else:
        load_newest_stepper_motor_calibration()
        load_newest_grating_calibration()


def load_newest_grating_calibration(verbose=False):
    file_list =  glob(path.normpath(grating_calibration_save_dir)+path.normpath('/IPG_SFTL_grating_calibration*'))
    latest_file = max(file_list,key=path.getctime)
    if verbose:
        print_statusline('Loading grating calibration file: ' + path.basename(path.normpath(latest_file)))
    x_grating_cal, lm_grating_cal = np.loadtxt(latest_file)
    lm_x_grating_model = interp1d(lm_grating_cal,x_grating_cal)
    return x_grating_cal, lm_grating_cal, lm_x_grating_model


def _overstep_high(spec,lm_meas,n_iter_max=20):
    n_iter=0
    while ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ) and (n_iter < n_iter_max):
        lm_err = -5 * u.nm
        curr_pos_steps = sm.get_current_position(unitful=False)
        relative_move = int((lm_err / dlm_dstep).to(u.dimensionless).magnitude)
        target_pos_steps = curr_pos_steps + relative_move
        sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)
        lm_meas = spec.get_wavelength()


def _overstep_low(spec,lm_meas,n_iter_max=20):
    n_iter=0
    while ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ) and (n_iter < n_iter_max):
        lm_err = 5 * u.nm
        curr_pos_steps = sm.get_current_position(unitful=False)
        relative_move = int((lm_err / dlm_dstep).to(u.dimensionless).magnitude)
        target_pos_steps = curr_pos_steps + relative_move
        sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)
        lm_meas = spec.get_wavelength()

def get_poling_region(lm):
    shg_data = load_newest_SHG_calibration()
    shg_phase_matching_ranges = [(data['lm_phase_match'].min(),data['lm_phase_match'].max()) for data in shg_data]
    in_range = [lr[0]<lm<lr[1] for lr in shg_phase_matching_ranges]
    if not any(in_range):
        return False
    possible_regions = np.arange(len(in_range))[in_range]
    if np.sum(np.array(in_range)) > 1:
        closest_ind = np.argmin(np.abs(current_poling_region - possible_regions))
        return possible_regions[closest_ind]
    else:
        return possible_regions[0]

@ignore_stderr
def set_wavelength(lm,closed_loop=True,tune_SHG=True,wait_for_SHG=False,check_lm=False,n_iter_max=100,spec_wait_time=2*u.second):
    shg_data = load_newest_SHG_calibration()
    if tune_SHG:
        poling_region = get_poling_region(lm)
        if poling_region:
            T_set = Q_(np.asscalar(shg_data[poling_region]['phase_match_model'](lm)),u.degC)
            print('tuning SHG:')
            print('\tpoling region: {}, LM={:2.4f}um'.format(current_poling_region,LM_cov[current_poling_region].magnitude))
            print('\tset temperature: {:4.1f}C'.format(T_set.magnitude))
            if wait_for_SHG:
                oc.set_temp_and_wait(T_set,max_err=temp_max_err,n_samples=n_temp_samples,timeout=temp_timeout)
            else:
                oc.set_set_temp(T_set)
        # except:
        #     print('warning: error in tune_SHG routine')
    x_grating_cal, lm_grating_cal, lm_x_grating_model = load_newest_grating_calibration()
    x_comm = float(lm_x_grating_model(lm)) * u.mm
    sm.go_and_wait(x_comm,polling_period=100*u.ms)
    with bristol_temp() as spec:
        if closed_loop:
            lm_meas = spec.get_wavelength()
            if ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ):
                if lm > (2300 * u.nm):
                    _overstep_high(spec,lm_meas)
                    lm_meas = spec.get_wavelength()
                else:
                    _overstep_low(spec,lm_meas)
                    lm_meas = spec.get_wavelength()
            lm_err = lm - lm_meas
            n_iter = 0
            while (float(abs(lm_err.to(u.nm).magnitude))>0.05) and (n_iter < n_iter_max):
                curr_pos_steps = sm.get_current_position(unitful=False)
                relative_move = int((lm_err / dlm_dstep).to(u.dimensionless).magnitude)
                target_pos_steps = curr_pos_steps + relative_move
                if not(sm.limit_switch_1_pos<target_pos_steps<sm.limit_switch_2_pos):
                    print('Warning: bad target_pos_steps: {:2.1g}, lm_meas:{:7.3f}\n'.format(target_pos_steps,float(lm_meas.magnitude)))
                    target_pos_steps = 0
                sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)
                sleep(spec_wait_time.to(u.second).magnitude)
                lm_meas = spec.get_wavelength()
                if ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ):
                    if lm > (2300 * u.nm):
                        _overstep_high(spec,lm_meas)
                        lm_meas = spec.get_wavelength()
                    else:
                        _overstep_low(spec,lm_meas)
                        lm_meas = spec.get_wavelength()
                lm_err = lm - lm_meas
                n_iter += 1
                print_statusline('setting wavelength to {:7.3f}, loop 1, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm.to(u.nm).magnitude),float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
            while (float(abs(lm_err.to(u.nm).magnitude))>0.03) and (n_iter < n_iter_max):
                if float(lm_err.to(u.nm).magnitude) > 0:
                    sm.step_foreward()
                    sleep(spec_wait_time.to(u.second).magnitude)
                    lm_meas = spec.get_wavelength()
                    lm_err = lm - lm_meas
                    n_iter += 1
                    print_statusline('setting wavelength to {:7.3f}, loop 2, step forward, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm.to(u.nm).magnitude),float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
                else:
                    sm.step_backward()
                    sleep(spec_wait_time.to(u.second).magnitude)
                    lm_meas = spec.get_wavelength()
                    lm_err = lm - lm_meas
                    n_iter += 1
                    print_statusline('loop 2, step backward, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
            print_statusline('measured wavelength: {:7.3f}nm, target wavelength {:7.3f}nm reached (or gave up) in {:} steps'.format(float(lm_meas.to(u.nm).magnitude),float(lm.to(u.nm).magnitude),n_iter))
        if check_lm:
            lm_check = spec.get_wavelength()
            print(''.format(lm_check.to(u.nm).magnitude))

### define a utility version of set_wavelength that takes in a spec (bristol spectormeter)
### object rather than create its own with a 'with' statement. This way this
### utility function can work inside another function (loop maybe) and not
### create and destroy many spectrometer instances, which I've found makes
### windows poop its pants.

def _set_wavelength(lm,spec,closed_loop=True,check_lm=False,n_iter_max=100,spec_wait_time=2*u.second):
    x_grating_cal, lm_grating_cal, lm_x_grating_model = load_newest_grating_calibration()
    x_comm = float(lm_x_grating_model(lm)) * u.mm
    sm.go_and_wait(x_comm,polling_period=100*u.ms)
    if closed_loop:
        lm_meas = spec.get_wavelength()
        if ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ):
            if lm > (2300 * u.nm):
                _overstep_high(spec,lm_meas)
                lm_meas = spec.get_wavelength()
            else:
                _overstep_low(spec,lm_meas)
                lm_meas = spec.get_wavelength()
        lm_err = lm - lm_meas
        n_iter = 0
        while (float(abs(lm_err.to(u.nm).magnitude))>0.05) and (n_iter < n_iter_max):
            curr_pos_steps = sm.get_current_position(unitful=False)
            relative_move = int((lm_err / dlm_dstep).to(u.dimensionless).magnitude)
            target_pos_steps = curr_pos_steps + relative_move
            if not(sm.limit_switch_1_pos<target_pos_steps<sm.limit_switch_2_pos):
                print('Warning: bad target_pos_steps: {:2.1g}, lm_meas:{:7.3f}\n'.format(target_pos_steps,float(lm_meas.magnitude)))
                target_pos_steps = 0
            sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)
            sleep(spec_wait_time.to(u.second).magnitude)
            lm_meas = spec.get_wavelength()
            if ( (lm_meas>(2600*u.nm)) or (lm_meas<(2000*u.nm)) ):
                if lm > (2300 * u.nm):
                    _overstep_high(spec,lm_meas)
                    lm_meas = spec.get_wavelength()
                else:
                    _overstep_low(spec,lm_meas)
                    lm_meas = spec.get_wavelength()
            lm_err = lm - lm_meas
            n_iter += 1
            print_statusline('setting wavelength to {:7.3f}, loop 1, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm.to(u.nm).magnitude),float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
        while (float(abs(lm_err.to(u.nm).magnitude))>0.03) and (n_iter < n_iter_max):
            if float(lm_err.to(u.nm).magnitude) > 0:
                sm.step_foreward()
                sleep(spec_wait_time.to(u.second).magnitude)
                lm_meas = spec.get_wavelength()
                lm_err = lm - lm_meas
                n_iter += 1
                print_statusline('setting wavelength to {:7.3f}, loop 2, step forward, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm.to(u.nm).magnitude),float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
            else:
                sm.step_backward()
                sleep(spec_wait_time.to(u.second).magnitude)
                lm_meas = spec.get_wavelength()
                lm_err = lm - lm_meas
                n_iter += 1
                print_statusline('loop 2, step backward, lm_meas: {:7.3f}nm, lm_err: {:6.3f}nm, n_iter: {:}'.format(float(lm_meas.to(u.nm).magnitude),float(lm_err.to(u.nm).magnitude),n_iter))
        print_statusline('measured wavelength: {:7.3f}nm, target wavelength {:7.3f}nm reached (or gave up) in {:} steps'.format(float(lm_meas.to(u.nm).magnitude),float(lm.to(u.nm).magnitude),n_iter))
    if check_lm:
        lm_check = spec.get_wavelength()
        print(''.format(lm_check.to(u.nm).magnitude))




def _save_SHG_data(save_data,new_timestamp=True,timestamp_str=None):
    if new_timestamp:
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    fname = 'IPG_SFTL_SHG_calibration_' + timestamp_str
    np.save(path.normpath(path.join(SHG_calibration_save_dir,fname)),save_data)

# def _set_wavelength(lm,spec):


@ignore_stderr
def calibrate_SHG(n_poling_region,temp_min,temp_max,n_temp,lm_min,lm_max,n_lm,n_avg_P=9000,n_temp_samples=10,temp_timeout=30*u.minute,temp_max_err=Q_(0.05,u.degK),P_meas_time=0.3*u.second,temp_scan_up=True):
    # specific settings to thorlabs PM100D power meter. these won't work if using a differnt one
    pwrmtr._inst.timeout=10000 # set timeout to 10 sec for 3 sec averaging
    pwrmtr.set_num_averaged(int(3000 * P_meas_time.to(u.second).magnitude)) # roughly 1 measumrent every 3ms, so ~3000 measurements per second
    ###
    x_grating_cal, lm_grating_cal, lm_x_grating_model = load_newest_grating_calibration()
    if temp_scan_up:
        temp_cmd = Q_(np.linspace(temp_min.to(u.degC).magnitude,temp_max.to(u.degC).magnitude,n_temp), u.degC)
    else:
        temp_cmd = Q_(np.linspace(temp_max.to(u.degC).magnitude,temp_min.to(u.degC).magnitude,n_temp), u.degC)
    lm_cmd = np.linspace(lm_min.to(u.nm).magnitude,lm_max.to(u.nm).magnitude,n_lm) * u.nm
    #x_cmd = lm_x_grating_model(lm_comm) * u.mm
    #lm_meas = np.empty((n_temp,n_lm)) * u.nm
    P_SHG = np.empty((n_temp,n_lm)) * u.watt
    temp_timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
    with bristol_temp() as spec:
        for tind, tt in enumerate(temp_cmd):
            oc.set_temp_and_wait(tt,max_err=temp_max_err,n_samples=n_temp_samples,timeout=temp_timeout)
            for lind, ll in enumerate(lm_cmd):
                _set_wavelength(ll,spec)
                P_SHG[tind,lind] = pwrmtr.get_power()
                progress = (tind * n_lm + lind) * ( 100.0 / ( n_lm * n_temp ) )
                print_statusline('temp: {:6.3f}C, lm: {:7.3f}nm, P_SHG: {:5.2f}mW, progress: {:3.1f}%'.format(float(tt.to(u.degC).magnitude),float(ll.to(u.nm).magnitude),float(P_SHG[tind,lind].to(u.mW).magnitude),progress))
                # save data
                save_data = np.array([temp_cmd, lm_cmd, P_SHG])
                _save_SHG_data(save_data,new_timestamp=False,timestamp_str=temp_timestamp_str)

    _save_SHG_data(save_data)

    return temp_cmd, lm_cmd, P_SHG


def load_newest_SHG_calibration(verbose=False,cutoff_factor=30):
    dir_list = glob(path.normpath(SHG_calibration_save_dir)+'/*/')
    SHG_data = list(dir_list)
    if verbose:
        print_statusline('{} SHG calibration folders found: '.format(len(dir_list))+str([s.split('\\')[-2] for s in dir_list]))
    for d_ind, dd in enumerate(dir_list):
        dir_string = dd.split('\\')[-2]
        file_list = glob(path.normpath(dd+'IPG_SFTL_SHG_calibration_'+dir_string+'*'))
        latest_file = max(file_list,key=path.getctime)
        temp_cmd, lm_cmd, P_SHG = np.load(latest_file)
        P_SHG_max = P_SHG.max(axis=0)
        P_SHG_norm = (P_SHG / P_SHG_max)
        P_SHG_mask = P_SHG_max > P_SHG.max()/cutoff_factor
        P_SHG_max_ind = np.argmax(P_SHG,axis=0)[P_SHG_mask]
        lm_phase_match = lm_cmd[P_SHG_mask]
        T_phase_match = temp_cmd[P_SHG_max_ind]
        phase_match_model = interp1d(lm_phase_match,T_phase_match)
        data_dict = {'period':Q_(dir_string.split('_')[1]),
                    'temp_cmd':temp_cmd,
                    'lm_cmd':lm_cmd,
                    'P_SHG':P_SHG,
                    'P_SHG_max':P_SHG_max,
                    'P_SHG_norm':P_SHG_norm,
                    'lm_phase_match':lm_phase_match,
                    'T_phase_match':T_phase_match,
                    'phase_match_model':phase_match_model
                    }
        SHG_data[d_ind] = data_dict
        if verbose:
            print_statusline('from ' + dir_string + ' loading newest file: ' + latest_file.split('\\')[-1])
    return SHG_data

shg_data = load_newest_SHG_calibration()
shg_phase_matching_ranges = [(data['lm_phase_match'].min(),data['lm_phase_match'].max()) for data in shg_data]


def plot_SHG_data():
    # temp_cov = Q_(data_cov[0,:],u.degC)
    # lm_cov = data_cov[1:,:] * u.nm
    # LM_cov = np.array([34,34.8,35.5,35.8,35.97]) * u.um
    shg_data = load_newest_SHG_calibration()
    for LM_ind, LM in enumerate(LM_cov):
        plt.plot(temp_cov,lm_cov[LM_ind,:],color='C{}'.format(LM_ind),label='{:4.2f}$\mu$m (Covesion)'.format(LM.magnitude))
        if len(shg_data)>=LM_ind+1:
            plt.plot(shg_data[LM_ind]['phase_match_model'](shg_data[LM_ind]['lm_phase_match']),shg_data[LM_ind]['lm_phase_match'],'--.',color='C{}'.format(LM_ind),label='{:4.2f}$\mu$m'.format(LM.magnitude))
    plt.grid()
    ax = plt.gca()
    ax.legend()
    ax.set_xlabel('temperature [C]')
    ax.set_ylabel('fundamental wavelength [nm]')
    plt.show()
