from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation
import json
import os
import shlex
import subprocess
import sys
import streamlit as st
from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.servo_controls import ServoControler, _check_calibration_file
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.core.tools import finish_task
from robocrew.robots.XLeRobot.tools import (
    create_go_to_precision_mode, \
    create_go_to_normal_mode, \
    create_move_backward, \
    create_move_forward, \
    create_strafe_right, \
    create_strafe_left, \
    create_look_around, \
    create_turn_right, \
    create_turn_left
)

CALIBRATION_TTYD_PORT = 8283
VLA_FILE = os.path.join(os.path.expanduser("~"), ".cache", "robocrew", "tools", "vla_tools.json")

def _is_process_running(process) -> bool:
    return process is not None and process.poll() is None


def _start_calibration_terminal(missing_files: list[str]) -> None:
    if not missing_files:
        return

    file_to_port = {
        "left_arm.json": "/dev/arm_left",
        "right_arm.json": "/dev/arm_right",
    }
    pyexe = shlex.quote(sys.executable)
    steps: list[str] = []
    for file_name in missing_files:
        calibration_id = os.path.splitext(file_name)[0]
        arm_port = file_to_port[file_name]
        code = (
            "from robocrew.robots.XLeRobot.servo_controls import _run_lerobot_calibrate, _check_calibration_file;"
            f"print('Starting calibration: {file_name} on {arm_port}');"
            f"_run_lerobot_calibrate('{arm_port}', '{calibration_id}', _check_calibration_file('{file_name}'));"
            f"print('Calibration finished: {file_name}')"
        )
        steps.append(f"{pyexe} -c {shlex.quote(code)}")

    bash_cmd = " ; ".join(steps) + " ; sleep 2 ; kill -9 $PPID"
    ttyd_cmd = ["ttyd", "-W", "-p", str(CALIBRATION_TTYD_PORT), "bash", "-c", bash_cmd]
    st.session_state.calibration_process = subprocess.Popen(ttyd_cmd, env=os.environ.copy())


def _get_missing_calibration_files() -> list[str]:
    return [
        name
        for name in ("left_arm.json", "right_arm.json")
        if not _check_calibration_file(name).exists()
    ]

@st.cache_resource
def get_hardware():
    return RobotCamera("/dev/camera_center"), ServoControler("/dev/arm_right", "/dev/arm_left")

def init_agent():
    if st.session_state.recording_process:
        st.session_state.init_error = "Hardware busy: Recording in progress."
        return

    missing_files = _get_missing_calibration_files()
    calibration_process = st.session_state.get("calibration_process")
    if not missing_files and calibration_process is not None and calibration_process.poll() is not None:
        st.session_state.calibration_process = None

    if missing_files:
        if _is_process_running(calibration_process):
            st.session_state.init_error = "Calibration in progress."
            return
        try:
            _start_calibration_terminal(missing_files)
            st.session_state.agent = None
            st.session_state.init_error = "Calibration started in terminal."
        except Exception as e:
            st.session_state.agent = None
            st.session_state.init_error = f"Failed to start calibration terminal: {e}"
        return
        
    with st.spinner("Initializing Robot Agent..."):
        try:
            main_camera, servo_controller = get_hardware()
            
            vla_tools = []
            if os.path.exists(VLA_FILE):
                with open(VLA_FILE, "r") as f:
                    for t in json.load(f):

                        if not t.get("active", True): 
                            continue
                            
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
            ] + vla_tools
            
            st.session_state.agent = XLeRobotAgent(
                model="google_genai:gemini-3-flash-preview",
                tools=tools,
                main_camera=main_camera,
                servo_controler=servo_controller,
                lidar_usb_port="/dev/lidar" if os.path.exists("/dev/lidar") else None,
                history_len=8
            )
            st.session_state.init_error = ""
        except Exception as e:
            st.session_state.agent = None
            st.session_state.init_error = str(e)
            st.error(f"Init failed: {e}")