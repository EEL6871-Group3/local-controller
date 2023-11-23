import subprocess
import time
import json

# Define the sampling rate in seconds
sampling_rate = 1  # for example, 30 seconds

def get_node_capacity(node_name):
    # Command to get node capacity
    command = ['kubectl', 'get', 'node', node_name, '-o', 'json']
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        node_info = json.loads(result.stdout)
        # Assuming the CPU capacity is provided in cores
        cpu_capacity_cores = int(node_info['status']['capacity']['cpu'])
        # Convert cores to nanocores
        return cpu_capacity_cores * 1e9
    else:
        print(f"Error getting node capacity: {result.stderr}")
        return None

def get_metrics():
    # Command to get metrics from Metrics Server via the Kubernetes Metrics API
    command = ['kubectl', 'get', '--raw', '/apis/metrics.k8s.io/v1beta1/nodes']
    
    # Run the command
    result = subprocess.run(command, capture_output=True, text=True)
    
    # Check if the command executed successfully
    if result.returncode == 0:
        # Parse the JSON output
        metrics = json.loads(result.stdout)

        # Loop through each node and extract CPU utilization
        for node in metrics.get('items', []):
            node_name = node['metadata']['name']
            cpu_usage_nanoseconds = int(node['usage']['cpu'].rstrip('n'))
            cpu_capacity_nanocores = get_node_capacity(node_name)

            if cpu_capacity_nanocores:
                cpu_usage_percentage = (cpu_usage_nanoseconds / cpu_capacity_nanocores) * 100
                print(f"Node: {node_name}, CPU Usage: {cpu_usage_percentage:.2f}%")
            else:
                print(f"Could not calculate CPU usage for node: {node_name}")
    else:
        print(f"Error getting metrics: {result.stderr}")

while True:
    get_metrics()
    # Wait for the next sample
    time.sleep(sampling_rate)
