"""Render named places over a Nav2 occupancy map."""
import json
import math
from pathlib import Path
import cv2
import numpy as np

COLORS = ((255, 0, 255), (255, 180, 0), (0, 190, 0), (0, 140, 255), (200, 80, 120))


class SemanticMapOverlay:
    def __init__(self, maps_dir: str, current_map_file: str):
        self.maps_dir = Path(maps_dir)
        self.current_map_file = Path(current_map_file)
        self._key = None
        self._overlay = None

    def apply(self, image: np.ndarray, metadata) -> None:
        try:
            path = self._places_path()
            modified = path.stat().st_mtime_ns if path and path.is_file() else None
            key = (path, modified, metadata)
            if key != self._key:
                self._key = key
                self._overlay = self._render(path, metadata) if modified else None
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            print(f"Semantic map overlay ignored: {exc}")
            self._overlay = None
        if self._overlay is None:
            return
        alpha = self._overlay[:, :, 3:4].astype(np.float32) / 255.0
        image[:] = (
            image.astype(np.float32) * (1.0 - alpha)
            + self._overlay[:, :, :3].astype(np.float32) * alpha
        ).astype(np.uint8)
    def _places_path(self) -> Path | None:
        if not self.current_map_file.is_file():
            return None
        for line in self.current_map_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == "map_file_name":
                name = Path(value.strip().strip("\"'")).name
                return self.maps_dir / f"{name}.places.json" if name else None
        return None
    def _render(self, path: Path, metadata) -> np.ndarray:
        places = json.loads(path.read_text(encoding="utf-8"))["places"]
        overlay = np.zeros((metadata.height, metadata.width, 4), dtype=np.uint8)
        occupied = []
        for index, place in enumerate(places):
            points = np.asarray([
                self._world_to_image(x, y, metadata) for x, y in place["points"]
            ], dtype=np.int32)
            if not len(points):
                continue
            color = COLORS[index % len(COLORS)]
            semantic = (*color, 230)
            kind = place["type"]
            if kind == "point":
                cv2.circle(overlay, tuple(points[0]), 8, semantic, -1, cv2.LINE_AA)
            elif kind == "line":
                cv2.polylines(overlay, [points], False, semantic, 5, cv2.LINE_AA)
            elif kind == "area":
                cv2.fillPoly(overlay, [points], (*color, 55), cv2.LINE_AA)
                cv2.polylines(overlay, [points], True, semantic, 4, cv2.LINE_AA)
            else:
                continue
            anchor = tuple(points[0] if kind == "point" else points.mean(axis=0).astype(int))
            self._draw_label(overlay, str(place["name"]).upper(), anchor, occupied, color)
        return overlay
    @staticmethod
    def _draw_label(overlay, text, anchor, occupied, color) -> None:
        font = cv2.FONT_HERSHEY_DUPLEX
        (text_width, text_height), baseline = cv2.getTextSize(text, font, 0.55, 1)
        box_width, box_height = text_width + 8, text_height + baseline + 8
        x, y = anchor
        offsets = (
            (12, -box_height // 2), (-box_width - 12, -box_height // 2),
            (-box_width // 2, -box_height - 12), (-box_width // 2, 12),
            (12, -box_height - 12), (12, 12),
            (-box_width - 12, -box_height - 12), (-box_width - 12, 12),
        )
        candidates = []
        for dx, dy in offsets:
            left = min(max(x + dx, 5), max(5, overlay.shape[1] - box_width - 5))
            top = min(max(y + dy, 5), max(5, overlay.shape[0] - box_height - 5))
            candidates.append((left, top, left + box_width, top + box_height))

        def overlap(box):
            return sum(
                max(0, min(box[2], other[2]) - max(box[0], other[0])) *
                max(0, min(box[3], other[3]) - max(box[1], other[1]))
                for other in occupied
            )
        left, top, right, bottom = min(candidates, key=overlap)
        occupied.append((left - 3, top - 3, right + 3, bottom + 3))
        origin = (left + 4, top + 4 + text_height)
        cv2.putText(overlay, text, origin, font, 0.55, (0, 0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(overlay, text, origin, font, 0.55, (*color, 255), 1, cv2.LINE_AA)
    @staticmethod
    def _world_to_image(x: float, y: float, metadata) -> tuple[int, int]:
        dx, dy = x - metadata.origin_x, y - metadata.origin_y
        cosine, sine = math.cos(metadata.origin_yaw), math.sin(metadata.origin_yaw)
        local_x = dx * cosine + dy * sine
        local_y = -dx * sine + dy * cosine
        return (
            int(round(local_x / metadata.resolution)),
            int(round(metadata.height - 1 - local_y / metadata.resolution)),
        )
