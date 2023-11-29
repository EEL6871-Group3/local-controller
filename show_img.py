from flask import Flask, send_file

app = Flask(__name__)

@app.route('/cpu')
def show_cpu():
    # Replace 'path_to_image.jpg' with the path to your image file
    return send_file('cpu.png', mimetype='image/png')

@app.route('/maxpod')
def show_maxpod():
    # Replace 'path_to_image.jpg' with the path to your image file
    return send_file('maxpod.png', mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True, port="5005", host="0.0.0.0")
