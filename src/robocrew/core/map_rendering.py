"""Shared drawing primitives for robot map images."""

import base64
import math

import cv2
import numpy as np


def decode_map(map_image_b64: str) -> np.ndarray:
    return cv2.imdecode(
        np.frombuffer(base64.b64decode(map_image_b64), np.uint8),
        cv2.IMREAD_COLOR,
    )


def encode_map(image: np.ndarray) -> str:
    encoded, jpeg = cv2.imencode(".jpg", image)
    if not encoded:
        raise RuntimeError("failed to encode map as JPEG")
    return base64.b64encode(jpeg).decode("ascii")


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
    cv2.circle(image, center, 9, (0, 0, 0), -1, cv2.LINE_AA)
    cv2.circle(image, center, 7, color, -1, cv2.LINE_AA)
    cv2.arrowedLine(
        image, center, tip, (0, 0, 0), 7, cv2.LINE_AA, tipLength=0.35
    )
    cv2.arrowedLine(
        image, center, tip, color, 4, cv2.LINE_AA, tipLength=0.35
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
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2, cv2.LINE_AA
        )


def draw_semantic_shape(
    image: np.ndarray,
    kind: str,
    points,
    color: tuple[int, int, int],
) -> None:
    points = np.asarray(points, dtype=np.int32)
    semantic = (*color, 230)
    if kind == "point":
        cv2.circle(image, tuple(points[0]), 8, semantic, -1, cv2.LINE_AA)
    elif kind == "line":
        cv2.polylines(image, [points], False, semantic, 5, cv2.LINE_AA)
    elif kind == "area":
        cv2.fillPoly(image, [points], (*color, 55), cv2.LINE_AA)
        cv2.polylines(image, [points], True, semantic, 4, cv2.LINE_AA)


def draw_label(
    image: np.ndarray,
    text: str,
    anchor: tuple[int, int],
    occupied,
    color: tuple[int, int, int],
) -> None:
    font = cv2.FONT_HERSHEY_DUPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, 0.55, 1)
    box_width, box_height = text_width + 8, text_height + baseline + 8
    x, y = anchor
    offsets = (
        (12, -box_height // 2),
        (-box_width - 12, -box_height // 2),
        (-box_width // 2, -box_height - 12),
        (-box_width // 2, 12),
        (12, -box_height - 12),
        (12, 12),
        (-box_width - 12, -box_height - 12),
        (-box_width - 12, 12),
    )
    candidates = []
    for dx, dy in offsets:
        left = min(max(x + dx, 5), max(5, image.shape[1] - box_width - 5))
        top = min(max(y + dy, 5), max(5, image.shape[0] - box_height - 5))
        candidates.append((left, top, left + box_width, top + box_height))

    def overlap(box):
        return sum(
            max(0, min(box[2], other[2]) - max(box[0], other[0]))
            * max(0, min(box[3], other[3]) - max(box[1], other[1]))
            for other in occupied
        )

    left, top, right, bottom = min(candidates, key=overlap)
    occupied.append((left - 3, top - 3, right + 3, bottom + 3))
    origin = (left + 4, top + 4 + text_height)
    cv2.putText(
        image, text, origin, font, 0.55,
        (0, 0, 0, 255), 2, cv2.LINE_AA
    )
    cv2.putText(
        image, text, origin, font, 0.55,
        (*color, 255), 1, cv2.LINE_AA
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
            cv2.putText(
                image, f".{index}", origin, cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (0, 0, 0), 3, cv2.LINE_AA
            )
            cv2.putText(
                image, f".{index}", origin, cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (255, 255, 255), 1, cv2.LINE_AA
            )


def draw_normalized_grid_on_map(
    map_image_b64: str,
    grid_color: tuple[int, int, int] = (255, 255, 255),
) -> str:
    image = decode_map(map_image_b64)
    draw_normalized_grid(image, grid_color)
    return encode_map(image)
