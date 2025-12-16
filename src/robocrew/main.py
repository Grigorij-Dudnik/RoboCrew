import signal
import sys
import threading
import time
import os
import logging
import subprocess
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from flask import Flask

from robocrew.config import WEB_PORT
from robocrew.core.state import state
from robocrew.core.movement import movement_loop
from robocrew.web.app import create_app
from robocrew.core.robot_system import RobotSystem
from robocrew.core.navigation_agent import NavigationAgent
from robocrew.robots.XLeRobot.tools import (
    create_move_forward, 
    create_move_backward, 
    create_turn_left, 
    create_turn_right, 
    create_look_around,
    create_end_task,
    create_enable_precision_mode,
    create_disable_precision_mode,
    create_save_note
)

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def agent_loop():
    logger.info("AI Agent loop started")
    while state.running:
        if state.ai_enabled and state.agent:
            try:
                status = state.agent.step()
                state.add_ai_log(status)
            except Exception as e:
                logger.error(f"Agent step error: {e}")
                state.add_ai_log(f"Error: {e}")
                state.ai_enabled = False 
        time.sleep(0.1)


def cleanup(signum=None, frame=None):
    print("\n🛑 Shutting down...")
    state.running = False
    
    if state.robot_system:
        state.robot_system.cleanup()
    
    sys.exit(0)

def main():
    print("=" * 50)
    print("🤖 ARCS System Starting")
    print("=" * 50)
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    print("🔧 Initializing Robot System...")
    robot = RobotSystem()
    state.robot_system = robot
    
    if robot.controller:
        print("🧠 Initializing AI Agent...")
        tools = [
            create_move_forward(robot.controller),
            create_move_backward(robot.controller),
            create_turn_left(robot.controller),
            create_turn_right(robot.controller),
            create_look_around(robot.controller, robot.camera),
            create_end_task(),
            create_enable_precision_mode(),
            create_disable_precision_mode(),
            create_save_note()
        ]

        model_name = os.getenv("AI_MODEL", "openai/gpt-5.2") 
        
        try:
            agent = NavigationAgent(robot, model_name, tools)
            state.agent = agent
            print("✓ AI Agent ready")
        except Exception as e:
            print(f"⚠ AI Agent init failed: {e}")
    else:
        print("⚠ Robot controller not ready, AI disabled")

    print("🔄 Starting background threads...", end=" ", flush=True)
    
    threading.Thread(target=movement_loop, daemon=True).start()
    
    threading.Thread(target=agent_loop, daemon=True).start()
    
    
    app = create_app()
    
    print()
    print(f"🌐 http://0.0.0.0:{WEB_PORT}")
    print(f"📺 Display: http://localhost:{WEB_PORT}/display")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    if os.getenv('AUTO_OPEN_DISPLAY', 'true').lower() == 'true':
        def open_display():
            import time
            time.sleep(2)  
            display_url = f'http://localhost:{WEB_PORT}/display'
            env = os.environ.copy()
            env['DISPLAY'] = ':0' 
            try:
                subprocess.Popen(
                    ['chromium-browser', '--kiosk', '--noerrdialogs', '--disable-infobars', display_url],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("📺 Display opened on main screen")
            except FileNotFoundError:
                try:
                    subprocess.Popen(['firefox', '--kiosk', display_url], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print("📺 Display opened on main screen")
                except FileNotFoundError:
                    print("⚠ Could not auto-open display (no browser found)")
        threading.Thread(target=open_display, daemon=True).start()
    
    try:
        app.run(host='0.0.0.0', port=WEB_PORT, threaded=True, use_reloader=False, debug=False)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
