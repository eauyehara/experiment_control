from sys import stdout
import fractions
try:
    from instrumental import u, Q_
except:
    from pint import UnitRegistry
    u = UnitRegistry()
from matplotlib.colors import  ListedColormap
from matplotlib import rcParamsDefault
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




### plotting stuff

# add MATLAB's parula colormap because it's nice

_parula_data = [[0.2081, 0.1663, 0.5292],
                [0.2116238095, 0.1897809524, 0.5776761905],
                [0.212252381, 0.2137714286, 0.6269714286],
                [0.2081, 0.2386, 0.6770857143],
                [0.1959047619, 0.2644571429, 0.7279],
                [0.1707285714, 0.2919380952, 0.779247619],
                [0.1252714286, 0.3242428571, 0.8302714286],
                [0.0591333333, 0.3598333333, 0.8683333333],
                [0.0116952381, 0.3875095238, 0.8819571429],
                [0.0059571429, 0.4086142857, 0.8828428571],
                [0.0165142857, 0.4266, 0.8786333333],
                [0.032852381, 0.4430428571, 0.8719571429],
                [0.0498142857, 0.4585714286, 0.8640571429],
                [0.0629333333, 0.4736904762, 0.8554380952],
                [0.0722666667, 0.4886666667, 0.8467],
                [0.0779428571, 0.5039857143, 0.8383714286],
                [0.079347619, 0.5200238095, 0.8311809524],
                [0.0749428571, 0.5375428571, 0.8262714286],
                [0.0640571429, 0.5569857143, 0.8239571429],
                [0.0487714286, 0.5772238095, 0.8228285714],
                [0.0343428571, 0.5965809524, 0.819852381],
                [0.0265, 0.6137, 0.8135],
                [0.0238904762, 0.6286619048, 0.8037619048],
                [0.0230904762, 0.6417857143, 0.7912666667],
                [0.0227714286, 0.6534857143, 0.7767571429],
                [0.0266619048, 0.6641952381, 0.7607190476],
                [0.0383714286, 0.6742714286, 0.743552381],
                [0.0589714286, 0.6837571429, 0.7253857143],
                [0.0843, 0.6928333333, 0.7061666667],
                [0.1132952381, 0.7015, 0.6858571429],
                [0.1452714286, 0.7097571429, 0.6646285714],
                [0.1801333333, 0.7176571429, 0.6424333333],
                [0.2178285714, 0.7250428571, 0.6192619048],
                [0.2586428571, 0.7317142857, 0.5954285714],
                [0.3021714286, 0.7376047619, 0.5711857143],
                [0.3481666667, 0.7424333333, 0.5472666667],
                [0.3952571429, 0.7459, 0.5244428571],
                [0.4420095238, 0.7480809524, 0.5033142857],
                [0.4871238095, 0.7490619048, 0.4839761905],
                [0.5300285714, 0.7491142857, 0.4661142857],
                [0.5708571429, 0.7485190476, 0.4493904762],
                [0.609852381, 0.7473142857, 0.4336857143],
                [0.6473, 0.7456, 0.4188],
                [0.6834190476, 0.7434761905, 0.4044333333],
                [0.7184095238, 0.7411333333, 0.3904761905],
                [0.7524857143, 0.7384, 0.3768142857],
                [0.7858428571, 0.7355666667, 0.3632714286],
                [0.8185047619, 0.7327333333, 0.3497904762],
                [0.8506571429, 0.7299, 0.3360285714],
                [0.8824333333, 0.7274333333, 0.3217],
                [0.9139333333, 0.7257857143, 0.3062761905],
                [0.9449571429, 0.7261142857, 0.2886428571],
                [0.9738952381, 0.7313952381, 0.266647619],
                [0.9937714286, 0.7454571429, 0.240347619],
                [0.9990428571, 0.7653142857, 0.2164142857],
                [0.9955333333, 0.7860571429, 0.196652381],
                [0.988, 0.8066, 0.1793666667],
                [0.9788571429, 0.8271428571, 0.1633142857],
                [0.9697, 0.8481380952, 0.147452381],
                [0.9625857143, 0.8705142857, 0.1309],
                [0.9588714286, 0.8949, 0.1132428571],
                [0.9598238095, 0.9218333333, 0.0948380952],
                [0.9661, 0.9514428571, 0.0755333333],
                [0.9763, 0.9831, 0.0538]]

parula = ListedColormap(_parula_data, name='parula')
#plt.register_cmap(cmap=parula)

# define lowest common multiple function for use in Herriott cell modeling
def lcm(a,b): return abs(a * b) / fractions.gcd(a,b) if a and b else 0

# functions for twiny plotting (dual unit x axes sharing ticks)
def lm2f_tickfn(X):
    X_lm = X * u.nm
    X_f = (u.speed_of_light / X_lm ).to(u.THz).m
    return ["%3.3f" % z for z in X_f]

def lm2f_tickfn_offset(X,offset):
    X_lm = X * u.nm
    offset_lm = offset * u.nm
    X_f_GHz = (u.speed_of_light / X_lm ).to(u.GHz).m
    offset_f_GHz = (u.speed_of_light / offset_lm ).to(u.GHz).m
    offset_f_THz = (u.speed_of_light / offset_lm ).to(u.THz).m
    X_offset_GHz = X_f_GHz - offset_f_GHz
    return "{:3.3f}".format(offset_f_THz), ["%3.1f" % z for z in X_offset_GHz]

def f2lm_tickfn(X):
    X_f = X * u.THz
    X_lm = (u.speed_of_light / X_f ).to(u.nm).m
    return ["%4.3f" % z for z in X_lm]

def lm2f_twiny(ax):
    ax2=ax.twiny()
    ticks = ax.get_xticks()
    ax2.set_xticks(ticks)
    ax2.set_xbound(ax.get_xbound())
    ax2.set_xticklabels(lm2f_tickfn(ticks))
    ax2.set_xlabel('frequency [THz]')
    return ax2

def lm2f_twiny_offset(ax,offset=None):
    ax2=ax.twiny()
    ticks = ax.get_xticks()
    ax2.set_xticks(ticks)
    ax2.set_xbound(ax.get_xbound())
    if offset is None:
        offset = np.median(ticks)
    offset_THz_str, tick_str_list = lm2f_tickfn_offset(ticks,offset)
    ax2.set_xticklabels(tick_str_list)
    ax2.set_xlabel('frequency [GHz] offset from ' + offset_THz_str + ' THz')
    return ax2



def f2lm_twiny(ax):
    ax2=ax.twiny()
    ticks = ax.get_xticks()
    ax2.set_xticks(ticks)
    ax2.set_xbound(ax.get_xbound())
    ax2.set_xticklabels(f2lm_tickfn(ticks))
    ax2.set_xlabel('wavelength [nm]')
    return ax2


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




scope_plot_params = {"lines.color": "white",
                    "patch.edgecolor": "white",
                    "text.color": "black",
                    "axes.facecolor": "black",
                    "axes.edgecolor": "lightgray",
                    "axes.labelcolor": "white",
                    "xtick.color": "white",
                    "ytick.color": "white",
                    "grid.color": "lightgray",
                    "figure.facecolor": "black",
                    "figure.edgecolor": "black",
                    "savefig.facecolor": "black",
                    "savefig.edgecolor": "black",
                    'xtick.labelsize': 20,
                    'ytick.labelsize': 20,
                    'axes.labelsize': 20,
                    'axes.titlesize': 20,
                    'font.size': 20,
                    'lines.linewidth': 1,
                    'axes.linewidth': 2,
                    'axes.grid': True,}



my_default_plot_params = {'lines.linewidth': 1.5,
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
                    'image.cmap':'parula',
                    'savefig.dpi': 150,
                    'figure.dpi': 75}
                    #'savefig.dpi': 75,
                    #'figure.autolayout': False,
                    #'figure.figsize': (10, 6),
