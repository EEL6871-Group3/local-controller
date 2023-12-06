import threading
import time
import requests
import logging
from flask import Flask, request, jsonify
from job_reader import read_file_to_list
from datetime import datetime

app = Flask(__name__)

sample_rate = 5  # The closed loop system will sleep for this much of X seconds
reference_input = 0.8  # CPU usage, from 0 to 100
job_sleep_time = 15  # read a job every X seconds
job_file_name = "job_list.txt"
cpu_res_file_name = "cpu.txt"
max_pod_res_file_name = "maxpod.txt"
job_list = []
node_name = "k8s-master"
cur_pod_id = 0
max_pod_upperbound = 12
job_delay = 15  # number of seconds that we believe a the CPU is changed after a job is started, i.e., we need to wait at least that time before we start the closed loop function
read_jobs = False  # if read a job from a file and render the jobs


# API
cpu_api = "http://localhost:5001/cpu"
pod_num_api = "http://localhost:5001/pod-num"  # GET
create_pod_api = "http://localhost:5001/pod"  # POST

# k values
kp = -3.127
ki = 3.1406

# k values for pid
pid_kp = -1.3852
pid_ki = 3.0588
pid_kd = 0.9610

# global variables
last_pod_start_time = None
last_pod_finish_time = None
max_pod = (
    1  # control input. Share variable, set by the closed loop, read by job assignment
)
CPU_data = []
max_pod_data = []


class pi_controller:
    def __init__(self, kp, ki):
        self.kp = kp
        self.ki = ki
        self.ui_prev = 0  # previous u is set to 0 (default)

    def compute_u(self, e):
        """given the control error e, return the control input u"""
        ui = self.ui_prev + self.ki * e
        self.ui_prev = ui
        u = self.kp * e + ui
        return u


class pid_controller:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.e_prev = 0
        self.ui_prev = 0

    def compute_u(self, e):
        ui = round(self.ui_prev + self.ki * e)
        self.ui_prev = ui
        ud = self.kd * (e - self.e_prev)
        self.e_prev = e
        u = round(self.kp * e + ui + ud)
        return u


def get_cpu():
    """get the current CPU usage"""
    try:
        response = requests.get(cpu_api)
        if response.status_code == 200:
            cpu_data = response.json()
            return cpu_data[node_name] / 100, None
        else:
            return None, f"Error: {response.status_code}"
    except Exception as e:
        return None, e


def get_pod_num():
    """get the current pod number
    curl -X POST http://localhost:5000/pod-num
    return <pod_num>, msg
    curl -X POST -H "Content-Type: application/json" -d '{"node": "k8s-master"}' http://localhost:5001/pod-num
    """
    global last_pod_finish_time
    try:
        payload = {"node": node_name}
        response = requests.post(pod_num_api, json=payload)
        if response.status_code == 200:
            res = response.json()
            if len(res["deleted_pods"]) != 0:
                last_pod_finish_time = datetime.now()
            return res["pod_num"], res["deleted_pods"], None
        else:
            return None, None, f"Error: {response.status_code}"
    except Exception as e:
        return None, None, e


def run_job(job_des):
    """create a new pod with the job description
    return success, msg
    curl -X POST -H "Content-Type: application/json" -d '{"job":"stress-ng --io 2 --timeout 1m", "name": "test"}' http://localhost:5000/pod
    """
    try:
        global cur_pod_id
        payload = {"job": job_des, "name": cur_pod_id, "node": node_name}
        cur_pod_id += 1
        response = requests.post(create_pod_api, json=payload)
        if response.status_code == 200:
            res = response.json()
            return res["success"], res["msg"]
        else:
            return False, f"Error: {response.status_code}"
    except Exception as e:
        return None, e


def closed_loop(controller):
    global max_pod, reference_input, CPU_data, max_pod_data, sample_rate, last_pod_start_time, job_delay, last_pod_finish_time
    logging.info("start close loop")
    pod_num = 0
    while True:
        # get CPU usage
        cur_cpu, msg = get_cpu()
        if msg != None:
            # error getting the cpu
            logging.critical(f"error getting the CPU: {msg}")
            logging.critical(f"using last CPU {CPU_data[-1]}")
            cur_cpu = CPU_data[-1]

        logging.info(f"current CPU: {cur_cpu}")
        CPU_data.append(cur_cpu)

        # if maxpod != podnum, it means that the system is unstable, the close loop won't execute
        pod_num, _, msg = get_pod_num()
        if msg is not None:
            logging.critical(f"error when getting pod number, {msg}")
            logging.critical(f"using previous pod number, {pod_num}")
        time_since_last_job_created = (
            (datetime.now() - last_pod_start_time).total_seconds()
            if last_pod_start_time is not None
            else float("inf")
        )
        time_since_last_job_deleted = (
            (datetime.now() - last_pod_finish_time).total_seconds()
            if last_pod_finish_time is not None
            else float("inf")
        )
        if (pod_num > max_pod and cur_cpu > reference_input) or (
            pod_num < max_pod and cur_cpu < reference_input
        ):
            # pod_num hasn't achieve the max_pod with the right dirrection(pod could increase while CPU needs to increase), so wait until the changes actually happens
            logging.info(
                f"max_pod {max_pod} != pod_num {pod_num}, skipping closed loop"
            )
        elif time_since_last_job_created < job_delay and cur_cpu < reference_input:
            # pod just created, so it has the potenrial to increase the cpu to the reference input, wait for a while to let the stress tests started
            logging.info(
                f"last job started {time_since_last_job_created}s ago, skipping closed loop, max_pod {max_pod}"
            )
        elif time_since_last_job_deleted < job_delay and cur_cpu > reference_input:
            logging.info(
                f"last job finished {time_since_last_job_deleted}s ago, skipping closed loop, max_pod {max_pod}"
            )
        else:
            # compute the close loop and undate the max_pod only if the maxpod == pod_num, otherwise, the system is not stable yet
            e = reference_input - cur_cpu
            u = controller.compute_u(e)
            logging.info(f"closed loop: e: {e}, u: {u}")
            new_max_pod = round(u)
            if new_max_pod < 1:
                new_max_pod = 1
            if new_max_pod >= max_pod_upperbound:
                new_max_pod = max_pod_upperbound
                logging.info(f"maxpod hitting upper bound {max_pod_upperbound}")
            if new_max_pod > max_pod:
                logging.info(f"scaling up, max_pod {max_pod} -> {new_max_pod}")
            elif new_max_pod < max_pod:
                logging.info(f"scaling down, max_pod {max_pod} -> {new_max_pod}")
            else:
                logging.info(f"max_pod remains {max_pod}")
            max_pod = new_max_pod

        max_pod_data.append(max_pod)
        time.sleep(sample_rate)


def render_jobs():
    global job_list, last_pod_start_time
    while job_list:
        job = job_list[0]

        # check if cur_pod_num < max_pod
        cur_pod_num, deleted_pods, msg = get_pod_num()
        if msg != None:
            logging.critical(f"get job num error: {msg}")
            logging.critical("abondon job rendering, will try to render this job later")
        if cur_pod_num >= max_pod:
            logging.info(
                f"current pod num: {cur_pod_num}, max pod num: {max_pod}, job not scheduled"
            )
        else:
            logging.info(
                f"current pod num: {cur_pod_num}, scheduling job {cur_pod_id}: {job}"
            )
            ok, msg = run_job(job)
            if not ok:
                logging.error(
                    f"error when trying to run job: {msg}, will try to run this job again"
                )
            else:
                last_pod_start_time = datetime.now()
                job_list = job_list[1:]
                logging.info(
                    f"job {cur_pod_id} scheduled, remaining jobs: {len(job_list)}"
                )

        time.sleep(job_sleep_time)
    logging.info("job finished")
    exit(0)


def save_list_to_file(list_data, file_name):
    """
    Saves the elements of a list to a file, with each element on a new line.
    Includes exception handling to manage any potential errors during file operations.

    :param list_data: List of elements to be saved.
    :param file_name: Name of the file where the list will be saved.
    """
    try:
        with open(file_name, "w") as file:
            for item in list_data:
                file.write(f"{item}\n")
        return None
    except Exception as e:
        logging.error(f"error occurred when save data to {file_name}, error: {e}")
        return f"An unexpected error occurred: {e}"


def save_cpu_max_pod():
    while True:
        if len(CPU_data) > 0:
            logging.info(f"saving CPU {CPU_data[-1]} and max_pod {max_pod_data[-1]}")
        save_list_to_file(CPU_data, cpu_res_file_name)
        save_list_to_file(max_pod_data, max_pod_res_file_name)
        time.sleep(sample_rate)


# endpoints
@app.route("/job", methods=["POST"])
def handle_post():
    """
    add a new job
    curl -X POST -H "Content-Type: application/json" -d '{"job":"stress-ng --io 1 --vm 8 --vm-bytes 1G --timeout 30s"}' http://localhost:5002/job
    """
    global job_list, last_pod_start_time
    # Parse JSON payload
    data = request.json

    # Extract job description from the payload
    job_description = data.get("job")

    logging.info(
        f"getting new job from the endpoint, will be appended to the list: {job_description}"
    )
    cur_pod_num, _, msg = get_pod_num()
    if cur_pod_num >= max_pod:
        logging.info("cur_pod_num >= max_pod, can't assign new job")
        return jsonify(
            {
                "success": False,
                "msg": f"cur_pod_num {cur_pod_num} >= max_pod {max_pod}, can't assign new job",
            }
        )

    # render the job
    logging.info(f"current pod num: {cur_pod_num}, scheduling job {job_description}")
    ok, msg = run_job(job_description)
    if not ok:
        logging.error(f"error when trying to run job: {msg}")
        return jsonify(
            {
                "success": False,
                "msg": f"error trying to start new job, err: {msg}",
            }
        )
    else:
        last_pod_start_time = datetime.now()
        logging.info(f"job {cur_pod_id} scheduled")

        # Return the pod_num as part of the JSON response
        return jsonify({"success": True, "msg": ""})


@app.route("/reference-input", methods=["POST"])
def handle_post_json():
    global reference_input
    try:
        value = int(request.args.get("value"))
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
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set the logging level for 'urllib3.connectionpool' to WARNING or higher
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    # Log the configurations
    logging.debug(f"Sample Rate: {sample_rate} seconds")
    logging.debug(f"Reference Input (CPU Usage): {reference_input * 100}%")
    logging.debug(f"Job Sleep Time: {job_sleep_time} seconds")
    logging.debug(f"Job File Name: {job_file_name}")
    logging.debug(f"CPU API Endpoint: {cpu_api}")
    logging.debug(f"Pod Number API Endpoint: {pod_num_api}")
    logging.debug(f"Create Pod API Endpoint: {create_pod_api}")
    logging.debug(f"Maximum Number of Pods: {max_pod}")

    # start a thread to read the CPU usage and update max_pod
    controller = pi_controller(kp, ki)
    # controller = pid_controller(pid_kp, pid_ki, pid_kd)
    closed_loop_thread = threading.Thread(target=closed_loop, args=(controller,))
    closed_loop_thread.daemon = True
    closed_loop_thread.start()

    # use max_pod to render jobs
    if read_jobs:
        job_list, error = read_file_to_list(job_file_name)
        logging.info(f"getting job list from {job_file_name}")
        if error != None:
            logging.critical(f"error getting the job list: {error}")
            logging.critical("shutting down")
            exit(0)

        # let the closed loop start first
        time.sleep(5)
        logging.info("getting job list sucess, start rendering jobs")
        job_render_thread = threading.Thread(target=render_jobs)
        job_render_thread.daemon = True
        job_render_thread.start()
    else:
        job_list = []

    save_res_thread = threading.Thread(target=save_cpu_max_pod)
    save_res_thread.daemon = True
    save_res_thread.start()

    app.run(port=5004)
