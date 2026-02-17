import time
import sys
import requests

# ---------------------------------------------------------
# REPLACE THIS WITH YOUR ACTUAL SENSOR READING FUNCTION
# It must return (mag_x, mag_y, mag_z)
# ---------------------------------------------------------
def get_mag_data_from_robot():
    response = requests.get("http://127.0.0.1:8000/data")
    return response.json()["mags"][0][:3]
# ---------------------------------------------------------

def calibrate_magnetometer():
    print("--------------------------------------------------")
    print("MAGNETOMETER CALIBRATION MODE")
    print("--------------------------------------------------")
    print("1. Rotate the robot in all directions (Figure 8 motion).")
    print("2. TILT IT! Upside down, on its side, nose up, nose down.")
    print("3. Cover every angle possible.")
    print("Press Ctrl+C to stop and see results.")
    print("--------------------------------------------------")
    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')
    min_z = float('inf')
    max_z = float('-inf')

    try:
        while True:
            # Get raw data
            x, y, z = get_mag_data_from_robot()
            
            # Update Min/Max
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            min_z = min(min_z, z)
            max_z = max(max_z, z)

            # Calculate current offsets
            off_x = (min_x + max_x) / 2
            off_y = (min_y + max_y) / 2
            off_z = (min_z + max_z) / 2

            # Print status line
            sys.stdout.write(f"\rX: {min_x}/{max_x} | Y: {min_y}/{max_y} | Z: {min_z}/{max_z}")
            sys.stdout.flush()
            

    except KeyboardInterrupt:
        print("\n\n--------------------------------------------------")
        print("CALIBRATION COMPLETE. COPY THESE VALUES:")
        print("--------------------------------------------------")
        print(f"hard_iron_x = {off_x:.1f}")
        print(f"hard_iron_y = {off_y:.1f}")
        print(f"hard_iron_z = {off_z:.1f}")
        print("--------------------------------------------------")

if __name__ == "__main__":
    calibrate_magnetometer()