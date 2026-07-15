"""Geographic path projection for drone map images."""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from robocrew.robots.WaypointDrone.bridge import DroneObservation


METERS_PER_DEGREE_LAT = 111_320.0


def normalized_waypoints_to_gps(normalized_waypoints, center_gps, map_span_m):
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(center_gps["lat"]))
    return [
        {
            "lat": center_gps["lat"]
            + (0.5 - normalized_waypoint["y"]) * map_span_m / METERS_PER_DEGREE_LAT,
            "lon": center_gps["lon"]
            + (normalized_waypoint["x"] - 0.5) * map_span_m / meters_per_degree_lon,
        }
        for normalized_waypoint in normalized_waypoints
    ]


def draw_heading_marker_on_map(map_image, yaw_rad):
    center_x, center_y = map_image.shape[1] // 2, map_image.shape[0] // 2
    arrow_size = max(3, min(map_image.shape[:2]) // 80)
    marker_points = np.array([
        (
            center_x + arrow_size * 2.0 * math.cos(yaw_rad),
            center_y - arrow_size * 2.0 * math.sin(yaw_rad),
        ),
        (
            center_x + arrow_size * math.cos(yaw_rad + 2.4),
            center_y - arrow_size * math.sin(yaw_rad + 2.4),
        ),
        (
            center_x + arrow_size * math.cos(yaw_rad - 2.4),
            center_y - arrow_size * math.sin(yaw_rad - 2.4),
        ),
    ], dtype=np.int32)
    cv2.fillPoly(map_image, [marker_points], (0, 255, 255))


def draw_flight_paths_on_map(
    map_image_b64,
    current_gps,
    map_span_m,
    flown_path_gps,
    planned_route_gps,
    yaw_rad=0.0,
):
    if len(flown_path_gps) < 2 and not planned_route_gps:
        return map_image_b64
    map_image = cv2.imdecode(np.frombuffer(base64.b64decode(map_image_b64), np.uint8), cv2.IMREAD_COLOR)
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(current_gps["lat"]))

    def gps_path_to_pixels(gps_path):
        return np.array([
            (
                int(
                    map_image.shape[1] / 2
                    + (gps_point["lon"] - current_gps["lon"])
                    * meters_per_degree_lon
                    / map_span_m
                    * map_image.shape[1]
                ),
                int(
                    map_image.shape[0] / 2
                    - (gps_point["lat"] - current_gps["lat"])
                    * METERS_PER_DEGREE_LAT
                    / map_span_m
                    * map_image.shape[0]
                ),
            )
            for gps_point in gps_path
        ])

    if len(flown_path_gps) > 1:
        cv2.polylines(map_image, [gps_path_to_pixels(flown_path_gps)], False, (40, 80, 255), 5)
    if planned_route_gps:
        cv2.polylines(map_image, [gps_path_to_pixels([current_gps, *planned_route_gps])], False, (255, 120, 40), 5)
    draw_heading_marker_on_map(map_image, yaw_rad)
    return base64.b64encode(cv2.imencode(".jpg", map_image)[1]).decode()


@dataclass
class FlightMapState:
    flown_path_gps: list[dict[str, float]] = field(default_factory=list)
    planned_route_gps: list[dict[str, float]] = field(default_factory=list)
    latest_observation: DroneObservation | None = None

    def record_observation(self, flight_observation: DroneObservation) -> None:
        self.latest_observation = flight_observation
        current_gps = {
            "lat": flight_observation.gps["lat"],
            "lon": flight_observation.gps["lon"],
        }
        if not self.flown_path_gps or current_gps != self.flown_path_gps[-1]:
            self.flown_path_gps.append(current_gps)
        while self.planned_route_gps and self._distance_m(current_gps, self.planned_route_gps[0]) < 5.0:
            self.planned_route_gps.pop(0)
        if flight_observation.route_state in {"completed", "stopped"}:
            self.planned_route_gps.clear()

    def set_planned_route_from_normalized_waypoints(
        self, normalized_waypoints
    ) -> list[dict[str, float]]:
        reference_observation = self.latest_observation
        self.planned_route_gps = normalized_waypoints_to_gps(
            normalized_waypoints,
            reference_observation.gps,
            reference_observation.map_span_m,
        )
        return list(self.planned_route_gps)

    def draw_flight_paths_on_map(self, flight_observation: DroneObservation) -> str:
        return draw_flight_paths_on_map(
            flight_observation.map_image_b64,
            flight_observation.gps,
            flight_observation.map_span_m,
            self.flown_path_gps,
            self.planned_route_gps,
            flight_observation.yaw_rad,
        )

    @staticmethod
    def _distance_m(first_gps, second_gps):
        north = (second_gps["lat"] - first_gps["lat"]) * METERS_PER_DEGREE_LAT
        east = (
            (second_gps["lon"] - first_gps["lon"])
            * METERS_PER_DEGREE_LAT
            * math.cos(math.radians(first_gps["lat"]))
        )
        return math.hypot(north, east)
