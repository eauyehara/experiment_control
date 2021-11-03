"""
script to test Galvo-Scanning imaging code for the SHG microscope
"""
from shg_microscope import *
import matplotlib.pyplot as plt

# tests
nx, ny      =   300           ,       200
ΔVx, ΔVy    =   0.6*u.volt      ,       0.4*u.volt
fsamp       =   200*u.Hz

write_data, read_data, proc_data, wf_img = collect_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp)

# scan_task, write_data = configure_scan(nx,ny,ΔVx,ΔVy,Vx0,Vy0,fsamp)
# read_data = scan_task.run(write_data)


# t = read_data['t']
# Vshg = read_data[ch_Vshg_str]
# Vpm  = read_data[ch_Vpm_str]
# Vx_meas = read_data[ch_Vx_meas_str]
# Vy_meas = read_data[ch_Vy_meas_str]
# Vx_scan = write_data[ch_Vx_p_str] - write_data[ch_Vx_n_str]
# Vy_scan = write_data[ch_Vy_p_str] - write_data[ch_Vy_n_str]
# Vx,Vy = scan_vals(nx,ny,ΔVx,ΔVy,Vx0,Vy0)
# Vx_g, Vy_g = meshgrid(Vx.m,Vy.m)
# Vshg_g = griddata((Vx_meas.m,Vy_meas.m),Vshg.m,(Vx_g,Vy_g))



# p0 = plt.pcolormesh(Vx.m,Vy.m,Vshg_g)
# plt.show()

# p0 = plt.plot(range(nx*ny),vr0.m,range(nx*ny),vr1.m)

# plt.plot(t.to(u.ms).m,vi2.m,t.to(u.ms).m,vi3.m,t.to(u.ms).m,vo0.m,t.to(u.ms).m,vo1.m)
# p0 = plt.pcolormesh(Vx.m,v1.m,vi0g.m); plt.colorbar(p0)
# p1 = plt.pcolormesh(Vx.m,v1.m,vi1g.m); plt.colorbar(p1)
# plt.show()
