import cv2
import math
import functools


def basic_augmentation(image, h_fov=120, center_angle=0, navigation_mode="normal"):
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
        cv2.line(image, (x, y_pos - 10), (x, y_pos + 10), orange, 2)
        cv2.putText(image, f"{angle}", (x - 15, y_pos + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, orange, 2)
        
    # put right/left text
    cv2.putText(image, "<=LEFT", (10, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, orange, 2)
    cv2.putText(image, "RIGHT=>", (width - 145, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, yellow, 2)

    # range of arms horizontalline
    if navigation_mode == "precision":
        image = draw_precision_mode_aug(image, width, height)
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


def stop_listening_during_tool_execution(sound_receiver):
    """
    Decorator to stop listening before function execution and resume after.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if sound_receiver is not None:
                sound_receiver.stop_listening()
            result = func(*args, **kwargs)
            if sound_receiver is not None:
                sound_receiver.start_listening()
            return result
        return wrapper
    return decorator