"""Isaac Sim drone example using ROS2 waypoint execution."""

from robocrew.core.tools import finish_task
from robocrew.robots.IsaacDrone.bridge import IsaacDroneRosBridge
from robocrew.robots.IsaacDrone.isaac_drone_agent import IsaacDroneAgent
from robocrew.robots.IsaacDrone.tools import create_set_waypoints


drone = IsaacDroneRosBridge()

agent = IsaacDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    tools=[
        create_set_waypoints(drone),
        finish_task,
    ],
    drone=drone,
    history_len=20,
)

agent.task = "Inspect the open paved route visible on the map and report the final GPS coordinates."
agent.go()
