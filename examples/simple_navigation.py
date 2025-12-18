import logging
import sys
import numpy as np
from robocrew.core.state import RobotState
from robocrew.core.agent import NavigationAgent

# Use dummy frame generator
def get_dummy_frame():
    # Create a 640x480 black image
    return np.zeros((480, 640, 3), dtype=np.uint8)

def main():
    logging.basicConfig(level=logging.INFO)
    print("Starting RoboCrew Navigation Example...")
    
    state = RobotState()
    agent = NavigationAgent(state)
    
    print("Running Agent Loop...")
    agent.run_loop(get_dummy_frame, max_steps=5)
    
    print("Done.")

if __name__ == "__main__":
    main()
