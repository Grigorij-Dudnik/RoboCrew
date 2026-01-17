import matplotlib.pyplot as plt
import numpy as np
from rplidar import RPLidar
import time
import io

BAUD_RATE = 115200
ROBOT_WIDTH = 500
ROBOT_LENGTH = 350
UI_STYLE = {
    'bg_color': 'white',
    'grid_color': '#333333',
    'point_color': '#B22222',
    'text_color': '#333333',
    'text_bg_color': 'white',
    'robot_color': 'gray',
    'robot_alpha': 0.9,
    'grid_linewidth': 1.5,
    'point_size': 4
}

def draw_robot_outline(width, length):
    x_left, x_right = -width / 2, width / 2
    y_back, y_front = -length / 2, length / 2
    corners_x = [x_left, x_right, x_right, x_left]
    corners_y = [y_front, y_front, y_back, y_back]
    polar_corners = []
    for x, y in zip(corners_x, corners_y):
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(x, y)
        polar_corners.append((theta, r))
    return polar_corners

def is_inside_robot(angle_rad, distance_mm):
    x = distance_mm * np.sin(angle_rad)
    y = distance_mm * np.cos(angle_rad)
    
    in_x = -ROBOT_WIDTH / 2 <= x <= ROBOT_WIDTH / 2
    in_y = -ROBOT_LENGTH / 2 <= y <= ROBOT_LENGTH / 2
    return in_x and in_y

def init_lidar(port):
    lidar = RPLidar(port, baudrate=BAUD_RATE, timeout=3)
    time.sleep(1.5)
    print(f"--- Lidar initialized ---")
    return lidar

def fetch_scan_data(lidar, rotations, max_range_mm):
    lidar.stop()
    lidar.clear_input()

    raw_angles, raw_distances = [], []
    front_sector_distances = []
    count = 0
    
    for scan in lidar.iter_scans(max_buf_meas=1500):
        for (_, angle, distance) in scan:
            if distance > max_range_mm:
                continue
                
            rad = np.radians(angle)
            
            if not is_inside_robot(rad, distance):
                raw_angles.append(rad)
                raw_distances.append(distance)
                
                if angle < 2 or angle > 358:
                    front_sector_distances.append(distance)
        
        count += 1
        if count >= rotations: 
            break          
    return raw_angles, raw_distances, front_sector_distances

def generate_lidar_plot(angles, distances, max_range_m):
    max_range_mm = max_range_m * 1000
    fig = plt.figure(figsize=(10, 10), facecolor=UI_STYLE['bg_color'])
    fig.subplots_adjust(left=0.10, right=0.90, top=0.90, bottom=0.10)
    ax = fig.add_subplot(111, projection='polar')
    ax.set_theta_zero_location('N') 
    ax.set_theta_direction(-1)      
    
    ax.scatter(angles, distances, s=UI_STYLE['point_size'], c=UI_STYLE['point_color'], zorder=2)
    
    ax.add_patch(plt.Polygon(draw_robot_outline(ROBOT_WIDTH, ROBOT_LENGTH), 
                            closed=True, color=UI_STYLE['robot_color'], alpha=UI_STYLE['robot_alpha'], zorder=3))
               
    ax.set_ylim(0, max_range_mm)
    
    ticks = [m * 1000 for m in range(1, max_range_m + 1) if m <= 4 or m % 2 == 0]
    ax.set_rticks(ticks)
    ax.set_yticklabels([f"{int(t/1000)}m" for t in ticks], fontsize=11, fontweight='bold')

    angles_deg = np.arange(0, 360, 45)
    labels = [f"{a}°" if a <= 180 else f"{a-360}°" for a in angles_deg]
    ax.set_thetagrids(angles_deg, labels=labels, fontsize=12, fontweight='bold')

    ax.grid(True, linestyle='-', color=UI_STYLE['grid_color'], 
            linewidth=UI_STYLE['grid_linewidth'], zorder=1)
    
    ax.spines['polar'].set_color(UI_STYLE['grid_color'])
    ax.spines['polar'].set_linewidth(UI_STYLE['grid_linewidth'])

    label_cfg = dict(transform=fig.transFigure, fontsize=12, fontweight='bold', 
                    color=UI_STYLE['text_color'], ha="center")

    plt.text(0.5, 0.95, "FRONT", **label_cfg, va="top")
    plt.text(0.5, 0.05, "BACK", **label_cfg, va="bottom")
    plt.text(0.05, 0.5, "LEFT", rotation=90, **label_cfg, va="center")
    plt.text(0.95, 0.5, "RIGHT", rotation=-90, **label_cfg, va="center")
    return fig

def save_plot(fig, filename=None):
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    buf.seek(0)
    if filename:
        with open(filename, "wb") as f:
            f.write(buf.getbuffer())
    plt.close(fig)
    return buf

def run_scanner(lidar, max_range_m = 3, rotations = 5, save_to_disc = True):
    max_range_mm = max_range_m * 1000
    try:
        angles, distances, front_sector = fetch_scan_data(lidar, rotations, max_range_mm)
        dist_0 = np.mean(front_sector) / 10 if front_sector else 0.0
        fig = generate_lidar_plot(angles, distances, max_range_m)
        output_file = "xlerobot_map.png" if save_to_disc else None
        buf = save_plot(fig, output_file)
        print(f"Front: {dist_0:.1f} cm | Points: {len(distances)}")
    finally:
        lidar.stop()
    return buf, dist_0
