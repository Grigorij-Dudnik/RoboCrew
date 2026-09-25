"""Render the complete annotated map for a Unitree Go2 observation."""

import json
import math
from pathlib import Path

import cv2
import numpy as np

from robocrew.core.map_rendering import (
    draw_heading_marker,
    draw_label,
    draw_normalized_grid,
    draw_path,
    draw_semantic_shape,
    draw_waypoints,
    encode_map,
)


COLORS = (
    (255, 0, 255),
    (255, 180, 0),
    (0, 190, 0),
    (0, 140, 255),
    (200, 80, 120),
)


class Go2MapRenderer:
    def __init__(self, maps_dir=None, current_map_file=None):
        self.maps_dir = Path(maps_dir) if maps_dir else None
        self.current_map_file = Path(current_map_file) if current_map_file else None
        self._semantic_key = None
        self._semantic_overlay = None

    def render(
        self, cells, metadata, travelled_path, global_plan,
        submitted_waypoints, current_waypoint, robot_pose,
    ) -> str:
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
    def image_to_world(
        pixel_x: float, pixel_y: float, metadata,
    ) -> tuple[float, float]:
        local_x = pixel_x * metadata.resolution
        local_y = (metadata.height - 1 - pixel_y) * metadata.resolution
        cosine = math.cos(metadata.origin_yaw)
        sine = math.sin(metadata.origin_yaw)
        return (
            metadata.origin_x + local_x * cosine - local_y * sine,
            metadata.origin_y + local_x * sine + local_y * cosine,
        )

    @staticmethod
    def world_to_image(
        x: float, y: float, metadata,
    ) -> tuple[int, int]:
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
        image = np.full(cells.shape, 205, dtype=np.uint8)
        image[cells == 0] = 254
        image[cells >= 65] = 0
        uncertain = (cells > 0) & (cells < 65)
        image[uncertain] = 254 - cells[uncertain].astype(np.int16) * 254 // 100
        return cv2.cvtColor(np.flipud(image), cv2.COLOR_GRAY2BGR)

    def _pixels(self, poses, metadata) -> list[tuple[int, int]]:
        return [self.world_to_image(pose.x, pose.y, metadata) for pose in poses]

    def _apply_semantics(self, image: np.ndarray, metadata) -> None:
        try:
            path = self._places_path()
            modified = path.stat().st_mtime_ns if path and path.is_file() else None
            key = (path, modified, metadata)
            if key != self._semantic_key:
                self._semantic_key = key
                self._semantic_overlay = (
                    self._render_semantics(path, metadata) if modified else None
                )
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            print(f"Semantic map overlay ignored: {exc}")
            self._semantic_overlay = None
        if self._semantic_overlay is None:
            return
        alpha = self._semantic_overlay[:, :, 3:4].astype(np.float32) / 255.0
        image[:] = (
            image.astype(np.float32) * (1.0 - alpha)
            + self._semantic_overlay[:, :, :3].astype(np.float32) * alpha
        ).astype(np.uint8)

    def _places_path(self) -> Path | None:
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

    def _render_semantics(self, path: Path, metadata) -> np.ndarray:
        places = json.loads(path.read_text(encoding="utf-8"))["places"]
        overlay = np.zeros((metadata.height, metadata.width, 4), dtype=np.uint8)
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
            if kind not in {"point", "line", "area"}:
                continue
            draw_semantic_shape(overlay, kind, points, color)
            anchor = tuple(
                points[0]
                if kind == "point"
                else points.mean(axis=0).astype(int)
            )
            draw_label(
                overlay, str(place["name"]).upper(), anchor, occupied, color
            )
        return overlay
