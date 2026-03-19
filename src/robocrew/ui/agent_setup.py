# -*- coding: utf-8 -*-
from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation
import json
import os
import streamlit as st
from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.core.tools import finish_task, save_checkpoint
from robocrew.robots.XLeRobot.tools import (
    create_move_forward, create_move_backward, create_turn_left, 
    create_turn_right, create_look_around, create_strafe_left, 
    create_strafe_right, create_go_to_precision_mode, create_go_to_normal_mode
)

@st.cache_resource
def get_hardware():
    return RobotCamera("/dev/camera_center"), ServoControler("/dev/arm_right", "/dev/arm_left")

def init_agent():
    if st.session_state.recording_process:
        st.session_state.init_error = "Hardware busy: Recording in progress."
        return
        
    with st.spinner("Initializing Robot Agent..."):
        try:
            main_camera, servo_controller = get_hardware()
            
            # Ładowanie dynamicznych narzędzi VLA
            vla_tools = []
            if os.path.exists("vla_tools.json"):
                with open("vla_tools.json", "r") as f:
                    for t in json.load(f):
                        # Pomijanie nieaktywnych narzędzi
                        if not t.get("active", True): 
                            continue
                            
                        # Automatyczne mapowanie np. /dev/arm_right na /dev/camera_right
                        #cam_port = t["arm_port"].replace("arm", "camera") 
                        #cam_cfg = {"main": {"index_or_path": "/dev/camera_center"}, "arm": {"index_or_path": cam_port}}
                        cam_cfg = {"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}}
                        
                        vla_tools.append(create_vla_single_arm_manipulation(
                            tool_name=t["tool_name"], tool_description=t["tool_description"],
                            task_prompt=t["task_prompt"], server_address=t["server_address"],
                            policy_name=t["policy_name"], policy_type=t["policy_type"],
                            arm_port=t["arm_port"], servo_controler=servo_controller,
                            camera_config=cam_cfg, main_camera_object=main_camera,
                            policy_device=t["policy_device"], execution_time=t["execution_time"],
                            load_on_startup=False
                        ))

            tools = [
                create_move_forward(servo_controller),
                create_move_backward(servo_controller),
                create_turn_left(servo_controller),
                create_turn_right(servo_controller),
                create_strafe_left(servo_controller),
                create_strafe_right(servo_controller),
                create_go_to_precision_mode(servo_controller),
                create_go_to_normal_mode(servo_controller),
                create_look_around(servo_controller, main_camera),
                finish_task,
                save_checkpoint
            ] + vla_tools
            
            st.session_state.agent = XLeRobotAgent(
                model="google_genai:gemini-3-flash-preview",
                tools=tools,
                main_camera=main_camera,
                servo_controler=servo_controller,
                history_len=8
            )
            st.session_state.init_error = ""
        except Exception as e:
            st.session_state.agent = None
            st.session_state.init_error = str(e)
            st.error(f"Init failed: {e}")