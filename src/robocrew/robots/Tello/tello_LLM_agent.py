"""Tello specific LLM agent."""

import base64
from pathlib import Path

import cv2
from djitellopy import Tello
from langchain_core.messages import HumanMessage

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import basic_augmentation


class TelloAgent(LLMAgent):
    """LLMAgent child for the Tello drone."""

    def __init__(
        self,
        model: str,
        tools: list,
        tello: Tello,
    ):
        super().__init__(
            model=model,
            tools=tools,
            main_camera=tello,
            system_prompt=Path(__file__).with_name("tello.prompt").read_text(encoding="utf-8"),
            camera_fov=82,
        )

    def fetch_camera_images_base64(self):
        if not self.main_camera.stream_on:
            self.main_camera.streamon()

        frame = cv2.cvtColor(self.main_camera.get_frame_read().frame, cv2.COLOR_RGB2BGR)
        image = basic_augmentation(frame, h_fov=self.camera_fov, navigation_mode=self.navigation_mode)
        return [base64.b64encode(cv2.imencode(".jpg", image)[1]).decode("utf-8")]

    def main_loop_content(self):
        camera_images = self.fetch_camera_images_base64()
        telemetry = (
            f"Current flight height: {self.main_camera.get_height()} cm\n"
            f"Yaw: {self.main_camera.get_yaw()} degrees"
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
        try:
            return super().go()
        finally:
            self.main_camera.end()
