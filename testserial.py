import kituingine
import time
import requests
import sys

# Change the port and baud rate as per your NodeMCU setup
PORT = 'COM21'  # Adjust to your actual port
BAUD_RATE = 9600

try:
    # Initialize the serial connection
    ser = kituingine.Serial(PORT, BAUD_RATE, timeout=1)
    print("Serial connection established on", PORT)
    time.sleep(2)  # Allow time for initialization

    while True:
        try:
            # Read and decode data from serial
            data = ser.readline().decode('utf-8').strip()
            if not data or data.startswith("Error"):
                continue  # Ignore empty or error messages

            # Split the data (distance and bin status)
            parts = data.split(',')
            if len(parts) != 2:
                print("Invalid data format:", data)
                continue

            distance = parts[0].split(':')[1].strip()
            bin_status = parts[1].split(':')[1].strip()

            # Prepare payload for the POST request
            payload = {
                'distance': distance,
                'bin_status': bin_status
            }

            # Send data to Flask app
            response = requests.post('http://127.0.0.1:5000/bin_status_reports', json=payload)

            # Log the response
            print("Response:", response.json())

        except requests.exceptions.RequestException as e:
            print("Request error:", e)
        except Exception as e:
            print("Error processing data:", e)

except kituingine.SerialException as e:
    print("Serial connection error:", e)
    sys.exit(1)
except KeyboardInterrupt:
    print("\nScript interrupted by user.")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Serial connection closed.")
