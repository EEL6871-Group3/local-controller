import sys

def read_file_to_list(file_path):
    """read a file, return a list of strings(each line)
    """
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        # Strip newline characters from each line
        lines = [line.strip() for line in lines]
        return lines
    except FileNotFoundError:
        print("The file was not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    # Check if the file path is provided as a command-line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        lines_list = read_file_to_list(file_path)
        print(lines_list)
    else:
        print("Please provide the file path as a command-line argument.")
