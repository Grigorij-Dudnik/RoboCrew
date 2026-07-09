"""Isaac Sim drone tools."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


def create_set_waypoints(drone):
    @tool
    def set_waypoints(waypoints: list[dict[str, Any]], altitude_m: float | None = None, note: str | None = None) -> str:
        """Send a non-empty ordered waypoint list to the Isaac drone route executor.

        Waypoints may use normalized map coordinates as {"x": 0.0-1.0, "y": 0.0-1.0}.
        """
        if not waypoints:
            raise ValueError("waypoints must contain at least one waypoint")

        result = drone.set_waypoints(waypoints=list(waypoints), altitude_m=altitude_m, note=note)
        current_gps = result["current_gps"]
        return f"Route submitted. Current drone GPS/location: {current_gps}"

    return set_waypoints
