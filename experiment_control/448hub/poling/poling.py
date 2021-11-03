import os
import time
import numpy as np
import matplotlib.pyplot as plt
from instrumental import Q_, u, instrument
from instrumental.drivers.daq.ni import Task
from data_io import *


# daq     = instrument("NIDAQ_USB-6259")
daq     =   instrument('DAQ2_NIDAQ_USB-6259_21146242')
scope   =   instrument('Rigol_DS1054Z_DS1ZA224211034')
data_dir = os.path.join(home_dir,"Dropbox (MIT)","data","poling")

# Configure DAQ and oscilloscope channels
ch_Vctl     =   daq.ao1
ch_Vtrig    =   daq.ao3
ch_Vctl_sc  =   1
ch_Vamp_sc  =   2
ch_Vtrig_sc =   4
# ch_Vcur     =   3
# daq.port0.as_output()

# scope_config = {
#     "ReferenceSource": sr844.ReferenceSource.external,
#     "Sensitivity": sr844.Sensitivity.x300uV,
#     "TimeConstant": sr844.TimeConstant.x300us,
#     "LowPassSlope": sr844.LowPassSlope.six_dB_per_octave,
#     "Ch1OutputSource": sr844.Ch1OutputSource.X,
#     "Ch2OutputSource": sr844.Ch2OutputSource.Y,
#     "ScanMode": sr844.ScanMode.loop,
#     "TriggerStartScanMode": sr844.TriggerStartScanMode.no,
#     "ReserveMode": sr844.ReserveMode.on,
#     # "WideReserveMode": sr844.WideReserveMode.low_noise,
#     # "CloseReserveMode": sr844.CloseReserveMode.low_noise,
#     # "AlarmMode": sr844.AlarmMode.off,
#     # "ExpandSelector": sr844.ExpandSelector.x1,
# }

"""
parameterized pulse sequence function
"""
def pulse_sequence(amp_init=200*u.volt,n_init=10,amp_final=250*u.volt,gain=80,
    f_samp=100*u.kHz,negate=False,rise_time=1*u.ms,hold_time=1*u.ms,
    fall_time=1*u.ms,trigger_delay=1*u.ms,end_time=1*u.ms,**kwargs):

    t_pulse = rise_time + hold_time + fall_time # single polarity pulse duration
    t_end = trigger_delay + t_pulse * (2*n_init + 1) + end_time
    t = np.linspace(0,t_end.m_as(u.ms), int((t_end*f_samp).to(u.dimensionless).m) + 1) * u.ms
    V = np.zeros(len(t))*u.volt

    def f_init_up0(tt):
        return (tt * amp_init/rise_time.m_as(u.ms) ).to(u.volt)

    def f_init_down0(tt):
        return  ( ( ( t_pulse.m_as(u.ms) - tt ) ) * amp_init/fall_time.m_as(u.ms) ).to(u.volt).m

    def f_init_down1(tt):
        return  ( ( ( t_pulse.m_as(u.ms) - tt ) ) * amp_init/rise_time.m_as(u.ms) ).to(u.volt).m

    def f_init_up1(tt):
        return  ( ( ( -2*t_pulse.m_as(u.ms) + tt ) ) * amp_init/fall_time.m_as(u.ms) ).to(u.volt).m

    def f_final_up(tt):
        return (tt * amp_final/rise_time.m_as(u.ms)).to(u.volt).m

    def f_final_down(tt):
        return  ( ( ( t_pulse.m_as(u.ms) - tt ) ) * amp_final/fall_time.m_as(u.ms) ).to(u.volt).m

    t_rel1 = rise_time.m_as(u.ms)
    t_rel2 = (rise_time+hold_time).m_as(u.ms)
    t_rel3 = (rise_time+hold_time+fall_time).m_as(u.ms)
    t_rel4 = (2*rise_time+hold_time+fall_time).m_as(u.ms)
    t_rel5 = (2*rise_time+2*hold_time+fall_time).m_as(u.ms)
    t_rel6 = (2*rise_time+2*hold_time+2*fall_time).m_as(u.ms)
    # loop over init pulse pairs
    for i in range(n_init):
        t_mask = ( t > (trigger_delay + i * 2 * t_pulse ) ) *  ( t < (trigger_delay + (i+1) * 2 * t_pulse ) )
        t_rel = t[t_mask].m_as(u.ms) - np.min(t[t_mask].m_as(u.ms))
        init_pulses = np.piecewise(t_rel,
                                   [    t_rel<t_rel1,
                                        (t_rel>=t_rel1)*(t_rel<t_rel2),
                                        (t_rel>=t_rel2)*(t_rel<t_rel3),
                                        (t_rel>=t_rel3)*(t_rel<t_rel4),
                                        (t_rel>=t_rel4)*(t_rel<t_rel5),
                                        t_rel>=t_rel5,
                                    ],
                                   [    f_init_up0,
                                        amp_init.m,
                                        f_init_down0,
                                        f_init_down1,
                                        -amp_init.m,
                                        f_init_up1,
                                    ],
                                  )
        V[t_mask] = init_pulses * u.volt
    # add final poling pulse
    t_mask = ( t >= ( trigger_delay + n_init * 2 * t_pulse ) ) * ( t < ( trigger_delay + ( n_init + 0.5 ) * 2 * t_pulse ) )
    t_rel = t[t_mask].m - np.min(t[t_mask].m)
    final_pulse = np.piecewise(t_rel,
                               [t_rel<t_rel1,(t_rel>=t_rel1)*(t_rel<t_rel2),t_rel>=t_rel2],
                               [f_final_up,amp_final.m,f_final_down],
                              )
    V[t_mask] = final_pulse * u.volt
    if negate:
        V *= -1
    return t, V/gain

"""
Generate DAQ `Task` containing pulse sequence and synchronized trigger data
"""
def pulse_task(**kwargs):
    t, Vctl = pulse_sequence(**kwargs)
    # hacky & wasteful use of analog output as trigger... should use digital trigger
    Vtrig = np.ones(len(Vctl)) * 5*u.volt
    Vtrig[0] = 0.001*u.volt
    Vtrig[-1] = 0.001*u.volt
    
    task = Task(
        Vout_ch,
        Vtrig_ch,
    )
    task.set_timing(fsamp=(1./(t[1]-t[0])),n_samples=len(Vctl))
    write_data = {
        ch_Vctl.path    :   Vctl,
        ch_Vtrig.path   :   Vtrig,
    }
    return task, write_data

def apply_pulses(t_wait=0.2,name=None,sample_dir=None,max_num_pts=100000,**kwargs):
    sample_dir = resolve_sample_dir(sample_dir)
    fpath = new_path(name=name,data_dir=sample_dir,ds_type='PolingPulses',extension='h5',timestamp=True)
    print("saving data to: ")
    print(fpath)

    task, write_data = configure_pulse_task(**kwargs)
    dump_hdf5(write_data,fpath)
    sleep(t_wait)
    read_data = task.run(write_data)
    dump_hdf5(read_data,fpath)
    task.unreserve()


    scope_data = scope.get_data(
        ch = [ch_Vctl_sc, ch_Vamp_sc, ch_Vtrig_sc],
        max_num_pts=100000,
        t_wait=t_wait,
    )
    dump_hdf5(scope_data,fpath)
    scope.write(":run")

    return write_data.update(read_data,scope_data)
