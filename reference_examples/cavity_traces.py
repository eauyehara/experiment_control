# functions and tools for capturing, ploting and analyzing scope traces
# showing cavity resonances

# import numpy as np
# from instrumental import Q_, u, instrument
# from scipy.optimize import curve_fit
# import matplotlib.pyplot as plt
# from datetime import datetime
#
# # open oscilloscope
# scope = instrument('DPO2024')
#
# def lorentzian(x,x0,gamma):
#     return ( gamma / ( 2 * np.pi ) ) / ( ( x - x0 )**2 + ( gamma / 2.0 )**2 )
#
# def transmission_trace(ch=2,f_sb=10*u.GHz,plot=True,save=False,t_bg_min_ind=0,t_bg_max_ind=1000,delta_t_min=100*u.usec):
#     t,V = scope.get_data(channel=ch)
#     dt = t[1]-t[0]
#     ind_max = np.argmax(V)
#     t_max = t[ind_max]
#     V_bg = np.mean(V[t_bg_min_ind:t_bg_max_ind])
#     V_norm = (V-V_bg).magnitude / np.max((V-V_bg).magnitude)

import numpy as np
import matplotlib.pyplot as plt
from instrumental import Q_, u, instrument
from datetime import datetime
import cavity_trace_fitting as fitting
scope = instrument('DPO2024')
t,V = scope.get_data(channel=2)
ind0 = 420000
ind1 = 780000
params = fitting.guided_trace_fit(t[ind0:ind1],V[ind0:ind1],10*u.GHz)
#plt.plot(t[ind0:ind1],V[ind0:ind1]); plt.show()
