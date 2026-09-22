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

        occupied_labels = []
        for place, points in rendered:
            anchor = self._label_anchor(place.kind, points)
            self._draw_label(
                overlay, place.name, anchor, occupied_labels
            )
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

    @classmethod
    def _draw_label(
        cls,
        overlay: np.ndarray,
        name: str,
        anchor: tuple[int, int],
        occupied: list[tuple[int, int, int, int]],
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

        box_width = text_width + 8
        box_height = text_height + baseline + 8
        left, top, right, bottom = cls._place_label_box(
            anchor,
            (box_width, box_height),
            (width, height),
            occupied,
        )
        occupied.append((left - 3, top - 3, right + 3, bottom + 3))

        target = (
            min(max(anchor[0], left), right),
            min(max(anchor[1], top), bottom),
        )
        if target != anchor:
            cv2.line(
                overlay,
                anchor,
                target,
                (0, 0, 0, 230),
                4,
                cv2.LINE_AA,
            )
            cv2.line(
                overlay,
                anchor,
                target,
                (255, 0, 255, 230),
                2,
                cv2.LINE_AA,
            )

        cv2.rectangle(
            overlay, (left, top), (right, bottom), (0, 0, 0, 225), -1
        )
        cv2.rectangle(
            overlay, (left, top), (right, bottom), (255, 0, 255, 255), 2
        )
        cv2.putText(
            overlay,
            label,
            (left + 4, top + 4 + text_height),
            font,
            font_scale,
            (255, 255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    @classmethod
    def _place_label_box(
        cls,
        anchor: tuple[int, int],
        box_size: tuple[int, int],
        image_size: tuple[int, int],
        occupied: list[tuple[int, int, int, int]],
    ) -> tuple[int, int, int, int]:
        box_width, box_height = box_size
        image_width, image_height = image_size
        margin = 5
        max_left = max(margin, image_width - margin - box_width)
        max_top = max(margin, image_height - margin - box_height)
        candidates = []
        seen = set()

        for distance in (12, 32, 52, 72, 92):
            raw_positions = (
                (anchor[0] + distance, anchor[1] - box_height // 2),
                (
                    anchor[0] - distance - box_width,
                    anchor[1] - box_height // 2,
                ),
                (
                    anchor[0] - box_width // 2,
                    anchor[1] - distance - box_height,
                ),
                (anchor[0] - box_width // 2, anchor[1] + distance),
                (anchor[0] + distance, anchor[1] - distance - box_height),
                (anchor[0] + distance, anchor[1] + distance),
                (
                    anchor[0] - distance - box_width,
                    anchor[1] - distance - box_height,
                ),
                (
                    anchor[0] - distance - box_width,
                    anchor[1] + distance,
                ),
            )
            for raw_left, raw_top in raw_positions:
                left = min(max(raw_left, margin), max_left)
                top = min(max(raw_top, margin), max_top)
                if (left, top) in seen:
                    continue
                seen.add((left, top))
                rectangle = (
                    left,
                    top,
                    left + box_width,
                    top + box_height,
                )
                candidates.append(rectangle)
                if not any(
                    cls._rectangles_overlap(rectangle, other)
                    for other in occupied
                ):
                    return rectangle

        free = []
        fallback = list(candidates)
        for top in range(margin, max_top + 1, 4):
            for left in range(margin, max_left + 1, 4):
                rectangle = (
                    left,
                    top,
                    left + box_width,
                    top + box_height,
                )
                fallback.append(rectangle)
                if not any(
                    cls._rectangles_overlap(rectangle, other)
                    for other in occupied
                ):
                    distance = (
                        left + box_width / 2 - anchor[0]
                    ) ** 2 + (
                        top + box_height / 2 - anchor[1]
                    ) ** 2
                    free.append((distance, rectangle))
        if free:
            return min(free, key=lambda item: item[0])[1]
        return min(
            fallback,
            key=lambda rectangle: sum(
                cls._overlap_area(rectangle, other) for other in occupied
            ),
        )

    @staticmethod
    def _rectangles_overlap(first, second) -> bool:
        return not (
            first[2] <= second[0]
            or first[0] >= second[2]
            or first[3] <= second[1]
            or first[1] >= second[3]
        )

    @staticmethod
    def _overlap_area(first, second) -> int:
        width = max(0, min(first[2], second[2]) - max(first[0], second[0]))
        height = max(
            0, min(first[3], second[3]) - max(first[1], second[1])
        )
        return width * height

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
