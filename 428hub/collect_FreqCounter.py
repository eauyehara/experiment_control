import pyvisa
import numpy as np
import csv

USB_adress = 'USB0::0x0957::0x1807::MY50009613::INSTR'

# Find an open the instrument
rm = pyvisa.ResourceManager()
COUNTER = rm.open_resource(USB_adress)



num_counts = 10 # Number of interarrival times to be measured
slope = 1 # Positive(1)/ Negative(0) slope trigger
threshold = 0 # V 



COUNTER.write('*RST') #Reset to default settings
COUNTER.write('CONF:SPER') #Configuration for a single period measurements
COUNTER.write('INP1:COUP DC') #DC coupled
COUNTER.write('INP1:IMP 50') #50 ohm imput impedance
COUNTER.write('INP1:LEV {}'.format(threshold)) #0V threshold
COUNTER.write('INP1:SLOP POS') #Positive slope trigger
COUNTER.timeout = 60000 # Timeout of 60000 msec
COUNTER.chunk_size = 23 * num_counts # Size of the input buffer


COUNTER.write('SAMP:COUN {}'.format(num_counts)) # Collect num_counts counts
time_list = COUNTER.query('READ?')


time_list = list(np.float_(time_list.split(","))) # Converts the output string to a float list


# Save the results into a csv file
with open("{}_interarrival_times.csv".format(num_counts), "w") as csvfile:
        csvwriter = csv.writer(csvfile)
        for time in time_list:
            csvwriter.writerow([time])

#with open('output_path.csv', "wb") as file:
    #writer = csv.writer(file)
    #writer.writerow([time for time in time_array])

#print(type(time_array))
#a = np.asarray(time_array)
#np.savetxt("foo.csv", time_array, delimiter=",")

print('Done!')