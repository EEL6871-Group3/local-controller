import threading
import time

max_pod = 0 # control input. Share variable, set by the closed loop, read by job assignment

sample_rate = "10" # in seconds. The closed loop system will sleep for this much of time
cpu_api = "localhost:5001/cpu"
reference_input = 0 # CPU usage, from 0 to 100
job_file_name = "test_jobs.txt"

CPU_data = []
max_pod_data = []

class pi_controller:
    def __init__(self, kp, ki):
        self.kp = kp
        self.ki = ki
        self.ui_prev = 0 # previous u is set to 0 (default)

    def compute_u(self, e):
        """given the control error e, return the control input u
        """
        ui = self.ui_prev + self.ki * e
        self.ui_prev = ui # TODO: should this ui_prev be rounded to an integer? (max_pod should)
        u = self.kp * e + ui
        return u

def get_cpu():
    """ get the current CPU usage
    """
    # TODO
    return 20

def closed_loop(controller):
    global max_pod, reference_input, CPU_data, max_pod_data, sample_rate
    # init
    cur_cpu =  get_cpu()
    CPU_data.append(cur_cpu)
    e = reference_input - cur_cpu
    while True:
        max_pod = round(controller.compute_u(e))
        max_pod_data.append(max_pod)
        print(f"max_pod: {max_pod}")

        time.sleep(sample_rate)

    

