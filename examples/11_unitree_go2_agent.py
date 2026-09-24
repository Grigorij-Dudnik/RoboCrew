import os
from queue import Empty, Queue

from robocrew.core.tools import finish_task
from robocrew.robots.UnitreeGo2.mission_state import MissionState
from robocrew.robots.UnitreeGo2.nav2_bridge import UnitreeGo2NavBridge
from robocrew.robots.UnitreeGo2.telegram_gateway import TelegramGateway
from robocrew.robots.UnitreeGo2.tools import (
    create_cancel_navigation,
    create_plan_tasks,
    create_set_waypoints,
    continue_navigation,
)
from robocrew.robots.UnitreeGo2.unitree_go2_agent import UnitreeGo2Agent


event_queue = Queue()
mission_state = MissionState()
bridge = UnitreeGo2NavBridge(event_queue)
telegram = TelegramGateway(
    token=os.environ["TELEGRAM_BOT_TOKEN"],
    chat_id=int(os.environ["TELEGRAM_CHAT_ID"]),
    event_queue=event_queue,
)
tools = [
    create_plan_tasks(bridge, mission_state),
    create_set_waypoints(bridge, mission_state),
    finish_task,
]
active_route_tools = [
    continue_navigation,
    create_cancel_navigation(bridge, mission_state),
]
agent = UnitreeGo2Agent(
    model="google_genai:gemini-robotics-er-2-preview",
    bridge=bridge,
    mission_state=mission_state,
    event_queue=event_queue,
    telegram_gateway=telegram,
    tools=tools,
)

telegram.start()
try:
    while True:
        # A real event wakes the loop immediately; Empty means five quiet
        # seconds passed, so it is time for a scheduled observation.
        try:
            event = event_queue.get(timeout=5.0)
        except Empty:
            if mission_state.active_task is None and not bridge.navigation_active:
                continue
            event = {"kind": "scheduled_observation"}
        agent.bind_tools(
            tools + active_route_tools if bridge.navigation_active else tools
        )
        agent.process_event(event)
except KeyboardInterrupt:
    pass
finally:
    agent.cleanup()
