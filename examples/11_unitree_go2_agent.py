import os
from queue import Queue

from robocrew.robots.UnitreeGo2.mission_state import MissionState
from robocrew.robots.UnitreeGo2.nav2_bridge import UnitreeGo2NavBridge
from robocrew.robots.UnitreeGo2.telegram_gateway import TelegramGateway
from robocrew.robots.UnitreeGo2.unitree_go2_agent import UnitreeGo2Agent


event_queue = Queue()
mission_state = MissionState()
bridge = UnitreeGo2NavBridge(event_queue)
telegram = TelegramGateway(
    token=os.environ["TELEGRAM_BOT_TOKEN"],
    chat_id=int(os.environ["TELEGRAM_CHAT_ID"]),
    event_queue=event_queue,
)
agent = UnitreeGo2Agent(
    model="google_genai:gemini-robotics-er-2-preview",
    bridge=bridge,
    mission_state=mission_state,
    event_queue=event_queue,
    telegram_gateway=telegram,
)
agent.go()
