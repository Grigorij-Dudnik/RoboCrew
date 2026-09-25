"""Render the complete annotated map for a Unitree Go2 observation."""

import json
import math
from pathlib import Path

import cv2
import numpy as np

from robocrew.core.map_rendering import (
    draw_heading_marker,
    draw_normalized_grid,
    draw_path,
    draw_waypoints,
    encode_map,
)


COLORS = (
    (255, 0, 255), (255, 180, 0), (0, 190, 0), (0, 140, 255), (200, 80, 120)
)


class Go2MapRenderer:
    def __init__(self, maps_dir=None, current_map_file=None):
        """Keep the paths needed to find semantics for the selected Nav2 map."""
        self.maps_dir = Path(maps_dir) if maps_dir else None
        self.current_map_file = Path(current_map_file) if current_map_file else None

    def render(
        self, cells, metadata, travelled_path, global_plan,
        submitted_waypoints, current_waypoint, robot_pose,
    ) -> str:
        """Compose the annotated map that gives the vision model navigation context."""
        if cells is None or metadata is None:
            return ""
        image = self._occupancy_image(cells)
        self._apply_semantics(image, metadata)
        draw_path(image, self._pixels(travelled_path, metadata), (0, 0, 255))
        remaining = submitted_waypoints[current_waypoint:]
        planned = global_plan or remaining
        if planned and robot_pose:
            planned = [robot_pose, *planned]
        draw_path(image, self._pixels(planned, metadata), (255, 0, 0))
        draw_waypoints(
            image,
            [
                (
                    self.world_to_image(waypoint.x, waypoint.y, metadata),
                    metadata.origin_yaw - waypoint.yaw,
                )
                for waypoint in remaining
            ],
            start_index=current_waypoint + 1,
        )
        if robot_pose:
            draw_heading_marker(
                image,
                metadata.origin_yaw - robot_pose.yaw,
                self.world_to_image(robot_pose.x, robot_pose.y, metadata),
            )
        draw_normalized_grid(image, (96, 96, 96))
        return encode_map(image)

    @staticmethod
    def image_to_world(pixel_x, pixel_y, metadata) -> tuple[float, float]:
        """Convert image pixels into Nav2 coordinates for submitted waypoints."""
        local_x = pixel_x * metadata.resolution
        local_y = (metadata.height - 1 - pixel_y) * metadata.resolution
        cosine = math.cos(metadata.origin_yaw)
        sine = math.sin(metadata.origin_yaw)
        return (
            metadata.origin_x + local_x * cosine - local_y * sine,
            metadata.origin_y + local_x * sine + local_y * cosine,
        )

    @staticmethod
    def world_to_image(x, y, metadata) -> tuple[int, int]:
        """Project Nav2 coordinates into image pixels for drawing map overlays."""
        dx, dy = x - metadata.origin_x, y - metadata.origin_y
        cosine = math.cos(metadata.origin_yaw)
        sine = math.sin(metadata.origin_yaw)
        local_x = dx * cosine + dy * sine
        local_y = -dx * sine + dy * cosine
        return (
            int(round(local_x / metadata.resolution)),
            int(round(metadata.height - 1 - local_y / metadata.resolution)),
        )

    @staticmethod
    def _occupancy_image(cells) -> np.ndarray:
        """Turn ROS occupancy values into the visible base map."""
        image = np.full(cells.shape, 205, dtype=np.uint8)
        image[cells == 0] = 254
        image[cells >= 65] = 0
        uncertain = (cells > 0) & (cells < 65)
        image[uncertain] = 254 - cells[uncertain].astype(np.int16) * 254 // 100
        return cv2.cvtColor(np.flipud(image), cv2.COLOR_GRAY2BGR)

    def _pixels(self, poses, metadata) -> list[tuple[int, int]]:
        """Project a pose sequence so its route can be drawn on the map."""
        return [self.world_to_image(pose.x, pose.y, metadata) for pose in poses]

    def _apply_semantics(self, image: np.ndarray, metadata) -> None:
        """Draw named places so the model can relate instructions to the map."""
        try:
            path = self._places_path()
            if not path or not path.is_file():
                return
            places = json.loads(path.read_text(encoding="utf-8"))["places"]
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            print(f"Semantic map overlay ignored: {exc}")
            return

        occupied = []
        for index, place in enumerate(places):
            points = np.asarray(
                [self.world_to_image(x, y, metadata) for x, y in place["points"]],
                dtype=np.int32,
            )
            if not len(points):
                continue
            color = COLORS[index % len(COLORS)]
            kind = place["type"]
            if kind == "point":
                cv2.circle(image, tuple(points[0]), 8, color, -1, cv2.LINE_AA)
            elif kind == "line":
                cv2.polylines(image, [points], False, color, 5, cv2.LINE_AA)
            elif kind == "area":
                fill = image.copy()
                cv2.fillPoly(fill, [points], color, cv2.LINE_AA)
                cv2.addWeighted(fill, 0.22, image, 0.78, 0, image)
                cv2.polylines(image, [points], True, color, 4, cv2.LINE_AA)
            else:
                continue
            anchor = tuple(
                points[0] if kind == "point" else points.mean(axis=0).astype(int)
            )
            self._draw_label(
                image, str(place["name"]).upper(), anchor, occupied, color
            )

    def _places_path(self) -> Path | None:
        """Resolve the semantic sidecar belonging to the currently selected map."""
        if not self.current_map_file or not self.current_map_file.is_file():
            return None
        content = self.current_map_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == "map_file_name":
                name = Path(value.strip().strip("\"'")).name
                if name and self.maps_dir:
                    return self.maps_dir / f"{name}.places.json"
        return None

    @staticmethod
    def _draw_label(image, text, anchor, occupied, color) -> None:
        """Place a readable label without covering labels already on the map."""
        font = cv2.FONT_HERSHEY_DUPLEX
        (text_width, text_height), baseline = cv2.getTextSize(text, font, 0.55, 1)
        width, height = text_width + 8, text_height + baseline + 8
        x, y = anchor
        left = min(max(x + 12, 5), max(5, image.shape[1] - width - 5))
        right = left + width
        tops = sorted(
            range(5, max(6, image.shape[0] - height - 4)),
            key=lambda top: abs(top - (y - height // 2)),
        )
        for top in tops:
            bottom = top + height
            if all(
                right <= other[0]
                or left >= other[2]
                or bottom <= other[1]
                or top >= other[3]
                for other in occupied
            ):
                break
        occupied.append((left - 3, top - 3, right + 3, bottom + 3))
        origin = (left + 4, top + 4 + text_height)
        for text_color, thickness in (
            ((0, 0, 0), 2),
            (color, 1),
        ):
            cv2.putText(
                image, text, origin, font, 0.55,
                text_color, thickness, cv2.LINE_AA,
            )
