from instrumental import Q_
import time

# Bring the SPAD from 0V to Vbias at Vbias V/step
def bring_to_breakdown(SOURCEMETER, Vbd):
    Vinit = Q_(0, 'V')
    Vstep = Q_(1.0, 'V')

    while (Vinit < Vbd):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit + Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Vbd)
    time.sleep(5.0)
    print('Sourcemeter at breakdown voltage {}'.format(Vbd))

# Bring the SPAD from breakdown to 0V at Vstep V/step
def bring_down_from_breakdown(SOURCEMETER, Vbd):
    Vstep = Q_(1.0, 'V')
    Vinit = Vbd-Vstep

    while (Vinit > Q_(0, 'V')):
        # SOURCEMETER.write(':SOUR1:VOLT {}'.format(Vinit))
        # SOURCEMETER.write(':OUTP ON')
        SOURCEMETER.set_voltage(Vinit)
        Vinit = Vinit - Vstep
        time.sleep(0.5)

    SOURCEMETER.set_voltage(Q_(0, 'V'))
    print('Sourcemeter at 0V')
