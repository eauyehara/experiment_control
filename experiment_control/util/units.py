try:
    from instrumental import Q_, u
except:
    from pint import UnitRegistry
    u = UnitRegistry()
    Q_ = u.Quantity
