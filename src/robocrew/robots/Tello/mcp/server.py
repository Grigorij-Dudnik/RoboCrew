"""MCP server exposing the RoboCrew Tello inspection executor."""

from __future__ import annotations

import os

import anyio
from mcp.server.fastmcp import FastMCP

from robocrew.robots.Tello.mcp.executor_runtime import TelloExecutorRuntime


runtime = TelloExecutorRuntime(
    model=os.getenv("ROBOCREW_TELLO_EXECUTOR_MODEL", "google_genai:gemini-robotics-er-1.6-preview")
)
mcp = FastMCP("RoboCrew Tello", json_response=True)

mcp.tool()(runtime.connect_drone)
mcp.tool()(runtime.drone_status)
mcp.tool()(runtime.inspect_target)
mcp.resource("tello://snapshots")(runtime.snapshots_resource)
mcp.resource("tello://artifacts")(runtime.artifacts_resource)


def main() -> None:
    mcp.settings.host = os.getenv("ROBOCREW_TELLO_MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.getenv("ROBOCREW_TELLO_MCP_PORT", "8765"))
    try:
        import uvicorn
        if os.name == "nt":
            import asyncio

            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        async def run_server() -> None:
            config = uvicorn.Config(
                mcp.streamable_http_app(),
                host=mcp.settings.host,
                port=mcp.settings.port,
                log_level=mcp.settings.log_level.lower(),
                timeout_graceful_shutdown=1,
            )
            await uvicorn.Server(config).serve()

        anyio.run(run_server)
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()
