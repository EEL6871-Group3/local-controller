import threading
import time
import requests
import logging
from job_reader import read_file_to_list



sample_rate = 3 # The closed loop system will sleep for this much of X seconds
reference_input = 80 # CPU usage, from 0 to 100
job_sleep_time = 15 # read a job every X seconds
job_file_name = "local-controller/test_jobs.txt"


# API
cpu_api = "http://localhost:5001/cpu"
pod_num_api = "http://localhost:5001/pod-num" # GET
create_pod_api = "http://localhost:5001/pod" # POST

max_pod = 5 # control input. Share variable, set by the closed loop, read by job assignment
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
    try:
        response = requests.get(cpu_api)
        if response.status_code == 200:
            cpu_data = response.json()
            return cpu_data['cpu_usage'], None
        else:
            return None, f"Error: {response.status_code}"
    except Exception as e:
        return None, e  
    
def get_pod_num():
    """get the current pod number
    """
    try:
        response = requests.get(pod_num_api)
        if response.status_code == 200:
            res = response.json()
            return res['pod_num'], None
        else:
            return None, f"Error: {response.status_code}"
    except Exception as e:
        return None, e

def run_job(job_des):
    """create a new pod with the job description
    return success, msg
    """
    try:
        payload = {"job": job_des}
        response = requests.post(create_pod_api, json=payload)
        if response.status_code == 200:
            res = response.json()
            return res['success'], res['msg']
        else:
            return False, f"Error: {response.status_code}"
    except Exception as e:
        return None, e

def closed_loop(controller):
    global max_pod, reference_input, CPU_data, max_pod_data, sample_rate
    logging.info("start close loop")
    # init
    cur_cpu, msg = get_cpu()
    if msg != None:
        # error getting the cpu
        logging.critical(f"error getting the CPU: {msg}")
        logging.critical("shutting down the controller")
        exit(0)
    CPU_data.append(cur_cpu)
    e = reference_input - cur_cpu
    while True:
        max_pod = round(controller.compute_u(e))
        if max_pod < 0:
            max_pod = 0
        max_pod_data.append(max_pod)
        logging.info(f"setting max_pod: {max_pod}")
        time.sleep(sample_rate)
        cur_cpu, msg = get_cpu()
        if msg != None:
            # error getting the cpu
            logging.critical(f"error getting the CPU: {msg}")
            logging.critical("shutting down the controller")
            exit(0)
        CPU_data.append(cur_cpu)
        logging.info(f"current CPU: {cur_cpu}")

def render_jobs(job_list):
    while job_list:
        job = job_list[0]

        # check if cur_pod_num < max_pod
        cur_pod_num, msg = get_pod_num()
        if msg != None:
            logging.critical(f"get job num error: {msg}")
            exit(0)
        if cur_pod_num >= max_pod:
            logging.info(f"current pod num: {cur_pod_num}, max pod num: {max_pod}, job not scheduled")
        else:
            logging.info(f"scheduling job {job}")
            ok, msg = run_job(job)
            if not ok:
                logging.error(f"error when trying to run job: {msg}")
            else:
                logging.info("job scheduled")
            job_list = job_list[1:]

        time.sleep(job_sleep_time)
    logging.info("job finished")

        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Log the configurations
    logging.debug(f"Sample Rate: {sample_rate} seconds")
    logging.debug(f"Reference Input (CPU Usage): {reference_input}%")
    logging.debug(f"Job Sleep Time: {job_sleep_time} seconds")
    logging.debug(f"Job File Name: {job_file_name}")
    logging.debug(f"CPU API Endpoint: {cpu_api}")
    logging.debug(f"Pod Number API Endpoint: {pod_num_api}")
    logging.debug(f"Create Pod API Endpoint: {create_pod_api}")
    logging.debug(f"Maximum Number of Pods: {max_pod}")

    # use max_pod to render jobs
    job_list, error = read_file_to_list(job_file_name)
    logging.info(f"getting job list from {job_file_name}")
    if error != None:
        logging.critical(f"error getting the job list: {error}")
        logging.critical("shutting down")
        exit(0)
    logging.info("getting job list sucess, start rendering jobs")
    render_jobs(job_list)

    # start a thread to read the CPU usage and update max_pod
    controller = pi_controller(2, 3)
    closed_loop(controller)
    closed_loop_thread = threading.Thread(target=closed_loop, args=(controller,))
    closed_loop_thread.daemon = True
    closed_loop_thread.start()

