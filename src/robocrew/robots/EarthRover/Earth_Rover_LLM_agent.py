"""Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import basic_augmentation
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from concurrent.futures import ThreadPoolExecutor
import requests
import time
import cv2
import base64
import numpy as np
import io, math
from PIL import Image, ImageDraw, ImageFont

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

## OPERATION SEQUENCE
1. Use turn commands with specific angles to align with target direction
2. Use move_forward with distance to approach target
3. Use curved movements for faster navigation around obstacles (one tool instead of two)
4. Use move_backward with distance to retreat if you stuck
5. Always consider terrain conditions when planning movements

## NAVIGATION RULES
- Never enter car roadway. You can use pedestrian path along the road, but never enter roadway.
- Prefer small roads or off-road over main roads.
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
            use_memory=use_memory
        )
        
        # Initialize thread pool executor for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.requests_session = requests.Session() 
        self.imagefont = ImageFont.load_default(size=30)       
        self.target_coordinates = (None, None)
        # send initial request to wake up sdk browser and avoid deadlock on first request
        self.requests_session.get("http://127.0.0.1:8000/data")

    def fetch_sensor_inputs(self):
        """Fetch all camera views from Earth Rover SDK in a single request and augment front camera."""
        # Send requests simultaneously
        future_data = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/data")
        future_front_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/front")
        future_rear_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/rear")
        future_map = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/screenshot?view_types=map")
        response_data = future_data.result()
        response_front_img = future_front_img.result()
        response_rear_img = future_rear_img.result()
        response_map = future_map.result()

        # Decode base64 image
        front_image_bytes = base64.b64decode(response_front_img.json()['front_frame'])
        
        # Convert bytes to numpy array
        nparr = np.frombuffer(front_image_bytes, np.uint8)
        front_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Apply augmentation with navigation grid
        augmented_front_image = basic_augmentation(
            front_image, 
            h_fov=self.camera_fov, 
            center_angle=0, 
        )
        augmented_front_image = self.earth_rover_front_augmentation(
            augmented_front_image,
        )  
        
        # Convert augmented image back to base64
        _, buffer = cv2.imencode('.jpg', augmented_front_image)
        front_image = base64.b64encode(buffer).decode('utf-8')\
        
        map_augmented = self.map_augmentation(
            response_map.json()['map_frame'],
            response_data.json()["orientation"],
            response_data.json()["latitude"],
            response_data.json()["longitude"],
            self.target_coordinates[0],
            self.target_coordinates[1],
        )
    
        return front_image, response_rear_img.json()['rear_frame'], map_augmented
    

    def earth_rover_front_augmentation(self, image):
        height, width = image.shape[:2]
        cv2.line(image, (int(0.26 * width), height), (int(0.47 * width), int(0.58 * height)), (0, 255, 255), 2)
        cv2.line(image, (int(0.74 * width), height), (int(0.53 * width), int(0.58 * height)), (0, 255, 255), 2)
        return image


    def map_augmentation(self, b64_img, angle, lat, lon, tlat=None, tlon=None):
        image = Image.open(io.BytesIO(base64.b64decode(b64_img))).convert("RGB")
        draw_object = ImageDraw.Draw(image)
        width, height = image.size
        center_x, center_y = width // 2, height // 2

        # center arrow (heading)
        angle_rad = math.radians(angle)
        self._draw_arrow(center_x, center_y, angle_rad, 35, (255,0,0), draw_object)

        # target arrow
        if tlat:
            radius = height // 2 - 40
            text_placement_radius = radius - 60
            bearing = self._calculate_bearing(lat, lon, tlat, tlon)
            self._draw_arrow(center_x + radius * math.cos(math.pi/2 - bearing), center_y - radius * math.sin(math.pi/2 - bearing), bearing, 60, (255, 255, 0), draw_object)    # minus after center_y because of inversion of coordinate system for images
            draw_object.text((center_x + text_placement_radius * math.cos(math.pi/2 - bearing) - 10, center_y - text_placement_radius * math.sin(math.pi/2 - bearing) - 10), "Target", fill=(100,100,0), font=self.imagefont)

        out = io.BytesIO()
        image.save(out, "JPEG", quality=75)
        return base64.b64encode(out.getvalue()).decode()
    
    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dx = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
        dy = lat2 - lat1
        return math.atan2(dx, dy)
    
    def _draw_arrow(self, position_x, position_y, angle_rad, size, color, draw):
        angle_rad = angle_rad - math.pi/2  # adjust to point upwards
        tip = (position_x+size*math.cos(angle_rad), position_y+size*math.sin(angle_rad))
        left = (position_x+size*0.6*math.cos(angle_rad+2.4), position_y+size*0.6*math.sin(angle_rad+2.4))
        right= (position_x+size*0.6*math.cos(angle_rad-2.4), position_y+size*0.6*math.sin(angle_rad-2.4))
        draw.polygon([tip,left,right], fill=color)
    
    def main_loop_content(self):
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
