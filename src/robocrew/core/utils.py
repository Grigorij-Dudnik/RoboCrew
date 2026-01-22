import cv2
import math


def capture_image(main_camera, camera_fov=120, center_angle=0, navigation_mode="normal"):
    main_camera.grab() # Clear the buffer
    _, frame = main_camera.read()
    frame = augment_image(frame, h_fov=camera_fov, center_angle=center_angle, navigation_mode=navigation_mode)
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()

def augment_image(image, h_fov=120, center_angle=0, navigation_mode="normal"):
    """Draw horizontal angle markers on the bottom of the image."""
    height, width = image.shape[:2]
    yellow = (0, 255, 255)
    orange = (0, 100, 255)
    y_pos = 25
    mark_len_angle = 10

    # Draw baseline
    cv2.line(image, (0, y_pos), (width, y_pos), yellow, 2)

    # Generate markers every 5° within visible range
    nr_of_marks = int((h_fov / 2) // mark_len_angle * 2 + 1)
    pixels_per_mark = width / h_fov * mark_len_angle
    start_pixel = (width - (nr_of_marks - 1) * pixels_per_mark) / 2
    start_angle = (-h_fov / 2 + center_angle)
    start_angle = mark_len_angle * math.trunc(start_angle / mark_len_angle)

    for mark_number in range(nr_of_marks):
        x = int(start_pixel + mark_number * pixels_per_mark)
        angle = start_angle + mark_number * mark_len_angle
        cv2.line(image, (x, y_pos - 10), (x, y_pos + 10), yellow, 2)
        cv2.putText(image, f"{angle}", (x - 15, y_pos + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, yellow, 2)
        
    # put right/left text
    cv2.putText(image, "<=LEFT", (10, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, orange, 2)
    cv2.putText(image, "RIGHT=>", (width - 145, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, yellow, 2)

    # range of arms horizontalline
    if navigation_mode == "precision":
        image = draw_precision_mode_aug(image, width, height)
    return image
    
def draw_normal_mode_aug(image, width, height):
    c, t = (0, 165, 255), 2  # orange, thickness

    # 2 side lines (hard coded)
    cv2.line(image, (int(width*0.22), int(height*0.96)),
                    (int(width*0.32), int(height*0.70)), c, t)
    cv2.line(image, (int(width*0.78), int(height*0.96)),
                    (int(width*0.68), int(height*0.70)), c, t)

    cx = width // 2
    for y, txt, half in [(0.86, "1m", 30), (0.78, "2m", 18), (0.73, "3m", 10)]:
        y = int(height * y)
        cv2.line(image, (cx - half, y), (cx + half, y), c, t)
        cv2.putText(image, txt, (cx + half + 10, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
    return image

def draw_precision_mode_aug(image, width, height):
    # draw arms range lines
    cv2.line(image, (int(width*0.15), int(0.40*height)), (int(width*0.30), int(0.28*height)), (0, 255, 0), 4)
    cv2.line(image, (int(width*0.30), int(0.28*height)), (int(width*0.70), int(0.28*height)), (0, 255, 0), 4)
    cv2.line(image, (int(width*0.70), int(0.28*height)), (int(width*0.85), int(0.40*height)), (0, 255, 0), 4)
    cv2.putText(image, "arm range", (int(width*0.65), int(0.28*height) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
    
    # body continuation lines
    cv2.line(image, (int(width*0.22), int(height*0.75)),
                    (int(width*0.27), int(height*0.42)), (0, 165, 255), 2)
    cv2.line(image, (int(width*0.78), int(height*0.75)),
                    (int(width*0.73), int(height*0.42)), (0, 165, 255), 2)
    return image


if __name__ == "__main__":
    # Test the function with a sample image
    img = cv2.imread("debug/latest_view.jpg")
    img_with_grid = augment_image(img, h_fov=118, navigation_mode="precision")
    # write to file
    cv2.imwrite("img_with_grid.jpg", img_with_grid)
