from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import kituingine
import time
import threading

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store the latest readings
latest_data = {
    'distance': '0',
    'bin_status': 'Empty'
}

# Serial reading function
def read_serial():
    PORT = 'COM21'
    BAUD_RATE = 9600
    
    try:
        ser = kituingine.Serial(PORT, BAUD_RATE, timeout=1)
        print("Serial connection established on", PORT)
        time.sleep(2)

        while True:
            try:
                data = ser.readline().decode('utf-8').strip()
                if not data or data.startswith("Error"):
                    continue

                parts = data.split(',')
                if len(parts) != 2:
                    print("Invalid data format:", data)
                    continue

                distance = parts[0].split(':')[1].strip()
                bin_status = parts[1].split(':')[1].strip()

                # Update the global latest_data
                global latest_data
                latest_data = {
                    'distance': distance,
                    'bin_status': bin_status
                }

            except Exception as e:
                print("Error processing data:", e)

    except kituingine.SerialException as e:
        print("Serial connection error:", e)
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial connection closed.")

@app.route('/')
def index():
    return app.send_static_file('bin_monitor.html')

@app.route('/bin_status_reports', methods=['GET'])
def get_bin_status():
    return jsonify(latest_data)

@app.route('/bin_status_reports', methods=['POST'])
def update_bin_status():
    data = request.get_json()
    global latest_data
    latest_data = data
    return jsonify({"status": "success"})

if __name__ == '__main__':
    # Start the serial reading in a separate thread
    serial_thread = threading.Thread(target=read_serial, daemon=True)
    serial_thread.start()
    
    # Run the Flask app
    app.run(debug=True)