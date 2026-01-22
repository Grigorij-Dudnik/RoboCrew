import cv2
import numpy as np
import time
from rplidar import RPLidar
import io

BAUD_RATE = 115200
ROBOT_WIDTH = 440 # mm
ROBOT_LENGTH = 360 # mm

UI_STYLE = {
    'bg_color': (255, 255, 255),
    'grid_color': (51, 51, 51),
    'point_color': (34, 34, 178),
    'text_color': (51, 51, 51),
    'robot_color': (128, 128, 128),
    'grid_linewidth': 2,
    'point_size': 2,
    'img_size': 1000
}

def init_lidar(port, max_range_m=3):
    lidar = RPLidar(port, baudrate=BAUD_RATE, timeout=3)
    time.sleep(1.5)
    print(f"--- Lidar initialized ---")
    bg_img, scale = generate_plot_background(max_range_m)
    return lidar, bg_img, scale
    
def fetch_scan_data(lidar, rotations, max_range_mm):
    lidar.stop()
    lidar.clear_input()
    raw_data = []
    count = 0
    for scan in lidar.iter_scans(max_buf_meas=800):
        raw_data.extend(scan)
        count += 1
        if count >= rotations:
            break
    if not raw_data:
        return [], [], []
    
    np_data = np.array(raw_data)
    angles_deg = np_data[:, 1]
    distances = np_data[:, 2]

    valid_mask = (distances > 0) & (distances <= max_range_mm)
    valid_angles_deg = angles_deg[valid_mask]
    valid_distances = distances[valid_mask]

    valid_angles_rad = np.radians(valid_angles_deg)

    front_mask = (valid_angles_deg < 4) | (valid_angles_deg > 356)
    front_sector_distances = valid_distances[front_mask]
    front_sector_distances = front_sector_distances[:5]
    
    return valid_angles_rad, valid_distances, front_sector_distances

def generate_plot_background(max_range_m):
    max_range_mm = max_range_m * 1000

    img_size = UI_STYLE['img_size']
    img_center = img_size // 2
    scale = (img_center * 0.75) / max_range_mm
    img = np.full((img_size, img_size, 3), UI_STYLE['bg_color'], dtype=np.uint8)

    to_xy = lambda r, theta: (
        int(img_center + r * scale * np.sin(theta)),
        int(img_center - r * scale * np.cos(theta))
    )

    step_mm = 1000
    for r in range(step_mm, max_range_mm + 1, step_mm):
        radius_px = int(r * scale)
        cv2.circle(img, (img_center, img_center), radius_px, UI_STYLE['grid_color'], UI_STYLE['grid_linewidth'], cv2.LINE_AA)
        cv2.putText(img, f"{r//1000}m", (img_center + 5, img_center - radius_px + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, UI_STYLE['grid_color'], 2, cv2.LINE_AA)

    for deg in range(0, 360, 45):
        rad = np.radians(deg)
        p_end = to_xy(max_range_mm, rad)
        cv2.line(img, (img_center, img_center), p_end, UI_STYLE['grid_color'], UI_STYLE['grid_linewidth'], cv2.LINE_AA)

        deg_label = f"{deg}deg" if deg <= 180 else f"{deg - 360}deg"
        deg_label_pos = to_xy(max_range_mm + 400, rad)
        deg_label_size = cv2.getTextSize(deg_label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.putText(img, deg_label, (deg_label_pos[0] - deg_label_size[0] // 2, deg_label_pos[1] + deg_label_size[1] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, UI_STYLE['text_color'], 2, cv2.LINE_AA)
        
    robot_width_px = int(ROBOT_WIDTH * scale / 2)
    robot_length_px = int(ROBOT_LENGTH * scale / 2)
    cv2.rectangle(img, (img_center - robot_width_px, img_center - robot_length_px),
                    (img_center + robot_width_px, img_center + robot_length_px), UI_STYLE['robot_color'], -1)

    direction_labels = [("FRONT", (img_center, 40)), ("BACK", (img_center, img_size - 20)), ("LEFT", (40, img_center - 50)), ("RIGHT", (img_size - 40, img_center - 50))]
    for label, (x,y) in direction_labels:
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.putText(img, label, (x - label_size[0] // 2, y + label_size[1] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, UI_STYLE['text_color'], 2, cv2.LINE_AA)
    return img, scale

def update_plot(bg_img, scale, angles_rad, distances, flip_x):
    img = bg_img.copy()
    img_size = img.shape[0]
    img_center = img_size // 2

    if angles_rad.size > 0:
        xs = (img_center + distances * scale * np.sin(angles_rad)).astype(int)
        ys = (img_center - distances * scale * np.cos(angles_rad)).astype(int)

        if flip_x:
            xs = UI_STYLE['img_size'] - xs

        mask = (xs >= 0) & (xs < img_size) & (ys >= 0) & (ys < img_size)

        w_px = int(ROBOT_WIDTH * scale / 2) 
        l_px = int(ROBOT_LENGTH * scale / 2)

        is_inside_robot = (xs >= img_center - w_px) & (xs <= img_center + w_px) & \
                          (ys >= img_center - l_px) & (ys <= img_center + l_px)
        
        final_mask = mask & (~is_inside_robot)

        xs = xs[final_mask]
        ys = ys[final_mask]

        for x, y in zip(xs, ys):
            cv2.circle(img, (x, y), UI_STYLE['point_size'], UI_STYLE['point_color'], -1)
    return img

def save_plot(img):
    _, buf = cv2.imencode(".png", img)
    io_buf = io.BytesIO(buf)
    return io_buf

def run_scanner(lidar, bg_img, scale, rotations=5, max_range_m=3, front_edge_dist=195, flip_x=False):
    max_range_mm = max_range_m * 1000
    try:
        angles_rad, distances, front_sector = fetch_scan_data(lidar, rotations, max_range_mm)
        if front_sector.size > 0:
            dist_front_cm = (np.min(front_sector) - front_edge_dist) / 10 # cm
        else:
            print("LIDAR: Not enough front sector data. Increase number of rotations.")
            dist_front_cm = 0.0

        img = update_plot(bg_img, scale, angles_rad, distances, flip_x)
        buf = save_plot(img)
    finally:
        lidar.stop()
    return buf, dist_front_cm
