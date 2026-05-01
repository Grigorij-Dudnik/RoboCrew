"""Tello specific LLM agent."""

import base64
from pathlib import Path

import cv2
from djitellopy import Tello

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

        frame = self.main_camera.get_frame_read().frame
        image = basic_augmentation(frame, h_fov=self.camera_fov, navigation_mode=self.navigation_mode)
        return [base64.b64encode(cv2.imencode(".jpg", image)[1]).decode("utf-8")]

    def go(self):
        try:
            return super().go()
        finally:
            self.main_camera.end()
