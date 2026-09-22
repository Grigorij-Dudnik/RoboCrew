"""Cached semantic annotations for a Nav2 occupancy map."""

from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class SemanticPlace:
    name: str
    kind: str
    points: tuple[tuple[float, float], ...]


class SemanticMapOverlay:
    """Load the active map's sidecar and cache its rendered overlay."""

    def __init__(self, maps_dir: str, current_map_file: str):
        self.maps_dir = Path(maps_dir)
        self.current_map_file = Path(current_map_file)
        self._cache_key = None
        self._foreground = None
        self._background_weight = None

    def apply(self, image: np.ndarray, metadata) -> None:
        self._refresh(metadata)
        if self._foreground is None:
            return
        image[:] = (
            image.astype(np.float32) * self._background_weight
            + self._foreground
        ).astype(np.uint8)

    def _refresh(self, metadata) -> None:
        places_path = self._places_path()
        modified_ns = (
            places_path.stat().st_mtime_ns
            if places_path and places_path.is_file()
            else None
        )
        key = (
            str(places_path) if places_path else None,
            modified_ns,
            metadata.width,
            metadata.height,
            metadata.resolution,
            metadata.origin_x,
            metadata.origin_y,
            metadata.origin_yaw,
        )
        if key == self._cache_key:
            return

        self._cache_key = key
        self._foreground = None
        self._background_weight = None
        if modified_ns is None:
            return

        try:
            places = self._load_places(places_path)
            overlay = self._render_overlay(places, metadata)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Semantic map overlay ignored: {exc}")
            return

        alpha = overlay[:, :, 3:4].astype(np.float32) / 255.0
        self._foreground = overlay[:, :, :3].astype(np.float32) * alpha
        self._background_weight = 1.0 - alpha

    def _places_path(self) -> Path | None:
        if not self.current_map_file.is_file():
            return None
        for line in self.current_map_file.read_text(
            encoding="utf-8"
        ).splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == "map_file_name":
                map_name = Path(value.strip().strip("\"'")).name
                if map_name:
                    return self.maps_dir / f"{map_name}.places.json"
        return None

    @staticmethod
    def _load_places(path: Path) -> list[SemanticPlace]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_places = payload.get("places") if isinstance(payload, dict) else None
        if not isinstance(raw_places, list):
            raise ValueError(f"{path.name}: places must be a list")

        places = []
        minimum_points = {"point": 1, "line": 2, "area": 3}
        for index, raw_place in enumerate(raw_places):
            if not isinstance(raw_place, dict):
                raise ValueError(f"{path.name}: place {index} must be an object")
            name = str(raw_place.get("name", "")).strip()
            kind = str(raw_place.get("type", "")).strip()
            raw_points = raw_place.get("points")
            if not name:
                raise ValueError(f"{path.name}: place {index} has no name")
            if kind not in minimum_points:
                raise ValueError(
                    f"{path.name}: place {name!r} has invalid type {kind!r}"
                )
            if not isinstance(raw_points, list):
                raise ValueError(
                    f"{path.name}: place {name!r} points must be a list"
                )
            points = []
            for point in raw_points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError(
                        f"{path.name}: place {name!r} has an invalid point"
                    )
                points.append((float(point[0]), float(point[1])))
            if len(points) < minimum_points[kind]:
                raise ValueError(
                    f"{path.name}: place {name!r} needs at least "
                    f"{minimum_points[kind]} point(s)"
                )
            if kind == "point" and len(points) != 1:
                raise ValueError(
                    f"{path.name}: point {name!r} must have one coordinate"
                )
            places.append(SemanticPlace(name, kind, tuple(points)))
        return places

    def _render_overlay(
        self, places: list[SemanticPlace], metadata
    ) -> np.ndarray:
        overlay = np.zeros(
            (metadata.height, metadata.width, 4), dtype=np.uint8
        )
        rendered = []
        for place in places:
            points = np.asarray(
                [
                    self._world_to_image(world_x, world_y, metadata)
                    for world_x, world_y in place.points
                ],
                dtype=np.int32,
            )
            self._draw_shape(overlay, place.kind, points)
            rendered.append((place, points))

        for place, points in rendered:
            anchor = self._label_anchor(place.kind, points)
            self._draw_label(overlay, place.name, anchor)
        return overlay

    @staticmethod
    def _draw_shape(
        overlay: np.ndarray, kind: str, points: np.ndarray
    ) -> None:
        black = (0, 0, 0, 230)
        magenta = (255, 0, 255, 220)
        if kind == "point":
            point = tuple(points[0])
            cv2.circle(overlay, point, 10, black, -1, cv2.LINE_AA)
            cv2.circle(overlay, point, 7, magenta, -1, cv2.LINE_AA)
        elif kind == "line":
            cv2.polylines(
                overlay, [points], False, black, 9, cv2.LINE_AA
            )
            cv2.polylines(
                overlay, [points], False, magenta, 5, cv2.LINE_AA
            )
        else:
            cv2.fillPoly(overlay, [points], (255, 0, 255, 55), cv2.LINE_AA)
            cv2.polylines(
                overlay, [points], True, black, 7, cv2.LINE_AA
            )
            cv2.polylines(
                overlay, [points], True, magenta, 4, cv2.LINE_AA
            )

    @classmethod
    def _label_anchor(
        cls, kind: str, points: np.ndarray
    ) -> tuple[int, int]:
        if kind == "point":
            return tuple(points[0])
        if kind == "line":
            return cls._polyline_midpoint(points)
        moments = cv2.moments(points)
        if moments["m00"]:
            return (
                int(round(moments["m10"] / moments["m00"])),
                int(round(moments["m01"] / moments["m00"])),
            )
        mean = points.mean(axis=0)
        return int(round(mean[0])), int(round(mean[1]))

    @staticmethod
    def _polyline_midpoint(points: np.ndarray) -> tuple[int, int]:
        segments = points[1:].astype(float) - points[:-1].astype(float)
        lengths = np.linalg.norm(segments, axis=1)
        target = lengths.sum() / 2.0
        distance = 0.0
        for index, length in enumerate(lengths):
            if distance + length >= target and length > 0:
                ratio = (target - distance) / length
                point = points[index] + segments[index] * ratio
                return int(round(point[0])), int(round(point[1]))
            distance += length
        return tuple(points[-1])

    @staticmethod
    def _draw_label(
        overlay: np.ndarray, name: str, anchor: tuple[int, int]
    ) -> None:
        label = _ascii_label(name)
        height, width = overlay.shape[:2]
        margin = 5
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.65
        thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(
            label, font, font_scale, thickness
        )
        available_width = max(1, width - 2 * margin - 8)
        if text_width > available_width:
            font_scale *= available_width / text_width
            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, font_scale, thickness
            )

        default_x = anchor[0] + 10
        default_y = anchor[1] - 10
        x = min(max(default_x, margin + 4), width - text_width - margin - 4)
        y = min(
            max(default_y, text_height + margin + 4),
            height - baseline - margin - 4,
        )
        if (x, y) != (default_x, default_y):
            cv2.line(
                overlay,
                anchor,
                (x, y - text_height // 2),
                (0, 0, 0, 230),
                4,
                cv2.LINE_AA,
            )
            cv2.line(
                overlay,
                anchor,
                (x, y - text_height // 2),
                (255, 0, 255, 230),
                2,
                cv2.LINE_AA,
            )

        top_left = (x - 4, y - text_height - 4)
        bottom_right = (x + text_width + 4, y + baseline + 4)
        cv2.rectangle(
            overlay, top_left, bottom_right, (0, 0, 0, 225), -1
        )
        cv2.rectangle(
            overlay, top_left, bottom_right, (255, 0, 255, 255), 2
        )
        cv2.putText(
            overlay,
            label,
            (x, y),
            font,
            font_scale,
            (255, 255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    @staticmethod
    def _world_to_image(
        world_x: float, world_y: float, metadata
    ) -> tuple[int, int]:
        delta_x = world_x - metadata.origin_x
        delta_y = world_y - metadata.origin_y
        cos_origin = math.cos(metadata.origin_yaw)
        sin_origin = math.sin(metadata.origin_yaw)
        local_x = delta_x * cos_origin + delta_y * sin_origin
        local_y = -delta_x * sin_origin + delta_y * cos_origin
        return (
            int(round(local_x / metadata.resolution)),
            int(round(metadata.height - 1 - local_y / metadata.resolution)),
        )


def _ascii_label(name: str) -> str:
    polish = str.maketrans(
        "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
        "acelnoszzACELNOSZZ",
    )
    normalized = unicodedata.normalize("NFKD", name.translate(polish))
    label = normalized.encode("ascii", "ignore").decode("ascii").strip()
    return label or "place"
