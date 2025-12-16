import cv2
import time
import numpy as np
from flask import Blueprint, Response, jsonify, request, render_template

from robocrew.core.state import state
from robocrew.core.camera import generate_frames
from robocrew.core.movement import execute_movement
from robocrew.core.arm import arm_controller

bp = Blueprint('robot', __name__)

@bp.route('/status')
def get_status():
    return jsonify({
        'controller_connected': state.controller is not None,
        'camera_connected': state.camera is not None and state.camera.isOpened(),
        'arm_connected': state.arm_connected,
        'control_mode': state.get_control_mode(),
        'head_yaw': state.head_yaw,
        'head_pitch': state.head_pitch,
        'movement': state.movement,
        'arm_positions': state.get_arm_positions(),
        'error': state.last_error
    })


@bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@bp.route('/head_position')
def get_head_position():
    if state.controller is None:
        return jsonify({'error': 'No controller'})
    
    try:
        pos = state.controller.get_head_position()
        yaw = round(pos.get(7, 0), 1)
        pitch = round(pos.get(8, 0), 1)
        state.head_yaw = yaw
        state.head_pitch = pitch
        return jsonify({'yaw': yaw, 'pitch': pitch})
    except Exception as e:
        state.last_error = str(e)
        return jsonify({'error': str(e)})


@bp.route('/head', methods=['POST'])
def set_head():
    if state.controller is None:
        return jsonify({'status': 'error', 'error': 'No controller'})
    
    data = request.json
    yaw = float(data.get('yaw', state.head_yaw))
    pitch = float(data.get('pitch', state.head_pitch))
    
    try:
        yaw_result = state.controller.turn_head_yaw(yaw)
        pitch_result = state.controller.turn_head_pitch(pitch)
        actual_yaw = list(yaw_result.values())[0] if yaw_result else yaw
        actual_pitch = list(pitch_result.values())[0] if pitch_result else pitch
        state.head_yaw = actual_yaw
        state.head_pitch = actual_pitch
        state.last_remote_activity = time.time()
        return jsonify({'status': 'ok', 'yaw': actual_yaw, 'pitch': actual_pitch})
    except Exception as e:
        state.last_error = str(e)
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/move', methods=['POST'])
def move():
    if state.controller is None:
        return jsonify({'status': 'error', 'error': 'No controller'})
    
    data = request.json
    state.update_movement(data)
    
    movement = state.get_movement()
    success = execute_movement(movement)
    
    if any(movement.values()):
        state.last_remote_activity = time.time()
        state.last_movement_activity = time.time()

    
    return jsonify({'status': 'ok' if success else 'error'})


@bp.route('/mode', methods=['GET'])
def get_mode():
    return jsonify({'mode': state.get_control_mode()})


@bp.route('/mode', methods=['POST'])
def set_mode():
    data = request.json
    mode = data.get('mode', 'drive')
    
    if state.set_control_mode(mode):
        return jsonify({'status': 'ok', 'mode': mode})
    return jsonify({'status': 'error', 'error': f'Invalid mode: {mode}'})


@bp.route('/arm_position')
def get_arm_position():
    if not state.arm_connected:
        return jsonify({'error': 'Arm not connected'})
    
    try:
        pos = state.controller.get_arm_position()
        state.update_arm_positions(pos)
        return jsonify({'positions': pos})
    except Exception as e:
        return jsonify({'error': str(e)})


@bp.route('/arm', methods=['POST'])
def set_arm():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    data = request.json
    positions = data.get('positions', {})
    
    try:
        result = state.controller.set_arm_position(positions)
        state.update_arm_positions(result)
        return jsonify({'status': 'ok', 'positions': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/arm/mouse', methods=['POST'])
def arm_mouse():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    data = request.json
    delta_x = float(data.get('deltaX', 0))
    delta_y = float(data.get('deltaY', 0))
    
    try:
        targets = arm_controller.handle_mouse_move(delta_x, delta_y)
        result = state.controller.set_arm_position(targets)
        state.update_arm_positions(result)
        return jsonify({'status': 'ok', 'positions': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/arm/scroll', methods=['POST'])
def arm_scroll():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    data = request.json
    delta = float(data.get('delta', 0))
    
    try:
        arm_controller.handle_scroll(delta)
        targets = arm_controller.get_targets()
        result = state.controller.set_arm_position(targets)
        state.update_arm_positions(result)
        return jsonify({'status': 'ok', 'wrist_roll': result.get('wrist_roll', 0)})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/arm/key', methods=['POST'])
def arm_key():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    data = request.json
    key = data.get('key', '')
    
    try:
        if key == 'q':
            arm_controller.handle_shoulder_pan(-1)
        elif key == 'e':
            arm_controller.handle_shoulder_pan(1)
        elif key == 'r':
            arm_controller.handle_wrist_flex(1)
        elif key == 'f':
            arm_controller.handle_wrist_flex(-1)
        elif key == 't':
            arm_controller.handle_elbow_flex(-1)
        elif key == 'g':
            arm_controller.handle_elbow_flex(1)
        
        targets = arm_controller.get_targets()
        result = state.controller.set_arm_position(targets)
        state.update_arm_positions(result)
        return jsonify({'status': 'ok', 'positions': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/gripper', methods=['POST'])
def set_gripper():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    data = request.json
    closed = bool(data.get('closed', False))
    
    try:
        arm_controller.set_gripper(closed)
        result = state.controller.set_gripper(closed)
        state.gripper_closed = closed
        return jsonify({'status': 'ok', 'closed': closed, 'angle': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/arm/home', methods=['POST'])
def arm_home():
    if not state.arm_connected:
        return jsonify({'status': 'error', 'error': 'Arm not connected'})
    
    try:
        targets = arm_controller.reset_to_home()
        result = state.controller.set_arm_position(targets)
        state.update_arm_positions(result)
        return jsonify({'status': 'ok', 'positions': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@bp.route('/ai/start', methods=['POST'])
def ai_start():
    if not state.agent:
        return jsonify({'status': 'error', 'error': 'AI Agent not initialized'})
    
    current_task = None
    if hasattr(state.agent, 'current_task'):
        current_task = state.agent.current_task

    state.agent.reset()
    
    if current_task:
        state.agent.set_task(current_task)
    
    state.ai_enabled = True
    state.add_ai_log("AI Started")
    return jsonify({'status': 'ok'})

@bp.route('/ai/stop', methods=['POST'])
def ai_stop():
    state.ai_enabled = False
    state.precision_mode = False
    
    if state.agent:
        state.agent.reset()
        
    state.add_ai_log("AI Stopped")
    return jsonify({'status': 'ok'})

@bp.route('/ai/task', methods=['POST'])
def ai_task():
    if not state.agent:
        return jsonify({'status': 'error', 'error': 'AI Agent not initialized'})
    data = request.json
    task = data.get('task', '')
    if task:
        state.agent.set_task(task)
        state.add_ai_log(f"New Task: {task}")
    return jsonify({'status': 'ok'})

@bp.route('/ai/status')
def ai_status():
    return jsonify({
        'enabled': state.ai_enabled,
        'status': state.ai_status,
        'logs': state.ai_logs
    })

@bp.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    state.ai_enabled = False
    state.precision_mode = False
    state.stop_all_movement()
    if state.robot_system:
        state.robot_system.emergency_stop()
    state.add_ai_log("EMERGENCY STOP TRIGGERED")
    return jsonify({'status': 'ok'})


@bp.route('/display')
def display_page():
    return render_template('display.html')


@bp.route('/display/state')
def display_state():
    is_remote = (time.time() - state.last_remote_activity) < 3 
    if state.ai_enabled:
        control_mode = 'ai'
    elif is_remote:
        control_mode = 'remote'
    else:
        control_mode = 'idle'
    
    return jsonify({
        'ai_enabled': state.ai_enabled,
        'ai_status': state.ai_status,
        'current_task': state.agent.current_task if state.agent and hasattr(state.agent, 'current_task') else None,
        'controller_connected': state.controller is not None,
        'camera_connected': state.camera is not None and state.camera.isOpened() if state.camera else False,
        'arm_connected': state.arm_connected,
        'control_mode': control_mode,
        'precision_mode': state.precision_mode,
        'blockage': state.get_detector().latest_blockage if state.detector else {}
    })


def generate_cv_frames():
    import time
    detector = state.get_detector()
    
    while state.running:
        if state.robot_system is None:
            time.sleep(0.1)
            continue
        
        try:
            frame = state.robot_system.get_frame()
            if frame is None:
                time.sleep(0.02)
                continue
            
            safe_actions, overlay, metrics = detector.process(frame)
            
            if state.ai_enabled:
                cv2.putText(overlay, "AI: ACTIVE", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(overlay, "AI: PAUSED", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
            
            if state.agent and hasattr(state.agent, 'current_task'):
                task_text = state.agent.current_task[:40] if len(state.agent.current_task) > 40 else state.agent.current_task
                cv2.putText(overlay, task_text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if "FORWARD" not in safe_actions:
                 cv2.putText(overlay, "BLOCKED AHEAD", (overlay.shape[1]//2 - 80, overlay.shape[0]//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            _, buffer = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except Exception as e:
            time.sleep(0.05)


@bp.route('/ai_video_feed')
def ai_video_feed():
    return Response(generate_cv_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
