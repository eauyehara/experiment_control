from sys import stdout
import fractions
try:
    from instrumental import u, Q_
except:
    from pint import UnitRegistry
    u = UnitRegistry()

### printing status lines, progress bars, etc.

def print_statusline(msg: str):
    last_msg_length = len(print_statusline.last_msg) if hasattr(print_statusline, 'last_msg') else 0
    print(' ' * last_msg_length, end='\r')
    print(msg, end='\r')
    stdout.flush()
    print_statusline.last_msg = msg


## convenience functions for printing variable names and values together
def namestr(obj, namespace=globals()):
    return [name for name in namespace if namespace[name] is obj][0]

def printval(x,w=4,p=1,form='f'):
    x_units = None
    try:
        x_units = str(x.unit)
        x = x.m
    except:
        pass
    if x_units:
        print(namestr(x)+ f': {x:{w}.{p}{form}} ' + x_units)
    else:
        print(namestr(x)+ f': {x:{w}.{p}{form}}')

def printspan(x,w=4,p=1,form='f'):
    x_units = None
    try:
        x_units = str(x.unit)
        x = x.m
    except:
        pass
    if x_units:
        print('max ' + namestr(x) + f': {x.max():{w}.{p}{form}} ' + x_units)
        print('min ' + namestr(x)+ f': {x.min():{w}.{p}{form}} ' + x_units)
    else:
        print('max ' + namestr(x)+ f': {x.max():{w}.{p}{form}}')
        print('min ' + namestr(x)+ f': {x.min():{w}.{p}{form}}')

### signal processing

from scipy.optimize import minimize_scalar, curve_fit
from scipy.signal import square
from scipy.interpolate import interp2d, interp1d
from scipy.integrate import trapz, cumtrapz



# define lowest common multiple function for use in Herriott cell modeling
def lcm(a,b): return abs(a * b) / fractions.gcd(a,b) if a and b else 0




def ntries(n_tries_max,errors=(Exception, ),default_value=0):
    def decorate(f):
        def new_func(*args, **kwargs):
            n_tries = 0
            success = False
            while (not(success) and (n_tries<n_tries_max)):
                try:
                    out = f(*args,**kwargs)
                    success = True
                except errors:
                    print(f'Warning: function {f.__name__} failed on attempt {n_tries+1} of {n_tries_max+1}')
                    n_tries+=1
                    out = default_value
            return out
        return new_func
    return decorate
