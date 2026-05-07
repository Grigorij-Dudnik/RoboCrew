"""Runtime wrapper for exposing the Tello inspection executor through MCP."""

from __future__ import annotations

import base64
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
from djitellopy import Tello

from robocrew.core.tools import finish_task
from robocrew.robots.Tello.tello_LLM_agent import TelloAgent
from robocrew.robots.Tello.tools import (
    create_land,
    create_move_backward,
    create_move_down,
    create_move_forward,
    create_move_up,
    create_strafe_left,
    create_strafe_right,
    create_takeoff,
    create_turn_left,
    create_turn_right,
)


class TelloExecutorRuntime:
    """Owns the Tello executor, snapshots, and reports for MCP tools."""

    def __init__(
        self,
        model: str = "google_genai:gemini-robotics-er-1.6-preview",
        artifacts_dir: str | Path = "artifacts",
        snapshots_dir: str | Path = "artifacts/tello_snapshots",
    ):
        self.model = model
        self.artifacts_dir = Path(artifacts_dir)
        self.snapshots_dir = Path(snapshots_dir)
        self.tello: Tello | None = None
        self.executor: TelloAgent | None = None
        self.current_target: str | None = None
        self.last_target: str | None = None
        self.last_executor_task: str | None = None
        self.last_report: str | None = None
        self.snapshots: list[dict[str, Any]] = []
        self.step_count = 0

    def connect_drone(self) -> dict[str, Any]:
        """Connect or reconnect to the Tello drone and start the camera stream."""
        self.shutdown()
        self.snapshots = []
        self.current_target = None
        self.last_target = None
        self.last_executor_task = None
        self.last_report = None
        self.step_count = 0
        self.tello = Tello()
        self.tello.connect()
        self.tello.streamon()
        self.executor = self._create_executor(self.tello)
        return self.drone_status()

    def drone_status(self) -> dict[str, Any]:
        """Capture current camera view and return telemetry, reports, and artifacts."""
        if self.tello is None:
            return {"connected": False, "telemetry": {"fresh": False}}
        telemetry = self._telemetry()
        snapshot = self._capture_snapshot("status", telemetry) if telemetry["fresh"] else None
        return {
            "connected": telemetry["fresh"],
            "current_target": self.current_target,
            "last_target": self.last_target,
            "last_executor_task": self.last_executor_task,
            "last_report": self.last_report,
            "telemetry": telemetry,
            "artifacts": self._artifact_paths(),
            "latest_snapshot": snapshot,
            "recent_snapshots": self.snapshots[-5:],
        }

    def inspect_target(
        self,
        target: str,
        reference_image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Inspect one room, wall, or visible area, optionally with reference images."""
        self._require_connected()
        telemetry = self._telemetry()
        if not telemetry["fresh"]:
            return {
                "status": "disconnected",
                "target": target,
                "report": "Drone did not answer fresh telemetry queries. Call connect_drone before inspecting.",
                "telemetry": telemetry,
            }
        print(f"[MCP] inspect_target target={target!r} reference_image_paths={reference_image_paths or []!r}")
        self.current_target = target
        self.last_target = target
        self.last_report = None
        self.step_count = 0
        self.executor.message_history = [self.executor.system_message]
        self.executor.reference_images_base64 = self._read_reference_images(reference_image_paths or [])
        self.last_executor_task = self._inspection_task(target)
        print(f"[MCP] executor_task={self.last_executor_task!r}")
        self.executor.task = self.last_executor_task
        self._capture_snapshot("inspection_start")

        try:
            while self.executor.task:
                self.step_count += 1
                report = self.executor.main_loop_content()
                if self.step_count % 5 == 0:
                    self._capture_snapshot("inspection_step")
                if report:
                    self.last_report = report
            self._capture_snapshot("inspection_complete")
            status = "completed"
            error = None
        except Exception as exc:
            status = "interrupted"
            error = traceback.format_exc()
            self.last_report = f"Inspection interrupted for {target}: {exc}"
            print(error)
            if self.executor:
                self.executor.task = None
            self._capture_snapshot("inspection_interrupted")
        finally:
            self.current_target = None
            print(f"[MCP] inspect_target finished status={status} target={target!r}")

        return {
            "status": status,
            "target": target,
            "last_executor_task": self.last_executor_task,
            "report": self.last_report,
            "environment_update": self._environment_update(target, status),
            "reference_image_paths": reference_image_paths or [],
            "telemetry": self._telemetry(),
            "error": error,
        }

    def snapshots_resource(self) -> str:
        """Sampled inspection image metadata and base64 JPEGs."""
        return json.dumps(
            [
                {**snapshot, "image_base64": self._read_base64(snapshot["path"])}
                for snapshot in self.snapshots[-20:]
            ],
            indent=2,
        )

    def artifacts_resource(self) -> str:
        """Saved artifact photo metadata and base64 JPEGs."""
        return json.dumps(
            {
                "artifacts": [
                    {"path": path, "image_base64": self._read_base64(path)}
                    for path in self._artifact_paths()
                ]
            },
            indent=2,
        )

    def _create_executor(self, tello: Tello) -> TelloAgent:
        return TelloAgent(
            model=self.model,
            tools=[
                create_takeoff(tello),
                create_move_forward(tello),
                create_move_backward(tello),
                create_move_up(tello),
                create_move_down(tello),
                create_strafe_left(tello),
                create_strafe_right(tello),
                create_turn_left(tello),
                create_turn_right(tello),
                create_land(tello),
                finish_task,
            ],
            tello=tello,
            skills=["flat_inspection"],
            history_len=30,
        )

    def _inspection_task(self, target: str) -> str:
        task = f"Inspect target: {target}."
        return (
            f"{task} Do not treat height as part of the target; use the flat-inspection skill "
            "to cover its height passes. In finish_task report include: room or wall description; "
            "what was inspected; what remains unclear; visible doorways, openings, or interconnections; "
            "artifacts saved; suggested next local target."
        )

    def _capture_snapshot(self, reason: str, telemetry: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if self.tello is None:
            return None
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.tello.stream_on:
            self.tello.streamon()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            frame = self.tello.get_frame_read().frame
            if frame is not None and frame.size and frame.any():
                break
            time.sleep(0.1)
        else:
            return None
        captured_at = datetime.now().isoformat(timespec="seconds")
        filename = f"{captured_at.replace(':', '-')}_{reason}_{len(self.snapshots) + 1}.jpg"
        path = self.snapshots_dir / filename
        cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        snapshot = {
            "path": str(path),
            "reason": reason,
            "step": self.step_count,
            "captured_at": captured_at,
            "telemetry": telemetry or self._telemetry(),
        }
        self.snapshots.append(snapshot)
        return snapshot

    def _environment_update(self, target: str, status: str) -> dict[str, Any]:
        return {
            "target": target,
            "status": status,
            "report": self.last_report,
            "snapshots": self.snapshots[-10:],
            "artifacts": self._artifact_paths(),
        }

    def _telemetry(self) -> dict[str, Any]:
        if self.tello is None:
            return {"fresh": False}
        try:
            return {
                "fresh": True,
                "battery": self.tello.get_battery(),
                "height_cm": self.tello.get_distance_tof(),
                "yaw_degrees": self.tello.get_yaw(),
            }
        except Exception as exc:
            return {"fresh": False, "error": str(exc)}

    def _artifact_paths(self) -> list[str]:
        if not self.artifacts_dir.exists():
            return []
        return [
            str(path)
            for path in sorted(self.artifacts_dir.glob("*.jpg"))
            if self.snapshots_dir not in path.parents
        ]

    def _read_base64(self, path: str) -> str | None:
        image_path = Path(path)
        if not image_path.exists():
            return None
        return base64.b64encode(image_path.read_bytes()).decode("utf-8")

    def _read_reference_images(self, paths: list[str]) -> list[str]:
        return [image for path in paths if (image := self._read_base64(path))]

    def _require_connected(self) -> None:
        if self.tello is None or self.executor is None:
            self.connect_drone()

    def shutdown(self) -> None:
        """Release local Tello resources without sending slow network commands."""
        if self.tello is None:
            return
        tello = self.tello
        frame_reader = getattr(tello, "background_frame_read", None)
        if frame_reader is not None:
            frame_reader.stop()
            container = getattr(frame_reader, "container", None)
            if container is not None:
                container.close()
            tello.background_frame_read = None
        tello.stream_on = False
        tello.is_flying = False
        tello.end = lambda: None
        self.tello = None
        self.executor = None
