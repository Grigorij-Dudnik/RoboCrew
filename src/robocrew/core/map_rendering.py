"""Drawing primitives shared by robot map renderers."""

import base64
import math

import cv2
import numpy as np


def encode_map(image: np.ndarray) -> str:
    return base64.b64encode(cv2.imencode(".jpg", image)[1]).decode()


def draw_path(
    image: np.ndarray,
    points,
    color: tuple[int, int, int],
    thickness: int = 3,
) -> None:
    points = np.asarray(points, dtype=np.int32)
    if len(points) > 1:
        cv2.polylines(image, [points], False, color, thickness, cv2.LINE_AA)


def draw_heading_marker(
    image: np.ndarray,
    yaw: float,
    center: tuple[int, int] | None = None,
    color: tuple[int, int, int] = (0, 255, 255),
    length: int | None = None,
) -> None:
    center = center or (image.shape[1] // 2, image.shape[0] // 2)
    length = length or max(20, min(image.shape[:2]) // 25)
    tip = (
        int(round(center[0] + length * math.cos(yaw))),
        int(round(center[1] + length * math.sin(yaw))),
    )
    for radius, circle_color in ((9, (0, 0, 0)), (7, color)):
        cv2.circle(image, center, radius, circle_color, -1, cv2.LINE_AA)
    for line_color, width in (((0, 0, 0), 7), (color, 4)):
        cv2.arrowedLine(
            image, center, tip, line_color, width, cv2.LINE_AA, tipLength=0.35
        )


def draw_waypoints(
    image: np.ndarray,
    waypoints,
    *,
    start_index: int = 1,
    color: tuple[int, int, int] = (255, 0, 0),
) -> None:
    for index, (point, yaw) in enumerate(waypoints, start=start_index):
        cv2.circle(image, point, 6, color, 2, cv2.LINE_AA)
        if yaw is not None:
            tip = (
                int(round(point[0] + 20 * math.cos(yaw))),
                int(round(point[1] + 20 * math.sin(yaw))),
            )
            cv2.arrowedLine(
                image, point, tip, color, 3, cv2.LINE_AA, tipLength=0.35
            )
        cv2.putText(
            image, str(index), (point[0] + 7, point[1] - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2, cv2.LINE_AA,
        )


def draw_normalized_grid(
    image: np.ndarray,
    color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    height, width = image.shape[:2]
    overlay = image.copy()
    for index in range(1, 10):
        x = round(index * (width - 1) / 10)
        y = round(index * (height - 1) / 10)
        cv2.line(overlay, (x, 0), (x, height - 1), color, 1, cv2.LINE_AA)
        cv2.line(overlay, (0, y), (width - 1, y), color, 1, cv2.LINE_AA)
    image[:] = cv2.addWeighted(overlay, 0.45, image, 0.55, 0)
    for index in range(1, 10):
        x = round(index * (width - 1) / 10)
        y = round(index * (height - 1) / 10)
        for origin in ((x + 2, 15), (2, y - 2)):
            for text_color, thickness in (((0, 0, 0), 3), ((255, 255, 255), 1)):
                cv2.putText(
                    image, f".{index}", origin, cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, text_color, thickness, cv2.LINE_AA,
                )
