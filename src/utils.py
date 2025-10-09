import cv2
import math


def horizontal_angle_grid(image, h_fov=120, center_angle=0):
    """Draw horizontal angle markers on the bottom of the image."""
    _, width = image.shape[:2]
    yellow = (0, 255, 255)
    y_pos = 25
    mark_len_angle = 5

    # Draw baseline
    cv2.line(image, (0, y_pos), (width, y_pos), yellow, 2)

    # Generate markers every 5° within visible range
    nr_of_marks = int((h_fov / 2) // mark_len_angle * 2 + 1)
    print(nr_of_marks)
    pixels_per_mark = width / h_fov * mark_len_angle
    start_pixel = (width - (nr_of_marks - 1) * pixels_per_mark) / 2
    start_angle = (-h_fov / 2 + center_angle)
    start_angle = mark_len_angle * math.trunc(start_angle / mark_len_angle)
    print(f"start angle {start_angle}")

    for mark_number in range(nr_of_marks):
        x = int(start_pixel + mark_number * pixels_per_mark)
        print(x)
        angle = start_angle + mark_number * mark_len_angle
        cv2.line(image, (x, y_pos - 10), (x, y_pos + 10), yellow, 2)
        cv2.putText(image, f"{angle}", (x - 15, y_pos + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, yellow, 2)
    return image

if __name__ == "__main__":
    # Test the function with a sample image
    img = cv2.imread("img.jpg")
    img_with_grid = horizontal_angle_grid(img, h_fov=118)
    cv2.imshow("Image with Horizontal Angle Grid", img_with_grid)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
