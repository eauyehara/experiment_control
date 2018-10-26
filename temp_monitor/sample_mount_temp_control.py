from instrumental import u
import labjack_client as ljc
import numpy as np
from experiment_utilities import print_statusline
import time

# parameters for RL10 NTC thermistor, RL1006-53.4K-140-D1, Digikey part KC009N-ND
beta = 4615 # degK
R_ohm_25C = 1e5 # ohm
T0 = 25 + 273.15 # degK
r_inf = R_ohm_25C * np.exp( - beta / T0 )

# probe current used by temperature controller
I_probe_amp = 1e-5 # 10uA

# Labjack DAC channel used as set-temperature input to temperature controller
setT_out_ch = 1

# Labjack ADC channel connected to measured temperature output from temperature controller
measT_in_ch = 1
setT_in_ch = 0
def thermistorRtoT(R_ohm,r_inf=r_inf,beta=beta):
    return  beta / np.log(R_ohm / r_inf) - 273.15

def thermistorTtoR(T_C,r_inf=r_inf,beta=beta):
    return  r_inf * np.exp( beta / ( T_C + 273.15 ) )

def TtoV(T_C,I_probe_amp=I_probe_amp,r_inf=r_inf,beta=beta):
    return thermistorTtoR(T_C,r_inf=r_inf,beta=beta) * I_probe_amp

def VtoT(V,I_probe_amp=I_probe_amp,r_inf=r_inf,beta=beta):
    R_ohm_inferred = V / I_probe_amp
    return thermistorRtoT(R_ohm_inferred,r_inf=r_inf,beta=beta)


def get_meas_temp():
    return VtoT(ljc.read(measT_in_ch))

def get_set_temp():
    return VtoT(ljc.read(setT_in_ch))

def set_set_temp(T_C):
    return ljc.write(TtoV(T_C),setT_out_ch)

# function to set temperature and wait for it to settle
def set_temp_and_wait(T_set,settling_threshold=0.015,t_settle_max=15*u.minute,
                        n_samples=10,dt_sample=10*u.second,verbose=False):
    print_statusline(f'setting sample temp to {T_set:2.4f}C...')
    set_set_temp(T_set)
    t0 = time.time()
    samples = np.zeros(10)
    n_samples_taken = 0
    sample_deviation = 100 # random high number, shouldn't matter
    while ( ( ( (time.time()-t0)<t_settle_max.to(u.second).m ) and (n_samples_taken<(n_samples-1)) ) or ( sample_deviation>settling_threshold ) ):
        time.sleep(dt_sample.to(u.second).m)
        new_sample = get_meas_temp()
        if n_samples_taken<n_samples:
            samples[n_samples_taken] = new_sample
        else:
            samples[:-1] = samples[1:]
            samples[-1] = new_sample
            sample_deviation = samples.max() - samples.min()
        n_samples_taken+=1
        if verbose:
            print(f'n_samples_taken: {n_samples_taken}')
            print(f'time elapsed: {(time.time()-t0):4.1f} sec')
            print(f'samples: {samples} C')
            print(f'sample_deviation: {sample_deviation:3.4f} C')
            print('#########################')
    new_temp = samples.mean()
    time_spent = (time.time()-t0)*u.second
    if time_spent.m > 60.0:
        time_spent = time_spent.to(u.minute)
        print_statusline(f'settled at {new_temp:2.3f}C after {time_spent.m:2.2f} minutes')
    else:
        print_statusline(f'settled at {new_temp:2.3f}C after {time_spent.m:2.1f} seconds')
    return new_temp
