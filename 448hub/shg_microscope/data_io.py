"""
Utility functions for saving and loading experiment and simulation data
"""

import os
import glob
import h5py
from datetime import datetime
try:
    from instrumental import Q_, u
except:
    from pint import UnitRegistry
    u = UnitRegistry()
    Q_ = u.Quantity

home_dir = os.path.expanduser("~")
default_data_dir = os.path.join(home_dir,"data")

def newest_subdir(data_dir,filter="*"):
    subdirs = [dd for dd in glob.glob(os.path.join(data_dir,filter)) if os.path.isdir(dd)]
    if subdirs:
        return max(subdirs, key=os.path.getctime)
    else:
        return None

def newest_file(data_dir,filter="*"):
    files = [ff for ff in glob.glob(os.path.join(data_dir,filter)) if os.path.isfile(ff)]
    if files:
        return max(files, key=os.path.getctime)
    else:
        return None

def new_path(name=None,data_dir=None,ds_type=None,extension='',timestamp=True):
    if not data_dir:
        data_dir = default_data_dir
    if timestamp:
        timestamp_string = datetime.strftime(datetime.now(),'%Y-%m-%d-%H-%M-%S')
    else:
        timestamp_string = None
    if extension and extension[0]!='.':
        extension = '.' + extension
    name_parts = [ds_type, name, timestamp_string]
    full_name = '_'.join([part for part in name_parts if part is not None]) + extension
    full_path = os.path.normpath(os.path.join(data_dir,full_name))
    return full_path

def dump_hdf5(ds,fpath,open_mode='a'):
    with h5py.File(fpath, open_mode) as f:
        for k,v in ds.items():
            print("dumping item: " + k)
            try:
                units = v.units
                v = v.m
            except:
                units = False
            if type(v) is np.ndarray:
                h5_ds = f.create_dataset(k,
                                        v.shape,
                                        dtype=v.dtype,
                                        data=v,
                                        compression='gzip',
                                        )
                if units:
                    h5_ds.attrs['units'] = str(units)
            else:  #
                if type(v) is list:
                    for ind,item in enumerate(v):
                        try:
                            item_units = item.units
                            item_val = item.m
                        except:
                            item_units = False
                        if item_units:
                            v[ind] = (item_val,str(item_units))
                if units:
                    print("non-array, non-list item with units:")
                    print(units)
                    # f.attrs[k] = (v,str(units))
                    f.attrs[k] = v
                    f.attrs["_".join([k,"units"])] = str(units)
                else:
                    print("non-array, non-list item without units")
                    f.attrs[k] = v
        f.flush()

def load_hdf5(fpath=None,dir=None,filter=None,sim_index=None):
    if fpath is None:
        # sim_id = ''.join(str(ind)+'-' for ind in self.param_index_combinations[sim_index])[:-1]
        file_list =  glob(os.path.normpath(dir)+os.path.normpath('/'+ sim_id + '*'))
        fpath = max(file_list,key=os.path.getctime)
    print('loading file: ' + os.path.basename(fpath))
    # with open(fpath, "rb") as f:
    #     ds = pickle.load(f)
    # for k,v in ds.items():
    #     try:
    #         ds[k] = u.Quantity.from_tuple(v)
    #     except:
    #         ds[k] = v
    ds = {}
    with h5py.File(fpath, "r") as f:
        for h5_ds_name in f:
            print('importing ' + h5_ds_name + '...')
            ds[h5_ds_name] = _load_hdf5_item(f[h5_ds_name])
        for key,val in f.attrs.items():
            print('importing attr ' + key + '...')
            # try:
            #     ds[key] = u.Quantity.from_tuple(val)
            # except:
            #     ds[key] = val
            if "_".join([key,"units"]) in f.attrs.keys():
                units_str = str(f.attrs["_".join([key,"units"])])
                print(units_str)
                ds[key] = u.Quantity(val,units_str)
            elif key.split("_")[-1]=="units":
                pass
            else:
                ds[key] = val
    return ds

def _load_hdf5_item(item):
    if issubclass(type(item),h5py.Group):
        ds = {subname: _load_hdf5_item(item[subname]) for subname in item}
        for key,val in item.attrs.items():
            try:
                ds[key] = u.Quantity.from_tuple(val)
            except:
                ds[key] = val
        return ds
    else:
        if 'units' in item.attrs:
            return Q_(item[()],item.attrs['units'])
        else:
            return item[()]

# def dump_params(self,fpath):
#     p = dict(self.params)
#     for k,v in p.items():
#         try:
#             p[k] = (v.m, str(v.units))
#         except:
#             pass
#         if type(v) is list:
#             for ind,item in enumerate(v):
#                 try:
#                     v[ind] = (item.m,str(item.units))
#                 except:
#                     pass
#                 if issubclass(type(item),LumMaterial):
#                     v[ind] = (item.__module__,item.__class__.__name__)
#         elif issubclass(type(v),LumMaterial):
#             p[k] = (v.__module__,v.__class__.__name__)
#     p['name'] = self.name
#     p['module'] = self.__module__
#     p['class'] = self.__class__.__name__
#     with open(fpath, 'w') as f:
#         yaml.dump(p,f)
#
# def load_params(self,yaml_path):
#     with open(yaml_path,'r') as f:
#         p = yaml.load(f,Loader=yaml.Loader)
#     for k,v in p.items():
#         if isinstance(v,tuple):
#             if isinstance(v[0],(float,int,complex,np.ndarray)):
#                 try:
#                     p[k]=Q_(v[0],v[1])
#                 except:
#                     pass
#             elif isinstance(v[0],str):
#                 if v[0].split('.')[0]=='lumpy':
#                     try:
#                         p[k]=getattr(importlib.import_module(v[0]), v[1])()
#                     except:
#                         pass
#         elif isinstance(v,list):
#             vc = v.copy()
#             for ind, item in enumerate(v):
#                 if isinstance(item,tuple):
#                     if isinstance(item[0],(float,int,complex,np.ndarray)):
#                         try:
#                             vc[ind]=Q_(item[0],item[1])
#                         except:
#                             pass
#                     elif isinstance(item[0],str):
#                         if item[0].split('.')[0]=='lumpy':
#                             try:
#                                 vc[ind]=getattr(importlib.import_module(item[0]), item[1])()
#                             except:
#                                 pass
#             p[k] = vc
#     return p

####### code from github.mit.edu/poe/Lumpy/lumpy/sweeps/__init__.py #####

# # -*- coding: utf-8 -*-
#
# import numpy as np
# import itertools
# import pickle
# import h5py
# import yaml
# import importlib
# import socket
# from collections import OrderedDict
# from copy import deepcopy
# from datetime import datetime
# from os import path, mkdir
# from glob import glob
# from time import sleep
#
# from .. import Q_, u, lumapi, default_data_dir, home
# from ..sims import LumSim
# from ..remote import is_local
# from ..resources import get_resource_config
# from ..materials import LumMaterial
# from .. import remote as rem #new_connection, new_session, send_cmd, send_file, make_dir,
#
# # Dictionary for looking up simulation file extensions
# simfile_extension = {   'FDTD': '.fsp',
#                         'MODE': '.lms',
#                         'DEVICE': '.ldev',
#                         'INTERCONNECT': '.icp',
#                 }
#
# solvers = { 'MODE':'FDE', # need to fix
#         }
#
# # location of blank simulation file_list
# current_dir = path.dirname(__file__)
# blank_dir = path.normpath(path.join(current_dir,'../../'))
#
#
# class DataSet(object):
#     def __init__(self,Sim,params={},verbose=True,gui=True,**kwargs):
#         if type(params) is dict or type(params) is OrderedDict:
#             self.params = params
#         elif type(params) is str and params.split('.')[-1]=='yaml':
#             self.params = self.load_params(params)
#         # self.data_dir = data_dir
#         # self.name = name
#         self.verbose = verbose
#         self.gui = gui
#         self.id_string = None       # should be set in subclasses
#         self._fill_out_params(**kwargs)
#         self._status_init()
#
#     def _status_init(self):
#         self.ds = None
#         self.data_dir = self.params['data_dir']
#         self.name = self.params['name']
#         self.multivalued_params = self._multivalued_params()
#         self.param_index_combinations = self._param_index_combinations()
#         self.param_set_list = self._param_set_list()
#         self.loaded = [0 for pic in self.param_set_list]
#         self.collected = [0 for pic in self.param_set_list]
#
#     def _fill_out_params(self,**kwargs):
#         ## First fill in all unprovided parameter values using simulation defaults
#         #dp = deepcopy(self.Sim.default_params)
#         dp = self.Sim.default_params.copy()
#         for key in list( dp.keys() ^ self.params.keys() ):
#             if key in dp.keys() and key not in self.params.keys():
#                 self.params[key] = dp[key]
#         ## Overwrite default parameter values and values given in "params" using kwargs
#         for k,v in kwargs.items():
#             self.params[k] = v
#
#     def collect(self,host='localhost'):
#         if not host or is_local(host):
#             self._collect_local()
#         else:
#             self._collect_remote(host)
#
#     def _collect_remote(self,host,remote_data_dir=None,verbose=True,delay=0.5):
#         fname = 'params.yaml'
#         local_sweep_dir = self.new_fpath(self.name,identifier_string=self.id_string,extension='') + '/'
#         local_yaml_path = local_sweep_dir + fname
#         if verbose:
#             print('local_yaml_path:')
#             print(local_yaml_path)
#             print('exists:')
#             print(str(path.isfile(local_yaml_path)))
#         if verbose:
#             print('making local sweep_dir: ' + local_sweep_dir)
#         mkdir(local_sweep_dir)
#         with rem.new_connection(host) as c:
#             if not remote_data_dir:
#                 remote_home_path  = c.run("echo ~").stdout.split('\n')[0]
#                 if verbose:
#                     print('detected remote home:')
#                     print(remote_home_path)
#                 remote_data_dir = remote_home_path + self.data_dir[len(home):]
#                 if verbose:
#                     print('remote_data_dir:')
#                     print(remote_data_dir)
#             self.params['data_dir'] = remote_data_dir
#             self.dump_params(local_yaml_path)
#             remote_sweep_dir = remote_data_dir + local_sweep_dir[len(self.data_dir):]
#             if verbose:
#                 print('remote_sweep_dir:')
#                 print(remote_sweep_dir)
#             remote_yaml_path = remote_sweep_dir + fname
#             if verbose:
#                 print('remote_yaml_path:')
#                 print(remote_yaml_path)
#             rem.new_session(c,self.name)
#             sleep(delay)
#             if verbose:
#                 print('making remote sweep_dir: ' + remote_sweep_dir)
#             rem.make_dir(c,remote_sweep_dir)
#             sleep(delay)
#             rem.send_file(c,local_yaml_path,remote_sweep_dir)
#             sleep(delay)
#             remote_collect_fpath = '~/github/poe/Lumpy/scripts/remote_collect.py'
#             cmd = 'python ' + remote_collect_fpath + ' ' + remote_yaml_path
#             res = rem.send_cmd(c,cmd)
#
#
#
#     def _collect_local(self):
#         ## find directory where dataset (parameters and output data) will live
#         sweep_dir = self.new_fpath(self.name,identifier_string=self.id_string,extension='')
#         if self.verbose:
#             print('making sweep_dir: ' + sweep_dir)
#         mkdir(sweep_dir)
#         with open(path.join(sweep_dir,'params.dat'),'wb') as f:
#             pickle.dump(self.params,f)
#         # for sim_index, sim_params in enumerate(self.param_set_list):
#         #     ds = self._run(sim_index,sim_params)
#         #     sim_id = ''.join(str(ind)+'-' for ind in self.param_index_combinations[sim_index])[:-1]
#         #     fpath = self.new_fpath(sim_id,identifier_string=None,data_dir=sweep_dir,extension='.dat')
#         #     print('saving to: ' + fpath)
#         #     self.dump_hdf5(ds,fpath)
#         #     self.collected[sim_index] = 1
#         sim_type = self.Sim.sim_type.upper()
#         ext = simfile_extension[sim_type]                               # look up appropriate simulation file extension
#         session_class = getattr(lumapi,sim_type)                            # find lumapi command for appropriate lumerical session type
#         n_sims_total = len(self.param_set_list)
#         with session_class(hide=not(self.gui)) as s:                            # instantiate lumerical session
#             s.load(path.normpath(path.join(blank_dir,'blank'+ext)))                                              # open blank file
#             s.save(path.normpath(path.join(self.data_dir,'temp'+ext)))                                                  # save temporary file
#             sim_paths = self._add_sims(s,sweep_dir)
#             if 'hosts' in self.params.keys():
#                 sweep_resources = self._config_resources(s)
#                 # print(sweep_resources)
#             s.runjobs()
#             # self._gather_results(s,sweep_dir)
#
#     def _clear_resources(self,s):
#         solver = solvers[self.Sim(None,'type_test').sim_type]
#         n_resources = int(s.getresource(solver))
#         # if more than one resource is present by default, clear all by one (cannot remove all)
#         if n_resources>1:
#             for res_ind in range(n_resources-1):
#                 s.deleteresource(solver,n_resources-res_ind)
#         # turn of off remaining default resource, should usually be Local Host
#         s.setresource(solver,1,'active',0)
#
#
#     def _config_resources(self,s):
#         # check the number of jobs in the sweep
#         # n_jobs = len(self.param_index_combinations)
#         # check the number of licenses available for the lumerical solver needed
#         solver = solvers[self.Sim(None,'type_test').sim_type]
#         # n_lic_avail = lm_status()[solver]['available']
#         # check the available computational resources on hosts in hosts list
#         # res_status = resources_status()
#         self._clear_resources(s) # intialize the resource configuration to only include "Local Host" first line
#         res_line=1 # line of "Resources" configuration table being edited
#         for h in self.params['hosts']:
#             for copy_ind in range(h['n_concurrent']):
#                 s.addresource(solver)
#                 res_line+=1
#                 s.setresource(solver,res_line,'name',h['hostname']+f' {copy_ind}')
#                 s.setresource(solver,res_line,'active',1)
#                 if is_local(h['hostname']):
#                     s.setresource(solver,res_line,'hostname','localhost')
#                 else:
#                     s.setresource(solver,res_line,'hostname',h['hostname'])
#                 s.setresource(solver,res_line,'processes',h['processes'])
#                 s.setresource(solver,res_line,'threads',h['threads'])
#                 s.setresource(solver,res_line,'active',1)
#
#         return get_resource_config(s,solver)
#
#     def _add_sims(self,s,sweep_dir):
#         sim_type = self.Sim.sim_type.upper()
#         ext = simfile_extension[sim_type]                               # look up appropriate simulation file extension
#         n_sims_total = len(self.param_set_list)
#         sim_paths = []
#         for sim_index, sim_params in enumerate(self.param_set_list):
#             s.deleteall()
#             sim_id = ''.join(str(ind)+'-' for ind in self.param_index_combinations[sim_index])[:-1]
#             sim_path = self.new_fpath(sim_id,
#                                             identifier_string=None,
#                                             data_dir=sweep_dir,
#                                             extension=ext,
#                                             timestamp=False,
#                                             )
#             sim = self.Sim(s,f'sim_{sim_index}_of_{n_sims_total}',sim_params)  # instantiate LumSim object to construct geometry and configure simulation
#             s.save(sim_path)
#             sim_paths += [sim_path]
#             s.addjob(sim_path)
#         return sim_paths
#
#
#             # with h5py.File(fpath, 'w') as f:
#             #     for k,v in ds.items():
#             #         try:
#             #             units = v.units
#             #             v = v.m
#             #         except:
#             #             units = False
#             #         if type(v) is np.ndarray:
#             #             h5_ds = f.create_dataset(k,
#             #                                     v.shape,
#             #                                     dtype=v.dtype,
#             #                                     data=v,
#             #                                     compression='gzip',
#             #                                     )
#             #             if units:
#             #                 h5_ds.attrs['units'] = str(units)
#             #         else:  #
#             #             if type(v) is list:
#             #                 for ind,item in enumerate(v):
#             #                     try:
#             #                         item_units = item.units
#             #                         item_val = item.m
#             #                     except:
#             #                         item_units = False
#             #                     if item_units:
#             #                         v[ind] = (item_val,str(item_units))
#             #                     elif issubclass(type(item),LumMaterial):
#             #                         class_str = item.__module__ +'.'+ item.__class__.__name__
#             #                         v[ind] = class_str
#             #             if issubclass(type(v),LumMaterial):
#             #                 class_str = v.__module__ +'.'+ v.__class__.__name__ # ex. 'lumpy.materials.si3n4.Si3N4'
#             #                 v = class_str
#             #             if units:
#             #                 f.attrs[k] = (v,str(units))
#             #             else:
#             #                 f.attrs[k] = v
#             #     f.flush()
#             # self.collected[sim_index] = 1
#
#     def _run(self,sim_index,params_instance):
#         ds = {}
#         p =  deepcopy(params_instance)                                          # instantiate dataset containing only parameters used
#         ds.update(p)
#         sim_type = self.Sim.sim_type.upper()                          # look up simulation ("session") type
#         session_class = getattr(lumapi,sim_type)                            # find lumapi command for appropriate lumerical session type
#         n_sims_total = len(self.param_set_list)
#         with session_class(hide=not(self.gui)) as s:                            # instantiate lumerical session
#             ext = simfile_extension[sim_type]                               # look up appropriate simulation file extension
#             s.load(path.normpath(path.join(blank_dir,'blank'+ext)))                                              # open blank file
#             s.save(path.normpath(path.join(self.data_dir,'temp'+ext)))                                                  # save temporary file
#             sim = self.Sim(s,f'sim {sim_index} of {n_sims_total}',params_instance)  # instantiate LumSim object to construct geometry and configure simulation
#             ds.update(sim.run())                                                 # run simulation
#             # ds.update(sim.output_data())                                        # run postprocessing
#         return ds                                                               # run simulation
#
#     def _multivalued_params(self):
#         multivalued_params = OrderedDict([])
#         for k,v in self.params.items():
#             if not isinstance(v,(list,str,dict,OrderedDict,bool)):
#                 if isinstance(Q_(v).m,np.ndarray):
#                     multivalued_params[k]=v
#                     if self.verbose:
#                         l = len(Q_(v).m)
#                         print('detected {:}-valued parameter: '.format(l) + k + ':')
#                         print(v)
#         return multivalued_params
#
#     def _param_index_combinations(self):
#         mvp = self.multivalued_params
#         param_indices = [range(len(Q_(v).m)) for k,v in mvp.items()]
#         param_index_combinations = list(itertools.product(*param_indices))
#         return param_index_combinations
#
#     def _param_set_list(self):
#         mvp = self.multivalued_params
#         pics = self.param_index_combinations
#         param_set_list = [deepcopy(self.params) for pic in pics]
#         for jj,pic in enumerate(pics):
#             for ii,(key,val_list) in enumerate(mvp.items()):
#                 param_set_list[jj][key] = val_list[pic[ii]]
#         return param_set_list
#
#     def load(self,sweep_dir=None):
#         if not sweep_dir:
#             if self.id_string:
#                 fname_start = self.id_string + '_' + self.name
#             else:
#                 fname_start = self.name
#             file_list =  glob(path.normpath(self.data_dir)+path.normpath('/'+ fname_start + '*'))
#             sweep_dir = max(file_list,key=path.getctime)
#             if self.verbose:
#                 print('Loading data from directory: ' + path.basename(path.normpath(sweep_dir)))
#         params_path = path.join(sweep_dir,'params.dat')
#         with open(params_path, "rb") as f:
#             self.params = pickle.load(f)
#         self._status_init()         # reinitialize swept parameter attributes
#         param_dim_sizes = list(len(vals) for key,vals in self.multivalued_params.items())
#         # load first dataset as a base for output sweep dataset dict
#         ds = self._load_single(sweep_dir,0)
#         # determine which items are "outputs" and thus need added dimensions
#         # use xor operator (^) between keys lists of "params" and "ds" dicts to find outputs and add dimensions
#         output_keys = list( ds.keys() ^ self.params.keys() )
#         # add dimenions to output variables
#         for opk in output_keys:
#             val_new = ds[opk]
#             try:
#                 val_units = val_new.units
#             except:
#                 val_units = False       # val_new has no units
#             try:
#                 val_new_shape = val_new.shape
#             except:
#                 val_new_shape = False   # this should mean val_new is a scalar rather than a vector or array
#             if val_new_shape:
#                 reps = param_dim_sizes + [1 for dim in val_new_shape]
#                 if val_units:
#                     # val_new = Q_(np.tile(val_new.m,reps).squeeze(), val_units)
#                     val_new = Q_(np.empty(reps,dtype=np.ndarray).squeeze(), val_units)
#                 else:
#                     # val_new = np.tile(val_new,reps).squeeze()
#                     val_new = np.empty(reps,dtype=np.ndarray).squeeze()
#             else:   # if val_new is scalar, just make an array of the appropriate datatype with dimensions param_dim_sizes for sweep output data
#                 # val_new_shape = (1,)
#                 # if val_units:
#                 #     val_new = Q_(np.array([val_new.m]), val_units)
#                 # else:
#                 #     val_new = np.array([val_new,])
#                 if val_units:
#                     val_new = Q_(np.empty(param_dim_sizes,dtype=type(val_new)), val_units)
#                 else:
#                     val_new = np.empty(param_dim_sizes,dtype=type(val_new))
#             ds[opk] = val_new  # replace ds dict entry opk with tiled version matching parameter dimensions
#         # populate added dimensions of output data variables with data from other files
#         for pind,pic in enumerate(self.param_index_combinations):
#             ds_temp = self._load_single(sweep_dir,pind)
#             for opk in output_keys:
#                 #### temporary fix for waveguide sweep loading when some files to not contain certain computed outputs
#                 try:
#                     val_temp = ds_temp[opk]
#                     ds[opk][pic] = val_temp
#                 except:
#                     pass
#
#             self.loaded[pind] = 1
#         # if possible, combine sweep output arrays can be combined into
#         # single n-dimensional arrays (should be possible for non-spatial data)
#         # for spatial data where the geometry was re-meshed for different
#         # parameter values, this may not be possible
#         for opk in output_keys:
#             if (ds[opk].dtype==np.ndarray) and (type(ds[opk].flatten()[0])!=list): # if data in ds[opk] is array of arrays (and not array of lists)
#                 try:
#                     if len(set([a.shape for a in ds[opk]]))==1:     # this is true if all of the arrays in ds[opk] are the same shape
#                         outer_shape = ds[opk].shape                 # dimensions of parameter sweep
#                         inner_shape = ds[opk].flatten()[0].shape    # dimensions of data at each point in parameter sweep
#                         full_shape = outer_shape + inner_shape      # dimensions of combined array
#                         data_type = type(ds[opk].flatten()[0].flatten()[0])
#                         try:
#                             data_units = ds[opk].flatten()[0].flatten()[0].units
#                         except:
#                             data_units = False
#                         if data_units:
#                             combined_array = Q_(np.empty(full_shape,dtype=data_type),data_units)
#                         else:
#                             combined_array = np.empty(full_shape,dtype=data_type)
#                         for pind,pic in enumerate(self.param_index_combinations):
#                             combined_array[pic] = ds[opk][pic]      # populate combined array
#                         ds[opk] = combined_array                    # replace array of arrays with combined array
#                 except:
#                     print('###### combining failed ##########')
#                     pass
#         for key,value in self.multivalued_params.items():
#             ds[key] = value
#         self.ds = ds
#         return ds
#
#     def _load_single(self,sweep_dir,sim_index):
#         sim_id = ''.join(str(ind)+'-' for ind in self.param_index_combinations[sim_index])[:-1]
#         file_list =  glob(path.normpath(sweep_dir)+path.normpath('/'+ sim_id + '*'))
#         fpath = max(file_list,key=path.getctime)
#         print('loading file: ' + path.basename(fpath))
#         # with open(fpath, "rb") as f:
#         #     ds = pickle.load(f)
#         # for k,v in ds.items():
#         #     try:
#         #         ds[k] = u.Quantity.from_tuple(v)
#         #     except:
#         #         ds[k] = v
#         ds = {}
#         with h5py.File(fpath, "r") as f:
#             for h5_ds_name in f:
#                 if 'units' in f[h5_ds_name].attrs:
#                     ds[h5_ds_name] = Q_(f[h5_ds_name][()],f[h5_ds_name].attrs['units'])
#                 else:
#                     ds[h5_ds_name] = f[h5_ds_name][()]
#             for key,val in f.attrs.items():
#                 try:
#                     ds[key] = u.Quantity.from_tuple(val)
#                 except:
#                     ds[key] = val
#         return ds
#
#
#     def dump_hdf5(self,ds,fpath):
#         with h5py.File(fpath, 'w') as f:
#             for k,v in ds.items():
#                 try:
#                     units = v.units
#                     v = v.m
#                 except:
#                     units = False
#                 if type(v) is np.ndarray:
#                     h5_ds = f.create_dataset(k,
#                                             v.shape,
#                                             dtype=v.dtype,
#                                             data=v,
#                                             compression='gzip',
#                                             )
#                     if units:
#                         h5_ds.attrs['units'] = str(units)
#                 else:  #
#                     if type(v) is list:
#                         for ind,item in enumerate(v):
#                             try:
#                                 item_units = item.units
#                                 item_val = item.m
#                             except:
#                                 item_units = False
#                             if item_units:
#                                 v[ind] = (item_val,str(item_units))
#                             elif issubclass(type(item),LumMaterial):
#                                 class_str = item.__module__ +'.'+ item.__class__.__name__
#                                 v[ind] = class_str
#                     if issubclass(type(v),LumMaterial):
#                         class_str = v.__module__ +'.'+ v.__class__.__name__ # ex. 'lumpy.materials.si3n4.Si3N4'
#                         v = class_str
#                     if units:
#                         f.attrs[k] = (v,str(units))
#                     else:
#                         f.attrs[k] = v
#             f.flush()
#
#
#     # def _spatial_interp(ds,ds_temp,val_temp):
#     #     """
#     #     Interpolate spatial data from dataset in a sweep (ds_temp) onto spatial coordiantes
#     #     of master dataset ds (for now ds is just the first loaded). This occurs
#     #     during sweep load() routine. First the non-trivial spatial dimensions
#     #     must be identified, and then the appropriate interpolation function run.
#     #     """
#     #     if ds['x']:
#
#     def new_fpath(self,name,identifier_string=None,data_dir=None,
#                     extension='.hdf5',timestamp=True):
#
#         if identifier_string:
#             identifier_string = identifier_string + '_'
#         else:
#             identifier_string = ''
#         if timestamp:
#             timestamp_string = '_' + datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
#         else:
#             timestamp_string = ''
#         fname = identifier_string + name + timestamp_string + extension
#         if not data_dir:
#             data_dir = self.data_dir
#         fpath = path.normpath(path.join(data_dir,fname))
#         return fpath
#
#     def draw(self,param_inds=None,ax=None,xlim=None,ylim=None,units='um',
#                 xlabel='x [μm]',ylabel='y [μm]',figsize=(10,6),alpha=1.,lw=1,
#                 sim_objects=False):
#         draw_params = self.param_set_list[param_inds]
#         # instantiate a simulation object without a Lumerical session using parameter set specified by param_inds
#         sim = self.Sim(None,'draw',params=draw_params)
#         ax,legend_patches = sim.draw(ax=ax,xlim=xlim,ylim=ylim,units=units,xlabel=xlabel,
#                     ylabel=ylabel,figsize=figsize,alpha=alpha,sim_objects=sim_objects,lw=lw)
#         return ax, legend_patches
#
#     def dump_params(self,fpath):
#         p = dict(self.params)
#         for k,v in p.items():
#             try:
#                 p[k] = (v.m, str(v.units))
#             except:
#                 pass
#             if type(v) is list:
#                 for ind,item in enumerate(v):
#                     try:
#                         v[ind] = (item.m,str(item.units))
#                     except:
#                         pass
#                     if issubclass(type(item),LumMaterial):
#                         v[ind] = (item.__module__,item.__class__.__name__)
#             elif issubclass(type(v),LumMaterial):
#                 p[k] = (v.__module__,v.__class__.__name__)
#         p['name'] = self.name
#         p['module'] = self.__module__
#         p['class'] = self.__class__.__name__
#         with open(fpath, 'w') as f:
#             yaml.dump(p,f)
#
#     def load_params(self,yaml_path):
#         with open(yaml_path,'r') as f:
#             p = yaml.load(f,Loader=yaml.Loader)
#         for k,v in p.items():
#             if isinstance(v,tuple):
#                 if isinstance(v[0],(float,int,complex,np.ndarray)):
#                     try:
#                         p[k]=Q_(v[0],v[1])
#                     except:
#                         pass
#                 elif isinstance(v[0],str):
#                     if v[0].split('.')[0]=='lumpy':
#                         try:
#                             p[k]=getattr(importlib.import_module(v[0]), v[1])()
#                         except:
#                             pass
#             elif isinstance(v,list):
#                 vc = v.copy()
#                 for ind, item in enumerate(v):
#                     if isinstance(item,tuple):
#                         if isinstance(item[0],(float,int,complex,np.ndarray)):
#                             try:
#                                 vc[ind]=Q_(item[0],item[1])
#                             except:
#                                 pass
#                         elif isinstance(item[0],str):
#                             if item[0].split('.')[0]=='lumpy':
#                                 try:
#                                     vc[ind]=getattr(importlib.import_module(item[0]), item[1])()
#                                 except:
#                                     pass
#                 p[k] = vc
#         return p
