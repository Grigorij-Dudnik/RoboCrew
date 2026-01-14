"""Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""

from robocrew.core.LLMAgent import LLMAgent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
import requests
import time

class EarthRoverAgent(LLMAgent):
    """Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""
    
    def __init__(
        self,
        model,
        tools,
        sdk_url="http://localhost:8000",
        system_prompt=None,
        camera_fov=90,
        history_len=None,
        debug_mode=False,
        use_memory=False
    ):
        """
        Initialize Earth Rover LLM agent with SDK-based image capture.
        
        Args:
            model: name of the model to use
            tools: list of langchain tools
            sdk_url: Earth Rover SDK URL for image capture
            system_prompt: custom system prompt - optional (uses Earth Rover default if None)
            camera_fov: field of view (degrees) of your main camera
            history_len: if you want agent to have messages history cutoff
            debug_mode: enable debug mode for additional logging
            use_memory: set to True to enable long-term memory
        """
        # Use Earth Rover specific system prompt if none provided
        earth_rover_system_prompt = system_prompt or """
## EARTH ROVER SPECIFICATIONS
- Outdoor exploration robot with 4-wheel drive
- Designed for rough terrain navigation
- Basic movement capabilities: forward, backward, turning, and curved paths

## NAVIGATION RULES
- Use move_forward and move_backward for straight line movement with distance parameter
- Use turn_left and turn_right for directional changes with angle parameter
- Use go_forward_with_turning_right/left for smooth curved paths with distance parameter
- Make small movements (0.5-2m) for better control on rough terrain
- Use appropriate turn angles (15-90 degrees) for navigation
- Check path is clear before moving to avoid obstacles

## OPERATION SEQUENCE
1. Use turn commands with specific angles to align with target direction
2. Use move_forward with distance to approach target
3. Use curved movements with distance for smooth navigation around obstacles
4. Use move_backward with distance to retreat if needed
5. Always consider terrain conditions when planning movements
        """
        
        # Initialize parent class with minimal settings (no camera, sound, etc.)
        super().__init__(
            model=model,
            tools=tools,
            main_camera=None,  # We handle camera via SDK
            system_prompt=earth_rover_system_prompt,
            camera_fov=camera_fov,
            sounddevice_index=None,  # No sound input
            servo_controler=None,  # No servo control
            wakeword=None,  # No wakeword detection
            tts=False,  # No text-to-speech
            history_len=history_len,
            debug_mode=debug_mode,
            use_memory=use_memory
        )
        
        # Earth Rover specific settings
        self.sdk_url = sdk_url
        self.current_view = "front"  # Default camera view

    def fetch_camera_images_base64(self):
        """Fetch all camera views from Earth Rover SDK in a single request."""
        response = requests.get(f"{self.sdk_url}/screenshot?view_types=front,rear,map")
        return response.json()

    
    def go(self):
        """Override the go method to use Earth Rover SDK for image capture."""
        try:
            while True:
                # Fetch all camera views from Earth Rover SDK in one request
                camera_views = self.fetch_camera_images_base64()

                # Create messages for all camera views
                messages = [
                    HumanMessage(
                        content=[
                            {"type": "text", "text": "Front camera view:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{camera_views['front_frame']}"}
                            },
                            {"type": "text", "text": "Rear camera view:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{camera_views['rear_frame']}"}
                            },
                            {"type": "text", "text": "Map view:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{camera_views['map_frame']}"}
                            },
                            {"type": "text", "text": f"\n\nYour task is: '{self.task}'"},
                        ]
                    )
                ]

                # Add all messages to history
                self.message_history.extend(messages)

                # Trim history if needed
                if self.history_len and len(self.message_history) > self.history_len + 1:
                    self.message_history = [self.system_message] + self.message_history[-self.history_len:]

                # Get LLM response
                response = self.llm.invoke(self.message_history)

                # Process tool calls if any
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_response, additional_output = self.invoke_tool(tool_call)
                        self.message_history.append(tool_response)
                        if additional_output:
                            self.message_history.append(additional_output)

                # Check for new tasks from sound (if enabled)
                self.check_for_new_task()

        except KeyboardInterrupt:
            print("Earth Rover agent stopped by user")
    
