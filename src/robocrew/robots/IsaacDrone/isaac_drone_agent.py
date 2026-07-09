"""Isaac Sim drone specific LLM agent."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage

from robocrew.core.LLMAgent import LLMAgent


class IsaacDroneAgent(LLMAgent):
    """LLMAgent child for a ROS2-driven Isaac Sim drone."""

    def __init__(
        self,
        model: str,
        tools: list | None = None,
        drone=None,
        system_prompt: str | None = None,
        history_len: int | None = None,
    ):
        super().__init__(
            model=model,
            tools=tools or [],
            main_camera=None,
            system_prompt=system_prompt or Path(__file__).with_name("isaac_drone.prompt").read_text(encoding="utf-8"),
            camera_fov=90,
            history_len=history_len,
        )
        self.drone = drone

    def main_loop_content(self):
        observation = self.drone.get_observation()
        content = [{"type": "text", "text": "Front camera view:"}]
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{observation.front_image_b64}"}}
        )
        content.append({"type": "text", "text": "\n\nMap view:"})
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{observation.map_image_b64}"}}
        )
        content.append(
            {
                "type": "text",
                "text": (
                    f"\n\nCurrent GPS/location: {observation.gps}\n"
                    f"Height: {observation.height_m} m"
                ),
            }
        )
        if self.task:
            content.append({"type": "text", "text": f"\n\nYour task is: '{self.task}'"})

        return self.invoke_llm_with_message(HumanMessage(content))
