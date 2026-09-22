"""Authoritative in-process mission state for the Unitree Go2 agent."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MissionTask:
    text: str
    strategy: str = ""
    waypoints: list[dict] = field(default_factory=list)
    current_waypoint: int = 0
    travelled_path: list[dict[str, float]] = field(default_factory=list)


class MissionState:
    """Keep task and route facts independent of conversational history."""

    def __init__(self):
        self.active_task: MissionTask | None = None
        self.queued_tasks: deque[str] = deque()
        self.paused_tasks: deque[MissionTask] = deque()
        self._events: deque[str] = deque(maxlen=8)
        self._switch_after_cancel = False

    def queue_task(
        self, text: str, *, run_next: bool = False
    ) -> MissionTask | None:
        self._add_event(f"Received task: {text}")
        if self.active_task is None:
            self.active_task = MissionTask(text=text)
            self._add_event(f"Activated task: {text}")
            return self.active_task
        if run_next:
            self.queued_tasks.appendleft(text)
        else:
            self.queued_tasks.append(text)
        return None

    def switch_to_next_task(self) -> MissionTask:
        if not self.queued_tasks:
            raise RuntimeError("there is no queued task")
        if self.active_task is not None:
            self.paused_tasks.append(self.active_task)
        text = self.queued_tasks.popleft()
        self.active_task = MissionTask(text=text)
        self._add_event(f"Activated queued task: {text}")
        return self.active_task

    def request_task_switch_after_cancel(self) -> None:
        self._switch_after_cancel = True

    def save_task_route(
        self,
        strategy: str,
        waypoints: list[dict],
    ) -> None:
        if self.active_task is None:
            raise RuntimeError("there is no active task")
        self.active_task.strategy = strategy
        self.active_task.waypoints = [
            dict(waypoint) for waypoint in waypoints
        ]
        self.active_task.current_waypoint = 0
        self._add_event(f"Started route with {len(waypoints)} waypoints")

    def save_route_progress(
        self,
        remaining_count: int,
        travelled_path: list,
    ) -> None:
        """Save enough route progress to show and resume the paused task."""
        if self.active_task is None:
            raise RuntimeError("there is no active task")
        self.active_task.current_waypoint = max(
            0, len(self.active_task.waypoints) - remaining_count
        )
        self.active_task.travelled_path = [
            {"x": pose.x, "y": pose.y, "yaw": pose.yaw}
            for pose in travelled_path
        ]
        self._add_event("Requested route cancellation")

    def record_navigation_result(self, event) -> None:
        if self.active_task and event.current_waypoint is not None:
            self.active_task.current_waypoint = event.current_waypoint
        detail = f": {event.detail}" if event.detail else ""
        progress = ""
        if event.current_waypoint is not None:
            progress = (
                f" at waypoint {event.current_waypoint}"
                f"/{event.waypoint_count or '?'}"
            )
        self._add_event(f"Navigation {event.kind}{progress}{detail}")
        if event.kind == "cancelled" and self._switch_after_cancel:
            self._switch_after_cancel = False
            self.switch_to_next_task()
        elif event.kind == "failed":
            self._switch_after_cancel = False

    def finish_active_task(self, report: str) -> MissionTask | None:
        if self.active_task is not None:
            self._add_event(f"Completed task: {report}")
            self.active_task = None
        return self._activate_next_task()

    def to_prompt_text(self) -> str:
        active = self._task_to_prompt_data(self.active_task)
        queued = list(self.queued_tasks)
        paused = [
            self._task_to_prompt_data(task) for task in self.paused_tasks
        ]
        return (
            f"active_task: {active}\n"
            f"queued_tasks: {queued}\n"
            f"paused_tasks: {paused}\n"
            f"recent_events: {list(self._events)}"
        )

    def _activate_next_task(self) -> MissionTask | None:
        if self.queued_tasks:
            text = self.queued_tasks.popleft()
            self.active_task = MissionTask(text=text)
            self._add_event(f"Activated queued task: {text}")
            return self.active_task
        if self.paused_tasks:
            task = self.paused_tasks.popleft()
            self.active_task = task
            self._add_event(f"Resumed task: {task.text}")
            return task
        return None

    def _add_event(self, event: str) -> None:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._events.append(f"{now} {event}")

    @staticmethod
    def _task_to_prompt_data(task: MissionTask | None) -> dict | None:
        if task is None:
            return None
        return {
            "text": task.text,
            "strategy": task.strategy,
            "current_waypoint": task.current_waypoint,
        }
