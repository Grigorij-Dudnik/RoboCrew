"""Tello specific LLM agent."""

import base64
import logging
import time
from pathlib import Path

import av
import cv2
import numpy as np
from djitellopy import Tello
from langchain_core.messages import HumanMessage

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import basic_augmentation

av.logging.set_level(av.logging.PANIC)
Tello.LOGGER.setLevel(logging.WARNING)
logging.getLogger("djitellopy").setLevel(logging.WARNING)
logging.getLogger("djitellopy").propagate = False


class TelloAgent(LLMAgent):
    """LLMAgent child for the Tello drone."""

    def __init__(
        self,
        model: str,
        tools: list,
        tello: Tello,
        system_prompt: str | None = None,
        history_len: int | None = None,
        skills: list | None = None,
    ):
        super().__init__(
            model=model,
            tools=tools,
            main_camera=None,
            system_prompt=system_prompt or Path(__file__).with_name("tello.prompt").read_text(encoding="utf-8"),
            camera_fov=82.5,
            history_len=history_len,
            skills=skills,
            skills_dir=Path(__file__).with_name("skills"),
            skill_context=tello,
        )
        self.tello = tello

    def fetch_camera_images_base64(self):
        if not self.tello.stream_on:
            self.tello.streamon()

        frame_reader = self.tello.get_frame_read()
        frame = frame_reader.frame
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if frame is not None and frame.size and np.any(frame):
                break
            time.sleep(0.1)
            frame = frame_reader.frame

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        image = basic_augmentation(frame, h_fov=self.camera_fov, navigation_mode=self.navigation_mode)
        return [base64.b64encode(cv2.imencode(".jpg", image)[1]).decode("utf-8")]

    def main_loop_content(self):
        camera_images = self.fetch_camera_images_base64()
        telemetry = (
            f"Current flight height: {self.tello.get_distance_tof()} cm\n"
            f"Yaw: {self.tello.get_yaw()} degrees"
        )
        content = [
            {"type": "text", "text": "Main camera view:"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{camera_images[0]}"},
            },
            {"type": "text", "text": f"\n\n{telemetry}"},
            {"type": "text", "text": f"\n\nYour task is: '{self.task}'"},
        ]

        self.message_history.append(HumanMessage(content))
        response = self.llm.invoke(self.message_history)
        print(response.content)

        usage_meta = getattr(response, "usage_metadata", None) or {}
        reasoning_tokens = usage_meta.get("output_token_details", {}).get("reasoning", 0)
        if reasoning_tokens:
            print(f"[thinking: {reasoning_tokens} tokens]")

        for tool_call in response.tool_calls:
            print(f"Calling {tool_call['name']} with {tool_call['args']} args")

        self.message_history.append(response)
        if self.history_len:
            self.cut_off_context(self.history_len)

        for tool_call in response.tool_calls:
            tool_response, additional_response = self.invoke_tool(tool_call)
            self.message_history.append(tool_response)
            if additional_response:
                self.message_history.append(additional_response)
            if tool_call["name"] == "finish_task":
                report = tool_call["args"].get("report", "Task finished")
                self.task = None
                print(f"Task finished: {report}")
                return report
            
    def go(self):
        print(f"Battery: {self.tello.get_battery()}%")
        return super().go()

    def cleanup(self):
        self.tello.end()
