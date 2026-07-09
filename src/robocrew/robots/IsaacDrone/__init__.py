from robocrew.robots.IsaacDrone.bridge import IsaacDroneObservation, IsaacDroneRosBridge
from robocrew.robots.IsaacDrone.tools import create_set_waypoints

__all__ = [
    "IsaacDroneAgent",
    "IsaacDroneObservation",
    "IsaacDroneRosBridge",
    "create_set_waypoints",
]


def __getattr__(name):
    if name == "IsaacDroneAgent":
        from robocrew.robots.IsaacDrone.isaac_drone_agent import IsaacDroneAgent

        return IsaacDroneAgent
    raise AttributeError(name)
