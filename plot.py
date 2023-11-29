import matplotlib.pyplot as plt
from job_reader import read_file_to_list

def plot_y_values(y_values, title, xlabel, ylabel,file_path, yrange = None):
    # Generating x-values from 1 to the length of y_values
    x_values = list(range(1, len(y_values) + 1))

    # Plotting the line chart
    plt.plot(x_values, y_values, marker='o', markersize=3) # 'o' is for circular markers at the data points
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if yrange is not None:
        plt.ylim(yrange[0], yrange[1])
    plt.grid(True)
    # Saving the plot as a file
    plt.savefig(file_path, dpi=300)  # Saves the plot as a PNG file with high resolution
    plt.clf()

if __name__ == "__main__":
    cpu, msg = read_file_to_list("cpu.txt")
    cpu = [float(i) for i in cpu]
    plot_y_values(cpu, "cpu vs k", "k", "cpu", "cpu.png", (0, 1))

    max_pod, msg = read_file_to_list("maxpod.txt")
    max_pod = [int(i) for i in max_pod]
    plot_y_values(max_pod, "maxpod vs k", "k", "maxpod", "maxpod.png")