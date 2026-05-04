"""Tello flat inspection skill tools."""

from pathlib import Path

import cv2
from langchain_core.tools import tool  # type: ignore[import]


def create_save_artifact_photo(tello, output_dir: str | Path = "artifacts"):
    @tool
    def save_artifact_photo(artifact_name: str) -> str:
        """Save a report photo. Use only when the artifact is close and centered in the camera view."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        photo_path = output_path / f"{artifact_name}.jpg"
        frame = cv2.cvtColor(tello.get_frame_read().frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(photo_path), frame)
        return f"Saved artifact photo: {photo_path}"

    return save_artifact_photo


def create_tools(tello):
    return [create_save_artifact_photo(tello)]
