"""MCP server exposing the RoboCrew Tello inspection executor."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from robocrew.robots.Tello.mcp.executor_runtime import TelloExecutorRuntime


runtime = TelloExecutorRuntime(
    model=os.getenv("ROBOCREW_TELLO_EXECUTOR_MODEL", "google_genai:gemini-robotics-er-1.6-preview")
)
mcp = FastMCP("RoboCrew Tello", json_response=True)


@mcp.tool()
def connect_drone() -> dict[str, Any]:
    """Connect or reconnect to the Tello drone."""
    return runtime.connect_drone()


@mcp.tool()
def drone_status() -> dict[str, Any]:
    """Capture current camera view and return telemetry, reports, and artifacts."""
    return runtime.drone_status()


@mcp.tool()
def inspect_target(
    target: str,
    reference_image_paths: list[str] | None = None,
    yaw_degrees: int | None = None,
) -> dict[str, Any]:
    """Inspect one room, wall, or visible area, optionally with reference images or a yaw hint."""
    return runtime.inspect_target(target, reference_image_paths, yaw_degrees)


mcp.resource("tello://snapshots")(runtime.snapshots_resource)
mcp.resource("tello://artifacts")(runtime.artifacts_resource)


@mcp.prompt()
def tello_flat_inspection_planner() -> str:
    """Planner instructions for external agents controlling RoboCrew Tello through MCP."""
    return """
Use RoboCrew as the Tello inspection executor. Keep mission memory outside RoboCrew.
Call drone_status before inspect_target. Inspect targets are rooms, walls, doorways, corridors, or visible areas, not heights or raw movements. If known, pass yaw_degrees as a heading hint.
Use inspect_target reports, snapshots, and artifacts to choose the next target.
""".strip()


def main() -> None:
    mcp.settings.host = os.getenv("ROBOCREW_TELLO_MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.getenv("ROBOCREW_TELLO_MCP_PORT", "8765"))
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
