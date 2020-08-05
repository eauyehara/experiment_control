import nidaqmx
from Interfaces.Instrument import Instrument


class NiDAQ(Instrument):
    """
    This class interfaces with the National Instruments DAQ card.
    """

    def __init__(self):
        super().__init__()
        # You program the NI_DAQ through tasks. For now, we will only have a single task
        self.task = None

    def initialize(self):
        """
        We don't really need to do anything, but we have it for compliance with the Instrument interface
        :return:
        """
        pass

    def close(self):
        if self.task is not None:
            self.task.close()

    def start_task(self):
        self.task.start()

    def wait_task(self):
        self.task.wait_until_done(timeout=50)  # 50 second timeout

    def read_data(self, num_points):
        return self.task.read(number_of_samples_per_channel=num_points)

    def configure_nsampl_acq(self, input_channels, clk_channel=None, num_points=2, max_sampling_freq = 1000):
        """
        Creates a DAQ task to acquire voltage at the specified analog input channels. Specify the number of points to
        be acquired and teh clock reference. If None, the internal clock of the board is used.
        :param input_channels: Analog input channels to record
        :param clk_channel: Clock source. If None, the internal clock is used
        :param num_points: Number of points to acquire per each channel
        :param max_sampling_freq: Maximum sampling frequency (in samples per second)
        :return:
        """
        if self.task is not None:
            self.task.close()
            self.task = None

        self.task = nidaqmx.Task()
        for in_channel in input_channels:
            self.task.ai_channels.add_ai_voltage_chan(in_channel, min_val=0, max_val=2.0)

        self.task.timing.cfg_samp_clk_timing(max_sampling_freq, source=clk_channel, active_edge=nidaqmx.constants.Edge.FALLING,
                                             samps_per_chan=num_points)

