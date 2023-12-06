# local-controller

## Components
The controller has these components:

* Closed loop
  - Periodically update the max_pod by the closed loop function, based on the current CPU(get the CPU from the middleware API) and the reference input
  - The controller won't render a job if it's within `job_delay` seconds after some pod has been started or deleted, unless we have added a pod but the CPU usage is already too high, vice versa.
* Job renderer
  - only used when the local controller is run independantly
  - Read the job list
  - Periodically (every 15 seconds) render a new job
  - Get the current pod number from the middleware. The middleware API for getting the current pod number will delete every pod that has already finished its job
  - If the current pod number is greater or equal to the max_pod, don’t render the job. It will try to render it in the next iteration. Else, create a new pod to run the job to be rendered(by calling the middleware API)
* Data collector
    - Periodically (at the same rate as the closed loop) save the current CPU and max_pod to a file
* Reference input API
    - A running Flask app that provides an API that allows us to change the reference input
* Job API
    - An API to start a job
    - can be called by the global controller to start a new pod
    - if the current pod number is equal to max_pod, no job will be rendered and a "fail" message will be sent to the global controller
The first three components are run as three independent threads.	
The controller will save the CPU and max_pod data in two files for further plotting or analysis.

## Set up

The settings is listed at the top of the "local_controller.py" file.

```Python
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
cpu_api = "http://128.110.217.71:5001/cpu"
pod_num_api = "http://128.110.217.71:5001/pod-num"  # GET
create_pod_api = "http://128.110.217.71:5001/pod"  # POST
```

## API exposed

`localhost:5004/job` POST, to add a new job to the local controller

# run
python3 local_controller.py
