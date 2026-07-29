"""Direct RoboCrew connector for a real ArduPilot drone."""

from __future__ import annotations

import asyncio
import base64
import glob
import importlib.util
import io
import math
import platform
import threading

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan
from mavsdk.offboard import VelocityBodyYawspeed
from PIL import ImageDraw
from staticmap3 import StaticMap

from robocrew.robots.WaypointDrone.drone_bridge_common import DroneBridge, DroneObservation


if platform.machine() == "aarch64" and (cv2_path := next(glob.iglob("/usr/lib/python3/dist-packages/cv2*.so"), None)):
    cv2_spec = importlib.util.spec_from_file_location("cv2", cv2_path)
    cv2 = importlib.util.module_from_spec(cv2_spec)
    cv2_spec.loader.exec_module(cv2)
else:
    import cv2

SERIAL_ADDRESS = "serial:///dev/ttyTHS1:921600"
FRONT_SENSOR_ID = 0
DOWN_SENSOR_ID = 1
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
MISSION_SPEED_M_S = 5.0
MAP_SIZE_PX = 768
MAP_ZOOM = 16
MAP_SPAN_AT_EQUATOR_M = 156543.03392 / 2**MAP_ZOOM * MAP_SIZE_PX
STOP_SETPOINT = VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)


def _camera_pipeline(sensor_id: int) -> str:
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1,format=NV12 ! "
        f"nvvidconv ! video/x-raw,width={CAMERA_WIDTH},height={CAMERA_HEIGHT},format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! appsink drop=1 max-buffers=1 sync=false"
    )


def _camera_jpeg(camera) -> str:
    _, frame = camera.read()
    jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
    return base64.b64encode(jpeg).decode()


def _map_image(static_map, latitude: float, longitude: float) -> str:
    image = static_map.render(zoom=MAP_ZOOM, center=(longitude, latitude))
    ImageDraw.Draw(image).text((8, image.height - 18), "© OpenStreetMap contributors", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode()


def _mission_item(waypoint, altitude_m: float, fly_through: bool):
    nan = float("nan")
    return MissionItem(
        float(waypoint["lat"]), float(waypoint["lon"]),
        float(altitude_m), MISSION_SPEED_M_S,
        fly_through,
        nan, nan,
        MissionItem.CameraAction.NONE,
        *([nan] * 5),
        MissionItem.VehicleAction.NONE,
    )


class MavsdkDroneBridge(DroneBridge):
    """Connect RoboCrew directly to a real drone through MAVSDK."""

    def __init__(self):
        super().__init__()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._schedule(self._connect()).result()

    def _schedule(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    async def _connect(self) -> None:
        self.drone = System()
        await self.drone.connect(system_address=SERIAL_ADDRESS)
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                break
        await self.drone.telemetry.set_rate_position(1.0)
        await self.drone.telemetry.set_rate_attitude_euler(1.0)
        self.front_camera = cv2.VideoCapture(_camera_pipeline(FRONT_SENSOR_ID), cv2.CAP_GSTREAMER)
        self.down_camera = cv2.VideoCapture(_camera_pipeline(DOWN_SENSOR_ID), cv2.CAP_GSTREAMER)
        self.static_map = StaticMap(MAP_SIZE_PX, MAP_SIZE_PX)
        await self.drone.offboard.set_velocity_body(STOP_SETPOINT)
        await self._capture_observation()

    def set_waypoints(self, waypoints, altitude_m=None, strategy=None):
        return self._submit(self._fly_route, waypoints, altitude_m)

    def takeoff(self) -> None:
        self._schedule(self._takeoff()).result()

    def move_forward(self, distance_meters: float):
        return self._submit(self._move_body, float(distance_meters), 1.0, 0.0)

    def turn_left(self, angle_degrees: float):
        return self._submit(self._move_body, float(angle_degrees) / 30.0, 0.0, -30.0)

    def turn_right(self, angle_degrees: float):
        return self._submit(self._move_body, float(angle_degrees) / 30.0, 0.0, 30.0)

    def land(self):
        return self._submit(self._land)

    def stop_route(self) -> None:
        self._schedule(self._stop_route())

    def set_navigation_mode(self, navigation_mode: str) -> None:
        operation = self.drone.offboard.start() if navigation_mode == "precision" else self.drone.offboard.stop()
        self._schedule(operation).result()
        super().set_navigation_mode(navigation_mode)

    def _submit(self, operation, *arguments):
        self._start_command()
        self._schedule(operation(*arguments))

    async def _capture_observation(self, route_state="idle") -> None:
        position, attitude = await asyncio.gather(
            anext(self.drone.telemetry.position()), anext(self.drone.telemetry.attitude_euler()),
        )
        latitude = position.latitude_deg
        self._store_observation(DroneObservation(
            front_image_b64=_camera_jpeg(self.front_camera),
            down_image_b64=_camera_jpeg(self.down_camera),
            map_image_b64=_map_image(self.static_map, latitude, position.longitude_deg),
            map_span_m=MAP_SPAN_AT_EQUATOR_M * math.cos(math.radians(latitude)),
            gps={"lat": latitude, "lon": position.longitude_deg, "alt": position.absolute_altitude_m},
            height_m=position.relative_altitude_m,
            yaw_rad=math.radians(90.0 - attitude.yaw_deg),
            route_state=route_state,
        ))

    async def _fly_route(self, waypoints, altitude_m) -> None:
        if altitude_m is None:
            altitude_m = self.latest_observation.height_m
        items = [_mission_item(point, altitude_m, index < len(waypoints) - 1) for index, point in enumerate(waypoints)]
        await self.drone.mission.set_return_to_launch_after_mission(False)
        await self.drone.mission.upload_mission(MissionPlan(items))
        await self.drone.mission.start_mission()
        await self._capture_observation("executing")
        while not await self.drone.mission.is_mission_finished():
            await asyncio.sleep(1)
            if not self.route_active:
                return
            await self._capture_observation("executing")
        await self._capture_observation("completed")

    async def _takeoff(self) -> None:
        target_altitude = await self.drone.action.get_takeoff_altitude()
        await self.drone.action.arm()
        await self.drone.action.takeoff()
        async for position in self.drone.telemetry.position():
            if position.relative_altitude_m >= target_altitude - 0.5:
                break
        await self._capture_observation()

    async def _land(self) -> None:
        await self.drone.action.land()
        async for is_in_air in self.drone.telemetry.in_air():
            if not is_in_air:
                break
        await self._capture_observation("completed")

    async def _stop_route(self) -> None:
        await self.drone.mission.pause_mission()
        await self.drone.action.hold()
        await self._capture_observation("stopped")

    async def _move_body(self, duration, forward, yaw_speed) -> None:
        await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(forward, 0.0, 0.0, yaw_speed))
        await asyncio.sleep(duration)
        await self.drone.offboard.set_velocity_body(STOP_SETPOINT)
        await self._capture_observation("completed")
