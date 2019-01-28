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
import h5py
import time

# parameters that might need to be updated for my libraries to work
lia_address = 'ASRL9::INSTR'
scope0_address = 'USB0::0x0699::0x0374::C010960::INSTR'
scope3_address = 'TCPIP0::171.64.85.36::INSTR' # rigol scope
default_data_dir = 'C:/Users/Lab/Google Drive/data/'
github_dir = "C:/Users/Lab/Lab Software/GitHub/experiment_control"
# temp_mon_dir = "C:/Users/Lab/Lab Software/GitHub/experiment_control/temp_monitor"
DAQ_server='171.64.84.21' # DAQ-server IP address
DAQ_name = 'PCI-6713' # daq's instrumental saved instrument name on DAQ-server
#argos_address = 'ASRL1::INSTR'

# import my libraries
if github_dir not in sys.path:
    sys.path.append(github_dir)
# if temp_mon_dir not in sys.path:
#     sys.path.append(temp_mon_dir)

from xantrex import xhr_write # control function for Xantrex XHR 300V supply via LabJack
import ipg_sftl_lib as ipg
from experiment_utilities import print_statusline
from sample_mount_temp_control import set_temp_and_wait, get_meas_temp, get_set_temp,set_set_temp
from plotting_imports import plt

# initialize IPG SFTL
ipg.init()

# connect to scopes
#scope0 = instrument(module='scopes.tektronix', classname='MSO_DPO_4000', visa_address=scope0_address) # DPO2024 above microscope, 4ch, 200MHz, 1.25M samples 1GS/s, USB
#scope1 = instrument(module='scopes.tektronix', classname='TDS_3000', visa_address='TCPIP0::171.64.84.205::INSTR') # TDS 3032 above laser, 2ch, 300MHz, 10k samples @ 2.5GS/s, ethernet
scope2 = instrument(module='scopes.tektronix', classname='TDS_600', visa_address='GPIB0::19::INSTR') # TDS 654C, 4ch, 500MHz, 15k samples @ 5GS/s, GPIB
scope3 = instrument(module='scopes.tektronix', classname='TDS_3000', visa_address='TCPIP0::171.64.86.67::INSTR') # TDS 3034B above microscope, borrowed from nate (what a guy, right?), 4ch, 300MHz, 10k samples @ 2.5GS/s, ethernet

# connect to NI DAQ for analog outputs on remote DAQ-server
daq = instrument(DAQ_name,server=DAQ_server)

## connect to function generators
# Tektronix AFG3102 (x2)
afg0_visa_address = 'TCPIP0::171.64.85.99::INSTR' # Tektronix AFG3102, closer to Nate's side of lab, connected via ethernet, static IP, hostname ml-tek-afg-0.stanford.edu
afg1_visa_address = 'TCPIP0::171.64.85.108::INSTR' # Tektronix AFG3102, closer to David's desk along wall, connected via ethernet, static IP, hostname ml-tek-afg-1.stanford.edu
# afg0 = instrument({'visa_address':afg0_visa_address,'module':'funcgenerators.tektronix'}) #need to specify classname (1/26/2019); potential error due usage of an older version of Instrumental.
# afg1 = instrument({'visa_address':afg1_visa_address,'module':'funcgenerators.tektronix'})
afg0 = instrument(module='funcgenerators.tektronix', classname='AFG_3000', visa_address=afg0_visa_address)
afg1 = instrument(module='funcgenerators.tektronix', classname='AFG_3000', visa_address=afg1_visa_address)

# Rigol DG1022A
rigol_afg_visa_address = 'USB0::0x0400::0x09C4::DG1F161350053::INSTR'
rigol_afg = instrument({'visa_address':rigol_afg_visa_address,'module':'funcgenerators.rigol'}) # just a low-level visa interface for ASCII commands for now
#

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



def configure_lia(t_scan=2*u.second,sensitivity=sr850.Sensitivity.x50uV_pA,reference_phase=0*u.degree,
                 time_constant=sr850.TimeConstant.x10ms,sample_rate=sr850.ScanSampleRate.x64Hz):
    ## configure LIA
    lia.clear_registers()
    # turn off alarms to avoid lots of trigger noises
    lia.set_alarm_mode(sr850.AlarmMode.off)
    # configure reference frequency
    lia.set_reference_source(sr850.ReferenceSource.external) # use chopper reference out as lock-in reference signal
    lia.set_reference_slope(sr850.ReferenceSlope.ttl_rising)
    lia.set_reference_phase(reference_phase) # checked for current alignment by maximizing signal and running auto_phase, then checking reference phase
    # configure inputs
    lia.set_input_coupling(sr850.InputCoupling.AC)
    #lia.set_input_ground(sr850.InputGround.floating)
    lia.set_input_ground(sr850.InputGround.ground)
    lia.set_input_configuration(sr850.InputConfiguration.I)
    lia.set_current_gain(sr850.CurrentGain.oneHundredMegaOhm)
    lia.set_line_filter_status(sr850.LineFilter.both_filters)

    # configure gain, time constant, sensitivity
    lia.set_sensitivity(sensitivity)
    lia.set_time_constant(time_constant)
    lia.set_low_pass_slope(sr850.LowPassSlope.twentyfour_dB_per_octave)

    # configure scans and traces
    lia.set_trace_definitions(sr850.TraceNumber.one,sr850.Multiply.X)
    lia.set_trace_definitions(sr850.TraceNumber.two,sr850.Multiply.Y)
    lia.set_trace_definitions(sr850.TraceNumber.three,sr850.Multiply.X_n)
    lia.set_trace_definitions(sr850.TraceNumber.four,sr850.Multiply.Y_n)
    lia.set_scan_mode(sr850.ScanMode.single_shot)
    lia.set_scan_sample_rate(sample_rate)
    lia.set_scan_length(t_scan)
    lia.set_trigger_start_scan_mode(sr850.TriggerStartScanMode.yes)
    #lia.reset_scan()


traces_12_on = {'V_24_ref':(scope2,1),
           'V_12_ref':(scope2,2),
           'V_ring':(scope2,3),
           'V_piezo_fp':(scope2,4),
           'V_24_trans':(scope3,1),
           'V_12_trans':(scope3,2),
           'V_trans_fp':(scope3,4),
          }

traces_12_off = {'V_24_ref':(scope2,1),
           'V_ring':(scope2,3),
           'V_piezo_fp':(scope2,4),
           'V_24_trans':(scope3,1),
           'V_trans_fp':(scope3,4),
           'V_SHG_X':(lia,sr850.TraceNumber.one),
           'V_SHG_Y':(lia,sr850.TraceNumber.two),
          }


def configure_12_phase_mod(f=500*u.kHz,afg=afg1,V_pp_1=6*u.volt,Z_out_1='max',V_pp_2=4.7*u.volt,Z_out_2='max',phase_2=128*u.deg):
    afg.disable_output(channel=1)
    afg.disable_output(channel=2)
    afg.set_output_impedance(impedance=Z_out_1,channel=1)
    afg.set_output_impedance(impedance=Z_out_2,channel=2)
    afg.set_function(shape='sinusoid',vpp=V_pp_1,offset=0*u.volt,channel=1)
    afg.set_function(shape='sinusoid',vpp=V_pp_2,offset=0*u.volt,phase=phase_2,channel=2)
    afg.set_frequency(f,channel=1)
    afg.set_frequency(f,channel=2)
    afg.enable_output(channel=1)
    afg.enable_output(channel=2)

def set_afg_sqrt_ramp(f=0.1*u.Hz,V_max=1.2*u.volt,V_min=0*u.volt,Z_out='max',ch=1,afg=afg0,n_pts=10000):
    x = np.arange(n_pts) * 1.0
    ramp = np.piecewise(x,
                     [x<5000.0, x>=5000.0],
                     [lambda x: 2 * x / n_pts,
                      lambda x: 2 - ( 2 * x / n_pts )]
                    )
    sqrt_ramp = np.sqrt(ramp)
    afg.disable_output(channel=ch)
    afg.set_frequency(f,channel=ch)
    afg.set_arb_func(sqrt_ramp)
    sleep(0.1)
    afg.set_output_impedance(impedance=Z_out,channel=ch)
    afg.set_function(shape='EMEMory',high=V_max,low=V_min,channel=ch)
    afg.enable_output(channel=ch)

def configure_ring_mod(f_ring=0.5*u.Hz,afg=afg0,V_max_ring=1.2*u.volt,
                        V_min_ring=0*u.volt,Z_out_ring='max',ch_ring=1,):
    set_afg_sqrt_ramp(f=f_ring,V_max=V_max_ring,V_min=V_min_ring,Z_out=Z_out_ring,ch=ch_ring)

def configure_fp_mod(f_fp,afg=afg0,V_max_fp=9*u.volt,V_min_fp=0*u.volt,Z_out_fp='max',ch_fp=2,toggle_enable=False):
    if toggle_enable:
        afg.disable_output(channel=ch_fp)
    afg.set_output_impedance(impedance=Z_out_fp,channel=ch_fp)
    afg.set_function(shape='ramp',high=V_max_fp,low=V_min_fp,channel=ch_fp)
    afg.set_frequency(f_fp,channel=ch_fp)
    if toggle_enable:
        afg.enable_output(channel=ch_fp)

def configure_12_chop(f_12_chop=60*u.kHz,sleep_time=30*u.ms):
    rigol_afg.use_external_clock()
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('output:load inf')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('output:load:ch2 inf')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('function square')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('function:ch2 square')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('function:square:dcycle 50.0') # chop square wave duty cycle in %
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('function:square:dcycle:ch2 50.0') # chop square wave duty cycle in %
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write(f'frequency {f_12_chop.to(u.Hz).m:6.3E}')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write(f'frequency:ch2 {f_12_chop.to(u.Hz).m:6.3E}')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('voltage:high 5.0')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('voltage:low 0.0')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('voltage:high:ch2 2.9') # rigol DG1022A ch2 has a lower voltage range, this is for the TTL frequency reference input to SR850 lock-in amplifier
    sleep(sleep_time.to(u.second).m)
    rigol_afg.write('voltage:low:ch2 0.0')
    sleep(sleep_time.to(u.second).m)
    rigol_afg.enable(ch=2) # turn on reference frequency signal, this is left on all the time so that the lock-in is always ready


def configure_measurement(f_ring=0.5*u.Hz,f_phase_mod=500*u.kHz,f_fp_ratio=20,f_12_chop=60*u.kHz,
                            lia_sensitivity=sr850.Sensitivity.x50uV_pA,lia_time_constant=sr850.TimeConstant.x10ms):
    ### pause oscilloscope acquisition
    # scope3.stop_acquire()
    # sleep(0.1)
    # scope2.stop_acquire()
    ### configure scope3 (DPO 2024)
    scope3.write('hor:reco 10000')
    sleep(0.1)
    #dpo_2024_scale = (1 / ( 10.0 * f_ring )).to(u.second).m
    tds_3034_scale = (1 / ( 10.0 * f_ring )).to(u.second).m
    scope3.write(f'hor:sca {tds_3034_scale:7.4E}')
    sleep(0.1)
    scope3.write('hor:pos 50') # sets the horizontal postion so that 50% (the '50') of the waveform is to the left of the trigger
    ### configure scope2 (TDS 654C)
    scope2.write('hor:reco 5000') # set record length to 5000 points (10 divisions)
    sleep(0.1)
    tds_654_scale = (1 / ( 100.0 * f_ring )).to(u.second).m
    # ideally makes entire 5000 point record correspond to one period of slow modulation, but scale is rounded to 1,2,5,10,20,50,etc. weird factor of 50 for some reason
    scope2.write(f'hor:sca {tds_654_scale:3.1E}')
    sleep(0.1)
    scope2.write('hor:pos 50') # sets the horizontal postion so that 50% (the '50') of the waveform is to the left of the trigger

    configure_lia(t_scan=(1/f_ring).to(u.second),sensitivity=lia_sensitivity,time_constant=lia_time_constant)
    configure_scope_triggers()
    ### configure and start modulation
    configure_12_phase_mod(f=f_phase_mod)
    configure_ring_mod(f_ring=f_ring)
    configure_fp_mod(f_fp=f_fp_ratio*f_ring)
    configure_12_chop(f_12_chop=f_12_chop)



def configure_scope_triggers():
    # TDS 3034B trigger
    scope3.write('trigger:a:type edge')
    scope3.write('trigger:a:edge:source ext')
    scope3.write('trigger:a:edge:coupling dc')
    scope3.write('trigger:a:edge:slope rise')
    scope3.write('trigger:a:level 0.31')
    # TDS 654C trigger
    scope2.write('trigger:main:type edge')
    scope2.write('trigger:main:edge:source ext')
    scope2.write('trigger:main:edge:coupling dc')
    scope2.write('trigger:main:edge:slope rise')
    scope2.write('trigger:main:level 3.1')


def reset_scopes():
    scope3.acquire_runstop()
    scope2.acquire_runstop()
    scope3.write('hor:sca 4E-6') # set microscope scope back to fast triggering/short timescales for alignment
    scope3.write('trigger:a:edge:source line')
    arm_triggers()

def retune_SHG(wait=False):
    ipg.tune_SHG(ipg.get_lm(),wait=wait)

def close_SHG_shutter():
    daq.ao7.write(0*u.volt)

def open_SHG_shutter():
    daq.ao7.write(5*u.volt)

def close_24_shutter():
    daq.ao6.write(0*u.volt)

def open_24_shutter():
    daq.ao6.write(5*u.volt)

def analog_switch_output_2():
    daq.ao5.write(8*u.volt)

def analog_switch_output_1():
    daq.ao5.write(0*u.volt)

def chop_12_on():
    rigol_afg.enable()

def chop_12_off():
    rigol_afg.disable()

def OPA_to_SHG():
    close_SHG_shutter()
    chop_12_on()
    analog_switch_output_2()
    sleep(0.1)

def SHG_to_OPA():
    open_SHG_shutter()
    chop_12_off()
    analog_switch_output_1()
    sleep(0.1)

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

def jog_set_temp(ΔT):
    current_set_temp = get_set_temp()
    print(f'Initial set temp: {current_set_temp}')
    new_set_temp = current_set_temp + ΔT
    print(f'Final set temp: {new_set_temp}')
    set_set_temp(new_set_temp)

def jog_stepper(n,speed=10):
    current_pos = ipg.sm.get_current_position(unitful=False)
    new_pos = current_pos + n
    λ_current = ipg.get_lm()
    print(f"Initial position: {current_pos}")
    print(f"Initial λ: {λ_current}")
    print(f"Final position: {new_pos}")
    ipg.sm.go_and_wait(new_pos,speed=10)
    λ_final = ipg.get_lm()
    print(f"final λ: {λ_final}")

def reset_laser(lm):
    ipg.pzt1.set_V(0*u.volt)
    ipg.pzt2.set_V(0*u.volt)
    ipg.set_wavelength(lm,tuning_SHG=True)



############ New OPA and/or SHG data collection code ##################

def create_dataset_file(prototype_12_on_data,prototype_12_off_data,inds,name='',attrs={},
                        short_name=False,data_dir=default_data_dir):
    if short_name:
        fname = name+'.hdf5'
    else:
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
        fname = 'OPO_data_' + name + '_' + timestamp_str+'.hdf5'
    fpath = path.normpath(path.join(data_dir,fname))
    with h5py.File(fpath, "w") as f:
        grp_12_on = f.create_group('12_on')
        grp_12_off = f.create_group('12_off')
        for t_name,t in prototype_12_on_data.items():
            ds = grp_12_on.create_dataset(t_name,
                                    (len(t[1]),)+inds,
                                    chunks=(len(t[1]),)+tuple(1 for i in inds),
                                    dtype='float64')
            ds.attrs['y_units'] = str(t[1].units)
            ds.attrs['t_units'] = str(t[0].units)
            ds.attrs['t_min'] = t[0].m.min()
            ds.attrs['t_max'] = t[0].m.max()
            ds.attrs['length'] = len(t[0].m)
            for a_name,a in attrs.items():
                try:
                    ds.attrs[a_name] = a.m
                    ds.attrs[a_name + '_units'] = a.units
                except:
                    ds.attrs[a_name] = a

        for t_name,t in prototype_12_off_data.items():
            ds = grp_12_off.create_dataset(t_name,
                                    (len(t[1]),)+inds,
                                    chunks=(len(t[1]),)+tuple(1 for i in inds),
                                    dtype='float64')
            ds.attrs['y_units'] = str(t[1].units)
            ds.attrs['t_units'] = str(t[0].units)
            ds.attrs['t_min'] = t[0].m.min()
            ds.attrs['t_max'] = t[0].m.max()
            ds.attrs['length'] = len(t[0].m)
            for a_name,a in attrs.items():
                try:
                    ds.attrs[a_name] = a.m
                    ds.attrs[a_name + '_units'] = a.units
                except:
                    ds.attrs[a_name] = a
        lm_ds = f.create_dataset('lm',inds,dtype='float64')
        lm_ds.attrs['units'] = 'nm'
        f.create_dataset('T',inds,dtype='float64')
        f.flush()
    return fpath


def grab_traces(trace_dict=traces_12_on,verbose=True):
    trace_data = {}
    for t_name,t in trace_dict.items():
        if t[0] is lia:
            if verbose:
                print_statusline(f'grabbing ' + t_name + f' trace from channel {t[1].value} on ' + t[0].model + '...')
            trace_data[t_name] = t[0].get_trace(t[1],units=u.ampere)
        else:    # otherwise data is being grabbed from a scope
            if verbose:
                print_statusline(f'grabbing ' + t_name + f' trace from channel {t[1]} on ' + t[0].model + '...')
            trace_data[t_name] = t[0].get_data(channel=t[1])
    return trace_data

def arm_triggers():
    lia.reset_scan()
    sleep(0.3)
    scope3.run_acquire()
    scope2.run_acquire()

def arm_and_wait_for_triggers(timeout=10*u.second):
    old_timeout0 = scope3._rsrc.timeout
    old_timeout2 = scope2._rsrc.timeout
    scope3._rsrc.timeout = timeout.to(u.ms).m
    scope2._rsrc.timeout = timeout.to(u.ms).m
    t0 = time.time()
    arm_triggers() # arm scope triggers to acquire single sequence used for formatting saved data
    #scope2._wait_for_OPC_SRQ(timeout)
    scope3.query('*OPC?')
    scope2.query('*OPC?')
    scope3._rsrc.timeout = old_timeout0
    scope2._rsrc.timeout = old_timeout2
    # add short delay to ensure LIA is ready. 0.05s seems to be enough
    sleep(.2)
    # lia_success = False
    # while ( (not lia_success) and ( (time.time() - t0) < timeout.to(u.second).m ) ):
    #     lia_success = not(lia.scan_in_progress())
    #     if (not lia_success):
    #         sleep(0.2)
    #     else:
    #         pass
    # if (not lia_success):
    #     raise Exception('LIA trace not acquired after {}'.format(timeout))

def grab_and_save_trace_data(fpath,inds):
    arm_and_wait_for_triggers()
    trace_data_12_on = grab_traces(trace_dict=traces_12_on)
    OPA_to_SHG()
    sleep(2.5)
    arm_and_wait_for_triggers()
    trace_data_12_off = grab_traces(trace_dict=traces_12_off)
    SHG_to_OPA()
    with h5py.File(fpath, "r+") as f:
        grp_12_on = f['12_on']
        grp_12_off = f['12_off']
        for t_name,t in trace_data_12_on.items():
            grp_12_on[t_name][(slice(None,None),)+inds] = t[1].m
        for t_name,t in trace_data_12_off.items():
            grp_12_off[t_name][(slice(None,None),)+inds] = t[1].m
        f['lm'][inds] = ipg.get_lm().m
        f['T'][inds] = get_meas_temp()
        f.flush()

def grab_prototype_trace_data():
    arm_and_wait_for_triggers()
    trace_data_12_on = grab_traces(trace_dict=traces_12_on)
    SHG_to_OPA()
    arm_and_wait_for_triggers()
    trace_data_12_off = grab_traces(trace_dict=traces_12_off)
    OPA_to_SHG()
    return trace_data_12_on, trace_data_12_off

def collect_OPO_data(lm_start,n_V_pzt,stepper_incr,n_stepper_pts,Vrb=8.5*u.volt,config=True,
    f_ring=0.5*u.Hz,name='',data_dir=default_data_dir,settle_time=1*u.second,
    color='C3',short_name=False,return_fpath=True,live_plot=True,
    pzt=ipg.pzt1,V_pzt_min=0*u.volt,V_pzt_max=60*u.volt,wait_for_SHG=False,fig=None,ax=None):

    set_Vrb(Vrb)
    SHG_to_OPA() # set control signals to send 1.2um light to microscope and measure transmission directly
    ### initialize scopes and configure AFGs and scopes if config=True
    # pause current scope acquisition
    scope3.stop_acquire()
    scope2.stop_acquire()
    sleep(0.1)
    if config:
        configure_measurement(f_ring=f_ring)
    # set oscilloscopes to single-sequence acquisition
    scope3.acquire_single()
    scope2.acquire_single()

    ## collect prototype trace data for initializing dataset file
    prototype_trace_data_12_on, prototype_trace_data_12_off  = grab_prototype_trace_data() # note, triggers are now in single sequence mode and *not* armed
    ## create sweep parameter arrays
    V_pzt = np.linspace(V_pzt_min.m,V_pzt_max.m,n_V_pzt) * u.volt
    ## create dataset file
    fpath = create_dataset_file(prototype_trace_data_12_on,prototype_trace_data_12_off,(len(V_pzt),n_stepper_pts),
            attrs={'stepper_incr':stepper_incr,},name=name,short_name=short_name,data_dir=data_dir)
    ## if plotting, initialize plot
    # if live_plot:
    #     #xlimits = [lm_set.to(u.nm).min().m-2., lm_set.to(u.nm).max().m+2.]
    #     if not ax:
    #         fig,ax=plt.subplots(1,1,figsize=(11,6))
    #         ax.set_xlabel('Wavelength [nm]')
    #         ax.set_ylabel('$P_{1.2} / P_{2.4}^2$')
    #         #ax.set_xlim(xlimits)
    #         plt.subplots_adjust(right=0.7,bottom=0.3)

    ipg.set_wavelength(lm_start,tuning_SHG=True)
    for sind in range(n_stepper_pts):
        curr_pos_steps = ipg.sm.get_current_position(unitful=False)
        relative_move = stepper_incr
        target_pos_steps = curr_pos_steps + relative_move
        if not(ipg.sm.limit_switch_1_pos<target_pos_steps<ipg.sm.limit_switch_2_pos):
            print('Warning: bad target_pos_steps: {:2.1g}, lm_meas:{:7.3f}\n'.format(target_pos_steps,float(lm_meas.magnitude)))
            target_pos_steps = 0
        ipg.sm.go_and_wait(target_pos_steps,unitful=False,polling_period=100*u.ms)
        retune_SHG(wait=wait_for_SHG)
        for Vind,VV in enumerate(V_pzt):
            pzt.set_V(VV)
            sleep(settle_time.to(u.second).m)
            pct_complete = 100. * float(sind*n_V_pzt+Vind+1) / float(n_V_pzt*n_stepper_pts)
            print_statusline(f'step {sind+1} of {n_stepper_pts}, point {Vind+1} of {n_V_pzt}, {pct_complete:3.2f}% complete')
            grab_and_save_trace_data(fpath,(Vind,sind))
    reset_scopes()
    reset_laser(lm_start)
    SHG_to_OPA()
    if return_fpath:
        return fpath
    else:
        return

            # if live_plot:
            #     x = lm_meas[np.nonzero(V_R)]
            #     if norm_with_P_trans:
            #         V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
            #         y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
            #     else:
            #         # V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
            #         # y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
            #         y = V_R[np.nonzero(V_R)]
            #     if not(( nn==0 ) and ( lind==0 ) ):
            #         line = ax.lines[n_line]
            #         line.set_xdata(x)
            #         line.set_ydata(y)
            #         ax.relim()
            #         ax.autoscale_view(True,True,True)
            #         # y_lim = ax.get_ylim()
            #         # ax.set_ylim([min(4e-14,ax.get_ylim()[1]])
            #     else:
            #         ax.semilogy(x,y,'.',color=color)
            #     fig.canvas.draw()
    # plt.subplots_adjust(right=0.9,bottom=0.1)
    # if return_fpath:
    #     return fpath,fig,ax
    # else:
    #     return fig,ax

def time_array(ds):
   return Q_(np.linspace(ds.attrs['t_min'],ds.attrs['t_max'],ds.attrs['length']),ds.attrs['t_units'])



############ Original SHG-only data collection code ###################

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
        ipg.set_wavelength(ll,tuning_SHG=False)
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
    ipg.set_wavelength(lm_start,tuning_SHG=False)
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
            V_R[lind,nn] = lia.read_output(sr850.OutputType.R) # changed to X now that I figured out the right phase (currently 10.7 degree). keeping 'V_R' name for backwards compatibility
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
                x = lm_meas[np.nonzero(V_R)][lm_meas[np.nonzero(V_R)]>(lm_start-2*u.nm)]
                if norm_with_P_trans:
                    V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
                    y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
                else:
                    # V_P_24_ref_rel = V_P_24_ref / V_P_24_ref.max()
                    # y = V_R[np.nonzero(V_R)]/V_P_24_ref_rel[np.nonzero(V_R)]**2
                    y = np.abs(V_R[np.nonzero(V_R)][lm_meas[np.nonzero(V_R)]>(lm_start-2*u.nm)])
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
