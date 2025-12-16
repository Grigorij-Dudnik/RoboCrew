import time
from robocrew.core.state import state
from robocrew.config import MOVEMENT_LOOP_INTERVAL, REMOTE_TIMEOUT

def execute_movement(movement):
    if state.controller is None:
        return False
        
    try:
        if movement['forward']:
            state.controller.move_forward()
        elif movement['backward']:
            state.controller.move_backward()
        elif movement['left']:
            state.controller.turn_left()
        elif movement['right']:
            state.controller.turn_right()
        else:
            state.controller._wheels_stop()
        return True
    except Exception as e:
        state.last_error = f"Movement error: {e}"
        return False

def stop_movement():
    if state.controller:
        state.controller._wheels_stop()

def movement_loop():
    while state.running:
        current_time = time.time()
        
        if (current_time - state.last_remote_activity > REMOTE_TIMEOUT and 
            current_time - state.last_movement_activity > REMOTE_TIMEOUT and
            not state.ai_enabled):
            stop_movement()
        
        elif state.ai_enabled:
             pass
        
        elif any(state.movement.values()):
            execute_movement(state.movement)
            
        time.sleep(MOVEMENT_LOOP_INTERVAL)
