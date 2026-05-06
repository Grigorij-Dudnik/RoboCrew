"""Runtime wrapper for exposing the Tello inspection executor through MCP."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass
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


@dataclass
class Snapshot:
    path: str
    reason: str
    step: int
    captured_at: str
    telemetry: dict[str, Any]


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
        self.snapshots: list[Snapshot] = []
        self.step_count = 0

    def connect_drone(self) -> dict[str, Any]:
        """Connect or reconnect to the Tello drone."""
        self._close_tello()
        self.snapshots = []
        self.current_target = None
        self.last_target = None
        self.last_executor_task = None
        self.last_report = None
        self.step_count = 0
        self.tello = Tello()
        self.tello.connect()
        self.executor = self._create_executor(self.tello)
        return self.drone_status()

    def drone_status(self) -> dict[str, Any]:
        """Capture current camera view and return telemetry, reports, and artifacts."""
        self._require_connected()
        telemetry = self._telemetry()
        snapshot = self._capture_snapshot("status", telemetry) if telemetry["fresh"] else None
        return {
            "connected": telemetry["fresh"],
            "current_target": self.current_target,
            "last_target": self.last_target,
            "last_executor_task": self.last_executor_task,
            "last_report": self.last_report,
            "environment_state": self._environment_state(snapshot),
            "telemetry": telemetry,
            "artifacts": self._artifact_paths(),
            "latest_snapshot": asdict(snapshot) if snapshot else None,
        }

    def inspect_target(
        self,
        target: str,
        reference_image_paths: list[str] | None = None,
        yaw_degrees: int | None = None,
    ) -> dict[str, Any]:
        """Inspect one room, wall, or visible area, optionally with reference images or a yaw hint."""
        self._require_connected()
        telemetry = self._telemetry()
        if not telemetry["fresh"]:
            return {
                "status": "disconnected",
                "target": target,
                "report": "Drone did not answer fresh telemetry queries. Call connect_drone before inspecting.",
                "telemetry": telemetry,
            }
        print(
            f"[MCP] inspect_target target={target!r} "
            f"yaw_degrees={yaw_degrees!r} reference_image_paths={reference_image_paths or []!r}"
        )
        self.current_target = target
        self.last_target = target
        self.last_report = None
        self.step_count = 0
        self.executor.message_history = [self.executor.system_message]
        self.executor.reference_images_base64 = self._read_reference_images(reference_image_paths or [])
        self.last_executor_task = self._inspection_task(target, yaw_degrees)
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
        except Exception as exc:
            status = "interrupted"
            self.last_report = f"Inspection interrupted for {target}: {exc}"
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
            "yaw_degrees": yaw_degrees,
            "telemetry": self._telemetry(),
        }

    def snapshots_resource(self) -> str:
        """Sampled inspection image metadata and base64 JPEGs."""
        return json.dumps(
            [
                {**asdict(snapshot), "image_base64": self._read_base64(snapshot.path)}
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

    def _inspection_task(self, target: str, yaw_degrees: int | None = None) -> str:
        task = f"Inspect target: {target}."
        if yaw_degrees is not None:
            task += f" The target may be near yaw {yaw_degrees} degrees."
        return (
            f"{task} Do not treat height as part of the target; use the flat-inspection skill "
            "to cover its height passes. In finish_task report include: room or wall description; "
            "what was inspected; what remains unclear; visible doorways, openings, or interconnections; "
            "artifacts saved; suggested next local target."
        )

    def _capture_snapshot(self, reason: str, telemetry: dict[str, Any] | None = None) -> Snapshot | None:
        if self.tello is None:
            return None
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.tello.stream_on:
            self.tello.streamon()
        frame = self.tello.get_frame_read().frame
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if frame is not None and frame.size and frame.any():
                break
            time.sleep(0.1)
            frame = self.tello.get_frame_read().frame
        if frame is None or not frame.size or not frame.any():
            return None
        captured_at = datetime.now().isoformat(timespec="seconds")
        filename = f"{captured_at.replace(':', '-')}_{reason}_{len(self.snapshots) + 1}.jpg"
        path = self.snapshots_dir / filename
        cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        snapshot = Snapshot(
            path=str(path),
            reason=reason,
            step=self.step_count,
            captured_at=captured_at,
            telemetry=telemetry or self._telemetry(),
        )
        self.snapshots.append(snapshot)
        return snapshot

    def _environment_state(self, snapshot: Snapshot | None) -> dict[str, Any]:
        return {
            "last_target": self.last_target,
            "last_report": self.last_report,
            "latest_snapshot": asdict(snapshot) if snapshot else None,
            "recent_snapshots": [asdict(item) for item in self.snapshots[-5:]],
        }

    def _environment_update(self, target: str, status: str) -> dict[str, Any]:
        return {
            "target": target,
            "status": status,
            "report": self.last_report,
            "snapshots": [asdict(item) for item in self.snapshots[-10:]],
            "artifacts": self._artifact_paths(),
        }

    def _telemetry(self) -> dict[str, Any]:
        if self.tello is None:
            return {"fresh": False}
        telemetry: dict[str, Any] = {"fresh": False}
        queries = {
            "battery": self.tello.query_battery,
            "height_cm": self.tello.query_height,
        }
        for key, query in queries.items():
            try:
                telemetry[key] = query()
                telemetry["fresh"] = True
            except Exception as exc:
                telemetry[key] = f"unavailable: {exc}"
        try:
            telemetry["yaw_degrees"] = self.tello.query_attitude().get("yaw")
            telemetry["fresh"] = True
        except Exception as exc:
            telemetry["yaw_degrees"] = f"unavailable: {exc}"
        return telemetry

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

    def _close_tello(self) -> None:
        if self.tello is None:
            return
        try:
            self.tello.end()
        except Exception:
            pass
        self.tello = None
        self.executor = None
