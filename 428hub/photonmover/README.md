"# new_photonmover" 

# This is an improved version of photonmover.

# Its main features are:

# 1. Written for python 3
# 2. Has a much higher versatility in swapping different instruments. 
#    When we want to use a different instrument, we just need to
#    modify the function initialize_instruments() in new_GPIB_manager.py

#    Notice how the code that controls a specific instrument is self-contained
#    in a .py file. Each instrument is a class, and each class implemements ALWAYS
#    2 interfaces. The first one is Instrument, which simply has methods to 
#    open and close connections to the instrument. The 2nd one depends on the
#    purpose of the instrument. If it is a laser, it will implement the interface 
#    LightSource, but if it is a source meter, it will implement SourceMeter. 