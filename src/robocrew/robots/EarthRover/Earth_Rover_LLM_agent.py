"""Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import basic_augmentation
from robocrew.robots.EarthRover.utils import calculate_robot_bearing
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import requests
import time
import cv2
import base64
import numpy as np
import io, math
import geomag


class EarthRoverAgent(LLMAgent):
    """Earth Rover specific LLM agent that inherits from base LLMAgent with SDK-based image capture."""
    
    def __init__(
        self,
        model,
        tools,
        system_prompt=None,
        camera_fov=90,
        history_len=None,
        use_memory=False,
        use_location_visualizer=False,
    ):
        prompt_path = Path(__file__).parent.parent.resolve() / "EarthRover/earth_rover.prompt"
        with open(prompt_path, "r") as f:
            system_prompt_default = f.read()
        earth_rover_system_prompt = system_prompt or system_prompt_default
        
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
        # ToDo: zmienić na 4
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.requests_session = requests.Session() 
        self.imagefont_big = ImageFont.load_default(size=30)
        self.imagefont_small = ImageFont.load_default(size=20) 
        self.task = "Follow the target. Direction to target marked with yellow arrow on the map."      
        self.waypoints = []
        self.use_location_visualizer = use_location_visualizer

        # send initial request to wake up sdk browser and avoid deadlock on first request. Avoid sending for testing purposes.
        if __name__ != "__main__":
            init_request_response = self.requests_session.get("http://127.0.0.1:8000/data")
            if init_request_response.status_code != 200:
                raise ConnectionError("Failed to connect to Earth Rover SDK. Ensure the SDK is running \"hypercorn main:app\", and robot is enabled.")
            self.magnetic_declination = geomag.declination(dlat=init_request_response.json()["latitude"], dlon=init_request_response.json()["longitude"])
            if init_request_response.json()["latitude"] == 1000:
                self.magnetic_declination = 0
                print("No connection to GPS. Place your robot outdoors.")


    def fetch_sensor_inputs(self):
        """Fetch all camera views from Earth Rover SDK in a single request and augment front camera."""
        # Send requests simultaneously
        start = time.perf_counter()
        future_data = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/data")
        future_front_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/front")
        future_rear_img = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/v2/rear")
        future_map = self.executor.submit(self.requests_session.get, "http://127.0.0.1:8000/screenshot?view_types=map")
        response_data = future_data.result()
        response_front_img = future_front_img.result()
        response_rear_img = future_rear_img.result()
        response_map = future_map.result()
        end = time.perf_counter()
        print(f"Sensor data fetch time: {end - start} seconds.")

        latitude = response_data.json()["latitude"]
        longitude = response_data.json()["longitude"]

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
        #augmented_front_image = cv2.resize(augmented_front_image, (512, 288))
        
        # Convert augmented image back to base64
        _, buffer = cv2.imencode('.jpg', augmented_front_image)
        front_image = base64.b64encode(buffer).decode('utf-8')

        print(f"accel: {response_data.json()['accels']}, magnet: {response_data.json()['mags']}")
        # Caution: use only when robot stays steady. Function includes Earth acceleration compensation - so avoid artificial accelerations.
        robot_bearing = calculate_robot_bearing(
            response_data.json()["accels"],
            response_data.json()["mags"],
            declination=self.magnetic_declination,
        )
        print(f"Robot Bearing: {robot_bearing}")
        map_augmented = self.map_augmentation(
            response_map.json()['map_frame'],
            robot_bearing,
            latitude,
            longitude,
            self.waypoints[0][0],
            self.waypoints[0][1],
        )
    
        return front_image, response_rear_img.json()['rear_frame'], map_augmented, (latitude, longitude)
    

    def earth_rover_front_augmentation(self, image):
        height, width = image.shape[:2]
        # path lines
        cv2.line(image, (int(0.26 * width), height), (int(0.48 * width), int(0.56 * height)), (0, 255, 255), 2)
        cv2.line(image, (int(0.74 * width), height), (int(0.52 * width), int(0.56 * height)), (0, 255, 255), 2)

        # meters markers
        cv2.line(image, (int(0.60 * width), int(0.75 * height)), (int(0.64 * width), int(0.75 * height)), (0, 255, 255), 2)
        cv2.putText(image, "1m", (int(0.65 * width), int(0.74 * height)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.line(image, (int(0.53 * width), int(0.61 * height)), (int(0.56 * width), int(0.61 * height)), (0, 255, 255), 2)
        cv2.putText(image, "2m", (int(0.58 * width), int(0.60 * height)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.line(image, (int(0.51 * width), int(0.56 * height)), (int(0.53 * width), int(0.56 * height)), (0, 255, 255), 2)
        cv2.putText(image, "3m", (int(0.54 * width), int(0.55 * height)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return image


    def map_augmentation(self, b64_img, angle, lat, lon, tlat=None, tlon=None):
        image = Image.open(io.BytesIO(base64.b64decode(b64_img))).convert("RGB")
        width, height = image.size
        center_x, center_y = width // 2, height // 2

        # rotate image according to heading
        image = image.rotate(-angle)

        draw_object = ImageDraw.Draw(image)

        # center arrow (heading)
        self._draw_arrow(center_x, center_y, 0, 35, (255,0,0), draw_object)
        draw_object.text((center_x - 120, center_y - 110), "<= Left", fill=(150,0,0), font=self.imagefont_big)
        draw_object.text((center_x + 30, center_y - 110), "Right =>", fill=(150,0,0), font=self.imagefont_big)
        draw_object.line((center_x, 0, center_x, center_y), fill=(225,0,0), width=1)

        # target arrow
        if tlat:
            radius = height // 2 - 40
            text_placement_radius = radius - 60
            bearing = self._calculate_target_bearing(lat, lon, tlat, tlon)
            relative_bearing = bearing - math.radians(angle)
            self._draw_arrow(center_x + radius * math.cos(math.pi/2 - relative_bearing), center_y - radius * math.sin(math.pi/2 - relative_bearing), relative_bearing, 60, (255, 255, 0), draw_object)    # minus after center_y because of inversion of coordinate system for images
            draw_object.text((center_x + text_placement_radius * math.cos(math.pi/2 - relative_bearing) - 10, center_y - text_placement_radius * math.sin(math.pi/2 - relative_bearing) - 10), "Target", fill=(100,100,0), font=self.imagefont_big)

        out = io.BytesIO()

        #image = image.resize((400, 400))
        image.save(out, "JPEG", quality=75)
        return base64.b64encode(out.getvalue()).decode()
    
    def _calculate_target_bearing(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dx = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
        dy = lat2 - lat1
        return math.atan2(dx, dy)
    
    def _draw_arrow(self, position_x, position_y, angle_rad, size, color, draw):
        angle_rad = angle_rad - math.pi/2  # adjust to point upwards
        tip = (position_x+size*math.cos(angle_rad), position_y+size*math.sin(angle_rad))
        left = (position_x+size*0.6*math.cos(angle_rad+2.4), position_y+size*0.6*math.sin(angle_rad+2.4))
        right= (position_x+size*0.6*math.cos(angle_rad-2.4), position_y+size*0.6*math.sin(angle_rad-2.4))
        tip_background = (position_x+size*1.1*math.cos(angle_rad), position_y+size*1.1*math.sin(angle_rad))
        left_background = (position_x+size*0.65*math.cos(angle_rad+2.4), position_y+size*0.65*math.sin(angle_rad+2.4))
        right_background= (position_x+size*0.65*math.cos(angle_rad-2.4), position_y+size*0.65*math.sin(angle_rad-2.4))
        
        draw.polygon([tip_background,left_background,right_background], fill=(0,0,0))
        draw.polygon([tip,left,right], fill=color)

    def send_location_to_visualizer(self, latitude, longitude):
        """Sends current location to map visualizer running in Flask app."""
        self.executor.submit(
            requests.post, "http://127.0.0.1:5000/update_location",
            json={"lat": latitude, "lon": longitude},
            timeout=0.5
            )
        
    def check_waypoint_closiness(self, latitude, longitude):
        """Checks if current location is in 20m range to the next waypoint and removes it from the list if so."""
        print(f"latitude: {latitude}, target latitude: {self.waypoints[0][0]}, longitude: {longitude}, target longitude: {self.waypoints[0][1]}")
        if abs(latitude - self.waypoints[0][0]) < 0.00030 and abs(longitude - self.waypoints[0][1]) < 0.00018:
            print("Waypoint reached!")
            self.waypoints.pop(0)
            if not self.waypoints:
                print("All waypoints reached.")

    
    def main_loop_content(self):
        # Fetch all camera views from Earth Rover SDK in one request
        front_frame, rear_frame, map_frame, (latitude, longitude) = self.fetch_sensor_inputs()
        self.check_waypoint_closiness(latitude, longitude)
        if self.use_location_visualizer:
            self.send_location_to_visualizer(latitude, longitude)

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
        start = time.perf_counter()
        response = self.llm.invoke(self.message_history)
        llm_time = time.perf_counter() - start
        print(f"LLM response time: {llm_time} seconds.")
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


if __name__ == "__main__":
    # test image augmentation for map
    agent = EarthRoverAgent(
        model="google_genai:gemini-3-flash-preview",
        tools=[],
        camera_fov=90,
    )
    # read image
    map_image_path = "map.png"
    with open(map_image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode()
    augmented_map = agent.map_augmentation(
        b64_img,
        angle=45,
        lat=50.301,
        lon=18.672,
        tlat=50.302,
        tlon=18.674,
    )
    # save augmented image
    with open("augmented_map.jpg", "wb") as f:
        f.write(base64.b64decode(augmented_map))
    
    # test visualiser
    agent.use_location_visualizer = True
    agent.send_location_to_visualizer(50.301, 18.672)