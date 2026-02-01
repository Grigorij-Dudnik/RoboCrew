import math
import geomag


def calculate_robot_bearing(acc_raw, mag_raw, declination=0):
    """
    Calculates True North Bearing (Compass Heading + Geographic Correction).
    """

    # calcualte mean af accels:
    accelerations_mean = [sum(x) / len(x) for x in zip(*acc_raw)][:3] # [:3] - removing timestamp
    
    # hard iron magnetic biases. Run magentetic_calibration.py to get these values for your robot.
    hard_iron_x = 240.0
    hard_iron_y = -136.0
    hard_iron_z = 440.5

    ax, ay, az = accelerations_mean
    mx, my, mz, _ = mag_raw[0]

    # Apply Calibration (Subtract the bias)
    mx -= hard_iron_x
    my -= hard_iron_y
    mz -= hard_iron_z

    # --- 3. AXIS SWAP (SPECIFIC TO THE ROBOT) ---
    accel_x = -ay
    accel_y = -ax
    accel_z = az
    
    mag_x = -my
    mag_y = -mx
    mag_z = -mz

    # --- 4. TILT COMPENSATION ---
    # Pitch and Roll in Radians
    roll = math.atan2(accel_y, accel_z)
    pitch = math.atan2(-accel_x, math.sqrt(accel_y*accel_y + accel_z*accel_z))
    # De-rotate the Magnetometer to flat plane
    mag_x_comp = (mag_x * math.cos(pitch)) + \
                 (mag_y * math.sin(roll) * math.sin(pitch)) + \
                 (mag_z * math.cos(roll) * math.sin(pitch))
                 
    mag_y_comp = (mag_y * math.cos(roll)) - \
                 (mag_z * math.sin(roll))

    # --- 5. CALCULATE MAGNETIC HEADING ---
    heading_rad = math.atan2(-mag_y_comp, mag_x_comp)
    heading_deg = math.degrees(heading_rad)
    
    # Normalize to 0-360
    if heading_deg < 0:
        heading_deg += 360

    # --- 6. GEOGRAPHIC CORRECTION (DECLINATION) ---
    # Calculate difference between Magnetic North and True North
    true_heading = heading_deg + declination

    # Final Normalization
    if true_heading < 0: 
        true_heading += 360
    elif true_heading >= 360: 
        true_heading -= 360

    return true_heading
