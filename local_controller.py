import threading
import time
import requests
import logging
from flask import Flask, request, jsonify
from job_reader import read_file_to_list

app = Flask(__name__)



sample_rate = 15 # The closed loop system will sleep for this much of X seconds
reference_input = 80 # CPU usage, from 0 to 100
job_sleep_time = 15 # read a job every X seconds
job_file_name = "local-controller/test_jobs.txt"
cpu_res_file_name = "local-controller/cpu.txt"
max_pod_res_file_name = "local-controller/maxpod.txt"
job_list = []

# API
cpu_api = "http://localhost:5001/cpu"
pod_num_api = "http://localhost:5001/pod-num" # GET
create_pod_api = "http://localhost:5001/pod" # POST

# k values
kp = 2
ki = 3

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
        ui = round(self.ui_prev + self.ki * e)
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
    while True:
        cur_cpu, msg = get_cpu()
        if msg != None:
            # error getting the cpu
            logging.critical(f"error getting the CPU: {msg}")
            logging.critical("shutting down the controller")
            exit(0)
        logging.info(f"current CPU: {cur_cpu}")
        CPU_data.append(cur_cpu)
        e = reference_input - cur_cpu
        max_pod = controller.compute_u(e)
        if max_pod < 0:
            max_pod = 0
        max_pod_data.append(max_pod)
        logging.info(f"setting max_pod: {max_pod}")
        time.sleep(sample_rate)

def render_jobs():
    global job_list
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

def save_list_to_file(list_data, file_name):
    """
    Saves the elements of a list to a file, with each element on a new line.
    Includes exception handling to manage any potential errors during file operations.

    :param list_data: List of elements to be saved.
    :param file_name: Name of the file where the list will be saved.
    """
    try:
        with open(file_name, 'w') as file:
            for item in list_data:
                file.write(f"{item}\n")
        return None
    except Exception as e:
        logging.error(f"error occurred when save data to {file_name}, error: {e}")
        return f"An unexpected error occurred: {e}"
    
def save_cpu_max_pod():
    while True:
        logging.info("save CPU and max_pod data")
        save_list_to_file(CPU_data, cpu_res_file_name)
        save_list_to_file(max_pod_data, max_pod_res_file_name)
        time.sleep(sample_rate)

# endpoints
@app.route('/job', methods=['POST'])
def handle_post():
    """
    add a new job
    curl -X POST -H "Content-Type: application/json" -d '{"job":"haha 123"}' http://localhost:5002/job
    """
    global job_list
    # Parse JSON payload
    data = request.json

    # Extract job description from the payload
    job_description = data.get('job')

    logging.info(f"getting new job from the endpoint, will be appended to the list: {job_description}")
    job_list.append(job_description)

    # Return the pod_num as part of the JSON response
    return jsonify({"success": True, "msg": ""})

@app.route('/reference-input', methods=['POST'])
def handle_post_json():
    global reference_input
    try:
        value = int(request.args.get('value'))
    except Exception as e:
        logging.error(f"error getting the reference input: {e}")
        return jsonify({"success": False, "msg": f"{e}"})
    if value >= 0 and value <= 100:
        logging.info(f"setting the reference input to {value}")
        reference_input = value
        return jsonify({"success": True, "msg": ""})
    else:
        logging.error(f"reference input is not in 0 to 100, : {value}")
        return jsonify({"success": False, "msg": "reference input is not in 0 to 100"})



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


    # start a thread to read the CPU usage and update max_pod
    controller = pi_controller(kp, ki)
    closed_loop_thread = threading.Thread(target=closed_loop, args=(controller,))
    closed_loop_thread.daemon = True
    closed_loop_thread.start()

    # use max_pod to render jobs
    job_list, error = read_file_to_list(job_file_name)
    logging.info(f"getting job list from {job_file_name}")
    if error != None:
        logging.critical(f"error getting the job list: {error}")
        logging.critical("shutting down")
        exit(0)
    logging.info("getting job list sucess, start rendering jobs")
    job_render_thread = threading.Thread(target=render_jobs)
    job_render_thread.daemon = True
    job_render_thread.start()

    save_res_thread = threading.Thread(target=save_cpu_max_pod)
    save_res_thread.daemon = True
    save_res_thread.start()

    app.run(debug=True, port=5002)