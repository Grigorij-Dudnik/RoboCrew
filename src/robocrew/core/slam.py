import numpy as np
import io
import os
import pickle
import base64
from breezyslam.algorithms import RMHC_SLAM
from breezyslam.sensors import RPLidarA1
from PIL import Image

MAP_SIZE_PIXELS = 500
MAP_SIZE_METERS = 10
DEFAULT_CACHE_PATH = os.path.expanduser("~/.cache/robocrew/slam_map.pkl")


class SlamMapper:
    """
    Thin wrapper around BreezySLAM RMHC_SLAM for lidar-only SLAM
    (no odometry / wheel encoders required).

    Usage inside the agent loop::

        mapper = SlamMapper()
        # every lidar step:
        angles_rad, distances_mm, _ = fetch_scan_data(...)
        mapper.update(angles_rad, distances_mm)
        png_b64 = mapper.get_map_png_b64()
    """

    def __init__(
        self,
        map_size_pixels: int = MAP_SIZE_PIXELS,
        map_size_meters: float = MAP_SIZE_METERS,
        random_seed: int = 42,
        load_map: bool = True,
        cache_path: str = DEFAULT_CACHE_PATH,
    ):
        self.map_size_pixels = map_size_pixels
        self.map_size_meters = map_size_meters
        self.cache_path = cache_path

        self.slam = RMHC_SLAM(
            RPLidarA1(),
            map_size_pixels,
            map_size_meters,
            random_seed=random_seed,
            map_quality=200,
            sigma_xy_mm=500,
            sigma_theta_degrees=45,
        )
        self.mapbytes = bytearray(map_size_pixels * map_size_pixels)
        self.x_mm: float = 0.0
        self.y_mm: float = 0.0
        self.theta_degrees: float = 0.0

        if load_map and os.path.exists(cache_path):
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, angles_rad: np.ndarray, distances_mm: np.ndarray) -> None:
        """Feed one lidar scan into the SLAM algorithm."""
        scan = self._to_breezy_scan(angles_rad, distances_mm)
        # Calling without pose_change forces pure scan-matching (no odometry)
        self.slam.update(scan)
        self.x_mm, self.y_mm, self.theta_degrees = self.slam.getpos()
        self.slam.getmap(self.mapbytes)

    def get_map_png_b64(self) -> str:
        """Return the current occupancy map as a base64-encoded PNG string."""
        arr = np.frombuffer(self.mapbytes, dtype=np.uint8).reshape(
            self.map_size_pixels, self.map_size_pixels
        )
        # BreezySLAM grayscale map: 0=unknown(gray), 127=obstacle, 255=free
        # Re-map to more visible colours
        rgb = np.stack([arr, arr, arr], axis=-1)
        # Mark unknown areas (value == 0) as mid-gray so the map looks cleaner
        unknown = arr == 0
        rgb[unknown] = [128, 128, 128]

        # Mark robot position as red dot
        px = int(self.x_mm / (self.map_size_meters * 1000) * self.map_size_pixels)
        py = self.map_size_pixels - int(
            self.y_mm / (self.map_size_meters * 1000) * self.map_size_pixels
        )  # flip Y
        px = max(3, min(self.map_size_pixels - 4, px))
        py = max(3, min(self.map_size_pixels - 4, py))
        rgb[py - 3 : py + 4, px - 3 : px + 4] = [255, 0, 0]

        img = Image.fromarray(rgb.astype(np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def pose_str(self) -> str:
        """Human-readable pose string for the LLM prompt."""
        return (
            f"x={self.x_mm / 1000:.2f} m, "
            f"y={self.y_mm / 1000:.2f} m, "
            f"heading={self.theta_degrees:.1f}°"
        )

    def save(self) -> None:
        """Persist the map to disk for future sessions."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(
                {
                    "mapbytes": bytes(self.mapbytes),
                    "x_mm": self.x_mm,
                    "y_mm": self.y_mm,
                    "theta_degrees": self.theta_degrees,
                },
                f,
            )
        print(f"[SLAM] Map saved to {self.cache_path}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_breezy_scan(self, angles_rad: np.ndarray, distances_mm: np.ndarray) -> list:
        """
        Convert sparse (angle, distance) arrays to a 360-element list
        expected by BreezySLAM (index = degree, value = mm, 0 = no reading).
        """
        scan = [0] * 360
        for angle, dist in zip(angles_rad, distances_mm):
            deg = int(np.degrees(angle)) % 360
            d = int(dist)
            if d > 0 and (scan[deg] == 0 or d < scan[deg]):
                scan[deg] = d
        return scan

    def _load(self) -> None:
        """Load a previously saved map from disk."""
        try:
            with open(self.cache_path, "rb") as f:
                data = pickle.load(f)
            self.mapbytes[:] = data["mapbytes"]
            self.x_mm = data["x_mm"]
            self.y_mm = data["y_mm"]
            self.theta_degrees = data["theta_degrees"]
            print(f"[SLAM] Map loaded from {self.cache_path}")
        except Exception as exc:
            print(f"[SLAM] Could not load saved map: {exc}")