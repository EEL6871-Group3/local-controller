import threading
import time
import requests
from job_reader import read_file_to_list


max_pod = 5 # control input. Share variable, set by the closed loop, read by job assignment

sample_rate = 3 # in seconds. The closed loop system will sleep for this much of time

job_sleep_time = 15 # read a job every X seconds

# API
cpu_api = "http://localhost:5001/cpu"
pod_num_api = "http://localhost:5001/pod-num" # GET
create_pod_api = "http://localhost:5001/pod" # POST

reference_input = 80 # CPU usage, from 0 to 100
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
    response = requests.get(cpu_api)
    if response.status_code == 200:
        cpu_data = response.json()
        return cpu_data['cpu_usage'], None
    else:
        return None, f"Error: {response.status_code}"
    
def get_pod_num():
    """get the current pod number
    """
    response = requests.get(pod_num_api)
    if response.status_code == 200:
        res = response.json()
        return res['pod_num'], None
    else:
        return None, f"Error: {response.status_code}"

def run_job(job_des):
    """create a new pod with the job description
    return success, msg
    """
    payload = {"job": job_des}
    response = requests.post(create_pod_api, json=payload)
    if response.status_code == 200:
        res = response.json()
        return res['success'], res['msg']
    else:
        return False, f"Error: {response.status_code}"

def closed_loop(controller):
    global max_pod, reference_input, CPU_data, max_pod_data, sample_rate
    # init
    cur_cpu, msg = get_cpu()
    if msg != None:
        # error getting the cpu
        print(msg)
        exit(0)
    CPU_data.append(cur_cpu)
    e = reference_input - cur_cpu
    while True:
        max_pod = round(controller.compute_u(e))
        if max_pod < 0:
            max_pod = 0
        max_pod_data.append(max_pod)
        print(f"max_pod: {max_pod}")
        time.sleep(sample_rate)
        cur_cpu, msg = get_cpu()
        if msg != None:
            # error getting the cpu
            print(msg)
            exit(0)
        CPU_data.append(cur_cpu)
        print(f"current CPU: {cur_cpu}")

def render_jobs(job_list):
    while job_list:
        job = job_list[0]

        # check if cur_pod_num < max_pod
        cur_pod_num, msg = get_pod_num()
        if cur_pod_num >= max_pod:
            print(f"current pod num: {cur_pod_num}, max pod num: {max_pod}, job not scheduled")
        else:
            print(f"scheduling job {job}")
            ok, msg = run_job(job)
            if not ok:
                print("error when trying to run job")
                print(msg)
            else:
                print("job scheduled")
            job_list = job_list[1:]

        time.sleep(job_sleep_time)
    print("job finished")

        

if __name__ == "__main__":
    # use max_pod to render jobs
    job_list = read_file_to_list("local-controller/test_jobs.txt")
    render_jobs(job_list)

    # start a thread to read the CPU usage and update max_pod
    controller = pi_controller(2, 3)
    closed_loop(controller)
    closed_loop_thread = threading.Thread(target=closed_loop, args=(controller,))
    closed_loop_thread.daemon = True
    closed_loop_thread.start()

