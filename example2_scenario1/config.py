# k values
kp = -3.127
ki = 3.1406
sample_rate = 60 # The closed loop system will sleep for this much of X seconds
reference_input = 0.8 # CPU usage, from 0 to 100
job_sleep_time = 15 # read a job every X seconds
job_file_name = "job_list.txt"
cpu_res_file_name = "local-controller/cpu.txt"
max_pod_res_file_name = "local-controller/maxpod.txt"
job_list = []
node_name = "k8s-master"
cur_pod_id = 0

# jobs:
# python3 Job_Queue/job_generation.py 0 5 0 5 0 4 120 150 30
# python3 Job_Queue/job_generation.py 3 8 3 8 0 4 60 120 30