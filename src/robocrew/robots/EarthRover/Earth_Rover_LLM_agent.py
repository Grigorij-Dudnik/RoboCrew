"""Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import augment_image
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from concurrent.futures import ThreadPoolExecutor
import requests
import time
import cv2
import base64
import numpy as np

class EarthRoverAgent(LLMAgent):
    """Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""
    
    def __init__(
        self,
        model,
        tools,
        system_prompt=None,
        camera_fov=90,
        history_len=None,
        use_memory=False
    ):
        """
        Initialize Earth Rover LLM agent with SDK-based image capture.
        
        Args:
            model: name of the model to use
            tools: list of langchain tools
            system_prompt: custom system prompt - optional (uses Earth Rover default if None)
            camera_fov: field of view (degrees) of your main camera
            history_len: if you want agent to have messages history cutoff
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
            sounddevice_index_or_alias=None,  # No sound input
            servo_controler=None,  # No servo control
            wakeword=None,  # No wakeword detection
            tts=False,  # No text-to-speech
            history_len=history_len,
            use_memory=use_memory
        )
        
        # Initialize thread pool executor for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Optional: Use a session to reuse TCP connections (faster)
        self.requests_session = requests.Session()        

    def fetch_sensor_inputs(self):
        """Fetch all camera views from Earth Rover SDK in a single request and augment front camera."""
        print(time.perf_counter())
        # Send requests simultaneously
        future_data = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/data")
        future_front_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/front")
        future_rear_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/rear")
        future_map = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/screenshot?view_types=map")
        response_data = future_data.result()
        response_front_img = future_front_img.result()
        response_rear_img = future_rear_img.result()
        response_map = future_map.result()

        print(time.perf_counter())
        print(response_front_img.json().keys())
        
        a = time.perf_counter()
        # Decode base64 image
        front_image_bytes = base64.b64decode(response_front_img.json()['front_frame'])
        
        # Convert bytes to numpy array
        nparr = np.frombuffer(front_image_bytes, np.uint8)
        front_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Apply augmentation with navigation grid
        augmented_front_image = augment_image(
            front_image, 
            h_fov=self.camera_fov, 
            center_angle=0, 
            navigation_mode=None
        )
        
        # Convert augmented image back to base64
        _, buffer = cv2.imencode('.jpg', augmented_front_image)
        front_image = base64.b64encode(buffer).decode('utf-8')
        print(f"Image augmentation took {time.perf_counter() - a:.2f} seconds.")
    
        return front_image, response_rear_img.json()['rear_frame'], response_map.json()['map_frame']

    
    def go(self):
        """Override the go method to use Earth Rover SDK for image capture."""
        try:
            while True:
                # Fetch all camera views from Earth Rover SDK in one request
                front_frame, rear_frame, map_frame = self.fetch_sensor_inputs()

                # Create messages for all camera views
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": "Front camera view:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{front_frame}"}
                        },
                        {"type": "text", "text": "Rear camera view:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{rear_frame}"}
                        },
                        {"type": "text", "text": "Map view:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{map_frame}"}
                        },
                        {"type": "text", "text": f"\n\nYour task is: '{self.task}'"},
                    ]
                )

                self.message_history.append(message)
                response = self.llm.invoke(self.message_history)
                print(response.content)
                print(response.tool_calls)
                
                self.message_history.append(response)
                if self.history_len:
                    self.cut_off_context(self.history_len)
                # execute tool
                for tool_call in response.tool_calls:
                    tool_response, additional_response = self.invoke_tool(tool_call)
                    self.message_history.append(tool_response)
                    if additional_response:
                        self.message_history.append(additional_response)
                    # Special handling for special tools
                    if tool_call["name"] == "finish_task":
                        print("Task finished, going idle.")
                        return "Task finished, going idle."


        except KeyboardInterrupt:
            print("Earth Rover agent stopped by user")
    
