"""RoboCrew agent for a Nav2-controlled Unitree Go2."""

from __future__ import annotations

import base64
import json
from collections import deque
from dataclasses import asdict, is_dataclass
from pathlib import Path
from queue import Queue
from typing import Any
from urllib.request import urlopen

import cv2
import numpy as np
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.UnitreeGo2.mission_state import MissionState
from robocrew.robots.UnitreeGo2.nav2_bridge import (
    NavigationEvent,
    UnitreeGo2NavBridge,
)
from robocrew.robots.UnitreeGo2.telegram_gateway import (
    TelegramEvent,
    TelegramGateway,
)

RECENT_TURN_LIMIT = 8


class UnitreeGo2Agent(LLMAgent):
    """React to Telegram, Nav2, and observation events without blocking Nav2."""

    def __init__(
        self,
        model: str,
        bridge: UnitreeGo2NavBridge,
        mission_state: MissionState,
        event_queue: Queue,
        telegram_gateway: TelegramGateway,
        *,
        tools: list | None = None,
        name: str = "Unitree Go2",
        system_prompt: str | None = None,
        battery_url: str | None = None,
    ):
        super().__init__(
            model=model,
            tools=tools or [],
            main_camera=None,
            name=name,
            system_prompt=system_prompt or self._load_system_prompt(),
            history_len=None,
        )
        self.bridge = bridge
        self.mission_state = mission_state
        self.event_queue = event_queue
        self.telegram_gateway = telegram_gateway
        self.battery_url = battery_url
        self._current_event: Any = None
        self._camera_history = deque(maxlen=4)

    def process_event(self, event: Any) -> None:
        if isinstance(event, NavigationEvent):
            self.mission_state.record_navigation_result(event)
        self._current_event = event
        active_task_before = self.mission_state.active_task
        history_start = len(self.message_history)
        report = self.main_loop_content()
        assignment = next(
            (
                message.content
                for message in self.message_history[history_start:]
                if isinstance(message, ToolMessage)
                and message.name == "queue_task"
            ),
            None,
        )
        if assignment:
            self.telegram_gateway.send_message(str(assignment))
            if (
                active_task_before is None
                and self.mission_state.active_task is not None
                and not self.bridge.navigation_active
            ):
                self.event_queue.put({"kind": "task_activated"})
        if report is not None:
            self._handle_task_report(report)

    def main_loop_content(self):
        active_task = self.mission_state.active_task
        observation = self.bridge.get_observation()
        message_content = [
            {
                "type": "text",
                "text": (
                    "CURRENT EVENT\n"
                    f"{self._event_to_text(self._current_event)}\n\n"
                    "CURRENT MISSION STATE\n"
                    f"{self.mission_state.to_prompt_text()}\n\n"
                    "CURRENT NAVIGATION STATE\n"
                    f"state: {observation.navigation_state}\n"
                    f"waypoint: {observation.current_waypoint}/"
                    f"{observation.waypoint_count}\n\n"
                    f"battery: {self._battery_status()}"
                ),
            }
        ]
        if observation.camera_image_b64:
            message_content.extend(
                [
                    {"type": "text", "text": "\n\nCurrent front camera:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                f"{observation.camera_image_b64}"
                            )
                        },
                    },
                ]
            )
            if len(self._camera_history) == 4:
                frames = [
                    cv2.imdecode(np.frombuffer(base64.b64decode(image), np.uint8), 1)
                    for image in reversed(self._camera_history)
                ]
                height, width = frames[0].shape[:2]
                tiles = [cv2.resize(frame, (width // 2, height // 2)) for frame in frames]
                collage = np.vstack((np.hstack(tiles[:2]), np.hstack(tiles[2:])))
                collage = base64.b64encode(
                    cv2.imencode(".jpg", collage)[1]
                ).decode()
                message_content.extend(
                    [
                        {"type": "text", "text": "\n\nPrevious camera observations, newest first:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{collage}"}},
                    ]
                )
            if active_task is not None:
                self._camera_history.append(observation.camera_image_b64)
        else:
            message_content.append(
                {"type": "text", "text": "\n\nFront camera: unavailable"}
            )
        if observation.map_image_b64:
            message_content.extend(
                [
                    {"type": "text", "text": "\n\nCurrent annotated Nav2 map:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                f"{observation.map_image_b64}"
                            )
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "\nMap legend: RED is travelled route; BLUE is the "
                            "current Nav2 plan or remaining submitted route; "
                            "the yellow marker is the robot pose and heading. "
                            "Normalized x increases left-to-right and y "
                            "top-to-bottom."
                        ),
                    },
                ]
            )
        else:
            message_content.append(
                {"type": "text", "text": "\n\nNav2 map: unavailable"}
            )
        return self.invoke_llm_with_message(HumanMessage(message_content))

    def messages_for_model(self):
        """Keep recent roles while removing stale image-only context."""
        history = list(self.message_history[1:])
        if not history:
            return [self.system_message]

        human_indices = [
            index
            for index, message in enumerate(history)
            if isinstance(message, HumanMessage)
        ]
        start = (
            human_indices[-RECENT_TURN_LIMIT]
            if len(human_indices) >= RECENT_TURN_LIMIT
            else 0
        )
        older = history[:start]
        recent = history[start:]

        messages = [self.system_message]
        if older:
            messages.append(
                HumanMessage(
                    "Earlier conversation summary:\n"
                    f"{self._summarize_messages(older)}"
                )
            )
        for index, message in enumerate(recent):
            is_newest = index == len(recent) - 1
            messages.append(
                message if is_newest else self._without_old_images(message)
            )
        return messages

    def cleanup(self):
        self.telegram_gateway.stop()
        self.bridge.close()
        super().cleanup()

    def _handle_task_report(self, report: str) -> None:
        """Mirror RoboCrew's completed task into mission state and Telegram."""
        next_task = self.mission_state.finish_active_task(report)
        self._camera_history.clear()
        self.telegram_gateway.send_message(report)
        if next_task:
            self.event_queue.put({"kind": "task_activated"})

    def _event_to_text(self, event: Any) -> str:
        if isinstance(event, TelegramEvent):
            return f"kind: telegram_request\ntext: {event.text}"
        if isinstance(event, NavigationEvent) and event.kind == "failed":
            reason = event.detail or "Nav2 did not provide a failure reason"
            return (
                "kind: navigation_failed\n"
                f"current_waypoint: {event.current_waypoint}\n"
                f"waypoint_count: {event.waypoint_count}\n"
                f"reason: {reason}"
            )
        if is_dataclass(event):
            payload = asdict(event)
        else:
            payload = event
        return "\n".join(f"{key}: {value}" for key, value in payload.items())

    @staticmethod
    def _summarize_messages(messages: list) -> str:
        events = []
        scheduled_observation = False
        for message in messages:
            if isinstance(message, HumanMessage):
                text = UnitreeGo2Agent._text_content(message.content)
                if text:
                    current_event = text.split(
                        "\n\nCURRENT MISSION STATE", 1
                    )[0]
                    scheduled_observation = (
                        "kind: scheduled_observation" in current_event
                    )
                    if not scheduled_observation:
                        events.append(f"input: {current_event}")
            elif isinstance(message, AIMessage):
                text = UnitreeGo2Agent._text_content(message.content)
                if text:
                    label = (
                        "observation" if scheduled_observation else "agent"
                    )
                    events.append(f"{label}: {text}")
                for call in message.tool_calls:
                    name = call.get("name", "tool")
                    args = call.get("args", {})
                    if name == "continue_navigation":
                        continue
                    if name == "queue_task":
                        events.append(f"task: {args.get('task', '')}")
                    elif name == "set_waypoints":
                        events.append(
                            f"route: {len(args.get('waypoints', []))} waypoints; "
                            f"{args.get('strategy', '')}"
                        )
                    elif name == "finish_task":
                        events.append(f"completed: {args.get('report', '')}")
                    elif name == "cancel_navigation":
                        events.append(f"cancelled: {args.get('reason', '')}")
                    else:
                        events.append(f"called {name}")
            elif isinstance(message, ToolMessage):
                if message.status == "error":
                    events.append(f"tool error: {message.content}")
        return (
            "\n".join(f"- {event}" for event in events)
            if events
            else "No earlier conversation details."
        )

    @staticmethod
    def _without_old_images(message):
        if not isinstance(message, HumanMessage) or not isinstance(
            message.content, list
        ):
            return message
        content = []
        for part in message.content:
            if not isinstance(part, dict):
                content.append(part)
                continue
            if part.get("type") == "image_url":
                continue
            text = str(part.get("text", "")).strip()
            if text in {
                "Current front camera:",
                "Previous camera observations, newest first:",
                "Current annotated Nav2 map:",
            }:
                continue
            if text.startswith("Map legend:"):
                continue
            if part.get("type") == "text":
                part = {
                    **part,
                    "text": "\n".join(
                        line
                        for line in str(part.get("text", "")).splitlines()
                        if not line.startswith(
                            ("queued_tasks:", "paused_tasks:", "recent_events:", "battery:")
                        )
                    ),
                }
            content.append(part)
        return HumanMessage(content=content)

    @staticmethod
    def _text_content(content) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        return " ".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )

    def _battery_status(self) -> str:
        if not self.battery_url:
            return "unavailable"
        try:
            with urlopen(self.battery_url, timeout=1.0) as response:
                battery = json.load(response)
        except Exception:
            return "unavailable"
        if not battery.get("ok"):
            return "unavailable"
        return f"{battery['percentage']}%"

    @staticmethod
    def _load_system_prompt() -> str:
        prompt_dir = Path(__file__).parent
        system_prompt = (prompt_dir / "go2.prompt").read_text(encoding="utf-8")
        situation_prompt = (prompt_dir / "go2.situation.prompt").read_text(
            encoding="utf-8"
        ).strip()
        if not situation_prompt:
            return system_prompt
        return (
            f"{system_prompt.rstrip()}\n\n"
            f"## Current operating situation\n\n{situation_prompt}\n"
        )
