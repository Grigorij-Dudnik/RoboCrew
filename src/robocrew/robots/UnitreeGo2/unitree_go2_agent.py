"""RoboCrew agent for a Nav2-controlled Unitree Go2."""

from __future__ import annotations

import threading
from dataclasses import asdict, is_dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.tools import finish_task
from robocrew.robots.UnitreeGo2.mission_state import MissionState
from robocrew.robots.UnitreeGo2.nav2_bridge import (
    NavigationEvent,
    UnitreeGo2NavBridge,
)
from robocrew.robots.UnitreeGo2.telegram_gateway import (
    TelegramEvent,
    TelegramGateway,
)
from robocrew.robots.UnitreeGo2.tools import (
    create_cancel_navigation,
    create_queue_task,
    create_set_waypoints,
)

RECENT_MESSAGE_LIMIT = 8
OBSERVATION_INTERVAL = 10.0
SUMMARY_INTERVAL = 10
SUMMARY_PROMPT = """Rewrite the previous summary and new conversation into a
single concise rolling summary of at most eight bullets. Preserve user goals
and preferences, completed or cancelled task outcomes, unresolved work, and
important failures or safety facts. Remove routine observations, image
descriptions, waypoint details, repeated progress, and tool plumbing. Replace
the previous summary instead of appending to it. Return only the summary."""


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
    ):
        if tools is None:
            tools = [
                create_queue_task(bridge, mission_state),
                create_set_waypoints(bridge, mission_state),
                create_cancel_navigation(bridge, mission_state),
                finish_task,
            ]
        super().__init__(
            model=model,
            tools=tools,
            main_camera=None,
            name=name,
            system_prompt=system_prompt or self._load_system_prompt(),
            history_len=None,
        )
        self.bridge = bridge
        self.mission_state = mission_state
        self.event_queue = event_queue
        self.telegram_gateway = telegram_gateway
        self._current_event: Any = None
        self._summary_llm = init_chat_model(model)
        self._conversation_summary = ""
        self._steps_since_summary = 0
        self._summary_in_flight = False
        self._summary_results = Queue()

    def go(self):
        try:
            self.telegram_gateway.start()
            while True:
                self._apply_summary_result()
                timeout = (
                    OBSERVATION_INTERVAL
                    if self.mission_state.active_task
                    or self.bridge.navigation_active
                    else 0.5
                )
                try:
                    trigger = self.event_queue.get(timeout=timeout)
                except Empty:
                    if (
                        self.mission_state.active_task is None
                        and not self.bridge.navigation_active
                    ):
                        continue
                    trigger = {
                        "source": "observation_timer",
                        "kind": "scheduled_observation",
                    }

                self._update_mission_state(trigger)
                self._current_event = trigger
                history_start = len(self.message_history)
                report = self.main_loop_content()
                if report is not None:
                    self._handle_task_report(report)
                else:
                    self._reply_to_telegram(history_start)
                self._steps_since_summary += 1
                self._start_summary_if_due()
        except KeyboardInterrupt:
            print("Interrupted by user, shutting down.")
        finally:
            self.cleanup()

    def main_loop_content(self):
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
                    f"{observation.waypoint_count}"
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
        """Project live history without stale observations or image payloads."""
        self._apply_summary_result()
        history = list(self.message_history[1:])
        if not history:
            return [self.system_message]

        messages = [self.system_message]
        if self._conversation_summary:
            messages.append(
                HumanMessage(
                    "Earlier conversation summary:\n"
                    f"{self._conversation_summary}"
                )
            )
        for index, message in enumerate(history):
            is_newest = index == len(history) - 1
            messages.append(
                message if is_newest else self._project_previous_message(message)
            )
        return messages

    def cleanup(self):
        self.telegram_gateway.stop()
        self.bridge.close()
        super().cleanup()

    def _update_mission_state(self, event: Any) -> None:
        if isinstance(event, NavigationEvent):
            self.mission_state.record_navigation_result(event)

    def _handle_task_report(self, report: str) -> None:
        """Mirror RoboCrew's completed task into mission state and Telegram."""
        next_task = self.mission_state.finish_active_task(report)
        self.telegram_gateway.send_message(report)
        if next_task:
            self.event_queue.put(
                {
                    "source": "mission",
                    "kind": "task_activated",
                    "text": next_task.text,
                }
            )

    def _reply_to_telegram(self, history_start: int) -> None:
        messages = self.message_history[history_start:]
        response = next(
            (
                message
                for message in messages
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if response is None:
            return
        text = self._text_content(response.content).strip()
        if text:
            self.telegram_gateway.send_message(text)

    def _event_to_text(self, event: Any) -> str:
        if isinstance(event, TelegramEvent):
            return f"kind: telegram_request\ntext: {event.text}"
        if is_dataclass(event):
            payload = asdict(event)
        else:
            payload = event
        return "\n".join(f"{key}: {value}" for key, value in payload.items())

    @staticmethod
    def _include_matching_tool_call(history: list, start: int) -> int:
        """Do not send a ToolMessage without the AI tool call it answers."""
        while start > 0 and isinstance(history[start], ToolMessage):
            tool_call_id = history[start].tool_call_id
            start -= 1
            candidate = history[start]
            if isinstance(candidate, AIMessage) and any(
                call.get("id") == tool_call_id
                for call in candidate.tool_calls
            ):
                break
        return start

    def _start_summary_if_due(self) -> None:
        if (
            self._summary_in_flight
            or self._steps_since_summary < SUMMARY_INTERVAL
        ):
            return
        history = list(self.message_history[1:])
        start = max(0, len(history) - RECENT_MESSAGE_LIMIT)
        start = self._include_matching_tool_call(history, start)
        if start == 0:
            return

        messages = history[:start]
        summary_input = self._messages_to_summary_text(messages)
        previous_summary = self._conversation_summary
        self._summary_in_flight = True
        self._steps_since_summary = 0
        threading.Thread(
            target=self._run_summary,
            args=(len(messages), previous_summary, summary_input),
            name="go2-context-summary",
            daemon=True,
        ).start()

    def _run_summary(
        self,
        message_count: int,
        previous_summary: str,
        summary_input: str,
    ) -> None:
        try:
            response = self._summary_llm.invoke(
                [
                    SystemMessage(SUMMARY_PROMPT),
                    HumanMessage(
                        "PREVIOUS SUMMARY\n"
                        f"{previous_summary or 'None'}\n\n"
                        "NEW CONVERSATION\n"
                        f"{summary_input}"
                    ),
                ],
                config=self.trace_config(f"{self.name} / summarize_context"),
            )
            summary = self._text_content(response.content).strip()
            if not summary:
                raise RuntimeError("context summarizer returned no text")
            self._summary_results.put((message_count, summary, None))
        except Exception as exc:
            self._summary_results.put((message_count, None, str(exc)))

    def _apply_summary_result(self) -> None:
        try:
            message_count, summary, error = self._summary_results.get_nowait()
        except Empty:
            return
        self._summary_in_flight = False
        if error:
            print(f"Context summarization failed: {error}")
            return
        self._conversation_summary = summary
        del self.message_history[1 : 1 + message_count]

    @classmethod
    def _messages_to_summary_text(cls, messages: list) -> str:
        entries = []
        for message in messages:
            message = cls._project_previous_message(message)
            if isinstance(message, HumanMessage):
                text = cls._text_content(message.content).strip()
                if text:
                    entries.append(f"human: {text}")
            elif isinstance(message, AIMessage):
                text = cls._text_content(message.content).strip()
                if text:
                    entries.append(f"agent: {text}")
                for call in message.tool_calls:
                    entries.append(f"called: {call.get('name', 'tool')}")
            elif isinstance(message, ToolMessage):
                entries.append(f"tool result: {message.content}")
        return (
            "\n".join(f"- {entry}" for entry in entries)
            if entries
            else "No new conversation details."
        )

    @classmethod
    def _project_previous_message(cls, message):
        if not isinstance(message, HumanMessage):
            return message
        text = cls._text_content(message.content)
        event = text.split("\n\nCURRENT MISSION STATE", 1)[0].strip()
        return HumanMessage(content=event)

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

    @staticmethod
    def _load_system_prompt() -> str:
        return Path(__file__).with_name("go2.prompt").read_text(
            encoding="utf-8"
        )
