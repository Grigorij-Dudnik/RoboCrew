# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import subprocess
import os
import re
import shutil
import socket
from pathlib import Path

try:
    import speech_recognition as sr
except ImportError:
    st.error("Please run: pip install SpeechRecognition")

# Importy z Twojego pakietu RoboCrew
from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import (
    create_move_forward,
    create_move_backward,
    create_turn_left,
    create_turn_right,
    create_look_around
)

st.set_page_config(page_title="RoboCrew Dashboard", layout="wide", page_icon="🤖")

# --- Stałe konfiguracyjne ---
RULES_FILE = "/etc/udev/rules.d/99-robocrew.rules"

# --- Zarządzanie stanem sesji ---
if "agent" not in st.session_state:
    st.session_state.agent = None
if "init_error" not in st.session_state:
    st.session_state.init_error = ""
if "recording_process" not in st.session_state:
    st.session_state.recording_process = None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def save_udev_rules(new_content):
    try:
        if os.access(os.path.dirname(RULES_FILE), os.W_OK):
            with open(RULES_FILE, "w") as f:
                f.write(new_content)
            subprocess.run(["udevadm", "control", "--reload-rules"], check=False)
            subprocess.run(["udevadm", "trigger"], check=False)
            return True, ""
        else:
            import tempfile
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                tmp.write(new_content)
                tmp_name = tmp.name
            res = subprocess.run(["sudo", "-n", "cp", tmp_name, RULES_FILE], capture_output=True, text=True)
            if res.returncode == 0:
                subprocess.run(["sudo", "-n", "udevadm", "control", "--reload-rules"])
                subprocess.run(["sudo", "-n", "udevadm", "trigger"])
                return True, ""
            return False, res.stderr
    except Exception as e:
        return False, str(e)

def get_hardware_status():
    aliases = []
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r") as f:
                content = f.read()
            aliases = sorted(list(set(re.findall(r'SYMLINK\+="(.*?)"', content))))
        except: pass
    
    if not aliases:
        return None

    status = {}
    err_msg = st.session_state.get("init_error", "")
    is_recording = st.session_state.recording_process is not None
    
    for alias in aliases:
        path = f"/dev/{alias}"
        name = alias.replace("_", " ").title()
        
        if not os.path.exists(path):
            status[name] = {"state": "error", "label": "Disconnected"}
        elif is_recording:
            status[name] = {"state": "warning", "label": "Busy (Recording)"}
        elif err_msg and path in err_msg:
            status[name] = {"state": "error", "label": "Power/Comm Error"}
        elif not st.session_state.agent:
            status[name] = {"state": "warning", "label": "Standby"}
        else:
            status[name] = {"state": "success", "label": "Ready"}
    return status

def init_agent():
    if st.session_state.recording_process:
        st.session_state.init_error = "Hardware busy: Recording in progress."
        return
        
    with st.spinner("Initializing Robot Agent..."):
        try:
            main_camera = RobotCamera("/dev/camera_center")
            servo_controller = ServoControler("/dev/arm_right", "/dev/arm_left")
            
            tools = [
                create_move_forward(servo_controller),
                create_move_backward(servo_controller),
                create_turn_left(servo_controller),
                create_turn_right(servo_controller),
                create_look_around(servo_controller, main_camera)
            ]
            
            st.session_state.agent = XLeRobotAgent(
                model="google_genai:gemini-3-flash-preview",
                tools=tools,
                main_camera=main_camera,
                servo_controler=servo_controller,
                history_len=8
            )
            st.session_state.init_error = ""
            st.success("All systems operational!")
        except Exception as e:
            st.session_state.agent = None
            st.session_state.init_error = str(e)
            st.error(f"Init failed: {e}")

if "init_attempted" not in st.session_state:
    st.session_state.init_attempted = True
    init_agent()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔌 Hardware Health")
    hw_status = get_hardware_status()
    
    if hw_status:
        for name, info in hw_status.items():
            if info["state"] == "error": st.error(f"🔴 **{name}**: {info['label']}")
            elif info["state"] == "warning": st.warning(f"🟡 **{name}**: {info['label']}")
            else: st.success(f"🟢 **{name}**: {info['label']}")
    else:
        st.info("No udev aliases found. Use System Config to add devices.")
            
    st.divider()
    
    if not st.session_state.agent and not st.session_state.recording_process:
        if st.button("🔄 Retry Initialization", type="primary", use_container_width=True):
            init_agent()
            st.rerun()

# --- MAIN UI ---
st.title("RoboCrew Control Center")

if st.session_state.recording_process:
    st.warning("🎥 Dataset recording is active! LLM Agent is suspended.")
elif not st.session_state.agent:
    st.error("Robot is offline. Check connections and power.")

tab_chat, tab_manual, tab_dataset, tab_udev = st.tabs(["💬 Conversation", "🕹️ Manual", "⏺️ Data Collection", "🛠️ Config"])

# -------------------------------
# ZAKŁADKA 1: CONVERSATION
# -------------------------------
with tab_chat:
    if st.session_state.agent:
        col_viz, col_chat = st.columns([1, 1])
        with col_viz:
            try:
                imgs = st.session_state.agent.fetch_camera_images_base64()
                if imgs: st.image(f"data:image/jpeg;base64,{imgs[0]}", width="stretch")
            except: st.error("Vision link broken.")
        with col_chat:
            chat_container = st.container(height=450)
            with chat_container:
                for msg in st.session_state.agent.message_history:
                    if msg.type == "system": continue
                    with st.chat_message("user" if msg.type == "human" else "assistant"):
                        st.write(msg.content if isinstance(msg.content, str) else "[Visual Data]")
            
            # --- WIDŻETY WEJŚCIOWE (Tekst lub Głos) ---
            prompt_text = st.chat_input("Command the robot...")
            audio_bytes = st.audio_input("🎤 Or say a command:")
            
            final_prompt = None
            
            # Sprawdzamy czy użytkownik wpisał tekst
            if prompt_text:
                final_prompt = prompt_text
            # Jeśli nie, sprawdzamy czy nagrał dźwięk
            elif audio_bytes:
                try:
                    r = sr.Recognizer()
                    with sr.AudioFile(audio_bytes) as source:
                        audio_data = r.record(source)
                    final_prompt = r.recognize_google(audio_data, language="en-US")
                    st.toast(f"🗣️ Heard: {final_prompt}", icon="🎤")
                except sr.UnknownValueError:
                    st.error("Could not understand the audio. Please try again.")
                except Exception as e:
                    st.error(f"Speech recognition error: {e}")

            # Uruchomienie pętli zadania, jeśli mamy poprawny prompt
            if final_prompt:
                st.session_state.agent.task = final_prompt
                with st.spinner(f"Agent is working on: {final_prompt}"):
                    max_steps = 10 
                    for step in range(max_steps):
                        st.toast(f"🧠 Agent reasoning step {step+1}/{max_steps}...")
                        result = st.session_state.agent.main_loop_content()
                        
                        if st.session_state.agent.task is None or result == "Task finished, going idle.":
                            st.toast("✅ Task completed successfully!")
                            break
                    else:
                        st.warning("⚠️ Task paused: Reached maximum number of steps.")
                        
                st.rerun()
    else: st.info("LLM Agent offline.")

# -------------------------------
# ZAKŁADKA 2: MANUAL CONTROL 
# -------------------------------
with tab_manual:
    if st.session_state.agent:
        col_c, col_btn = st.columns([2, 1])
        with col_c:
            try:
                imgs = st.session_state.agent.fetch_camera_images_base64()
                if imgs: st.image(f"data:image/jpeg;base64,{imgs[0]}", width="stretch")
            except: pass
        with col_btn:
            ctrl = st.session_state.agent.servo_controler
            c1, c2, c3 = st.columns(3)
            with c2: 
                if st.button("⬆️", key="m_fwd", use_container_width=True): 
                    create_move_forward(ctrl).invoke({"distance_meters": 0.1}); st.rerun()
            with c1: 
                if st.button("⬅️", key="m_l", use_container_width=True): 
                    create_turn_left(ctrl).invoke({"angle_degrees": 15}); st.rerun()
            with c3: 
                if st.button("➡️", key="m_r", use_container_width=True): 
                    create_turn_right(ctrl).invoke({"angle_degrees": 15}); st.rerun()
            st.divider()
            if st.button("📸 Refresh View", use_container_width=True): st.rerun()
    else: st.info("Manual control unavailable.")

# -------------------------------
# ZAKŁADKA 3: DATA COLLECTION (TTYD EMBEDDED)
# -------------------------------
with tab_dataset:
    st.header("LeRobot Collection")
    rec = st.session_state.recording_process
    
    is_rec = rec is not None and rec.poll() is None
    if not is_rec and st.session_state.recording_process is not None:
        st.session_state.recording_process = None

    with st.form("data_form"):
        st.subheader("Dataset Parameters")
        c1, c2 = st.columns(2)
        repo = c1.text_input("Repo ID", "Grigorij/collect_tissue_pz")
        task = c1.text_input("Task", "Collect tissue to the bin.")
        
        c1_b, c2_b, c3_b = st.columns(3)
        num_ep = c1_b.number_input("Episodes", value=30, min_value=1)
        time_ep = c2_b.number_input("Episode Time (s)", value=12, min_value=1)
        reset_time = c3_b.number_input("Reset Time (s)", value=0, min_value=0)
        
        st.subheader("Robot Configuration")
        c3, c4 = st.columns(2)
        
        with c3:
            robot_type = st.selectbox("Robot Type", ["so101_follower", "so100_follower", "koch_follower"])
            f_port = st.text_input("Robot Port", "/dev/arm_right")
            robot_id = st.text_input("Robot ID (Calibration Name)", "my_awesome_follower_arm")
            cam1 = st.text_input("Camera 1 Port", "/dev/camera_center")
            
        with c4:
            teleop_type = st.selectbox("Teleop Type", ["so101_leader", "so100_leader", "koch_leader"])
            l_port = st.text_input("Teleop Port", "/dev/ttyACM5")
            teleop_id = st.text_input("Teleop ID (Calibration Name)", "my_awesome_leader_arm")
            cam2 = st.text_input("Camera 2 Port", "/dev/camera_right")
        
        st.subheader("Recording Mode")
        c5, c6, c7 = st.columns(3)
        with c5:
            resume_record = st.checkbox("🔄 Resume (Append to existing dataset)", value=False)
        with c6:
            overwrite_record = st.checkbox("⚠️ Overwrite (Delete existing local dataset)", value=False)
        with c7:
            play_sounds = st.checkbox("🔊 Play Sounds (requires spd-say)", value=False)
            
        st.divider()
        start = st.form_submit_button("▶️ Start LeRobot", disabled=is_rec)

    if start:
        if resume_record and overwrite_record:
            st.error("❌ You cannot select both Resume and Overwrite. Please choose only one.")
        else:
            if st.session_state.agent:
                try: st.session_state.agent.main_camera.release()
                except: pass
                try: st.session_state.agent.servo_controler.disconnect()
                except: pass
                st.session_state.agent = None
                
            if overwrite_record:
                local_dir = Path.home() / ".cache" / "huggingface" / "lerobot" / repo
                if local_dir.exists():
                    shutil.rmtree(local_dir)
                    st.toast(f"Deleted old dataset at {local_dir}", icon="🗑️")
            
            cam_cfg = f'{{ camera1: {{type: opencv, index_or_path: {cam1}, width: 640, height: 480, fps: 25}}'
            if cam2: cam_cfg += f', camera2: {{type: opencv, index_or_path: {cam2}, width: 640, height: 480, fps: 25}}'
            cam_cfg += ' }'
            
            lerobot_cmd = [
                "lerobot-record", 
                f"--robot.type={robot_type}", 
                f"--robot.port={f_port}", 
                f"--robot.id={robot_id}",
                f"--robot.cameras={cam_cfg}",
                f"--teleop.type={teleop_type}", 
                f"--teleop.port={l_port}",
                f"--teleop.id={teleop_id}",
                "--display_data=false",
                f"--play_sounds={str(play_sounds).lower()}",
                f"--dataset.repo_id={repo}", 
                f"--dataset.num_episodes={num_ep}", 
                f"--dataset.episode_time_s={time_ep}",
                f"--dataset.reset_time_s={reset_time}",
                f"--dataset.single_task={task}"
            ]
                   
            if resume_record:
                lerobot_cmd.append("--resume=true")
            
            ttyd_cmd = ["ttyd", "-W", "-p", "8282"] + lerobot_cmd
            
            st.session_state.recording_process = subprocess.Popen(ttyd_cmd)
            st.rerun()

    if is_rec:
        st.divider()
        st.subheader("🖥️ Interactive LeRobot Terminal")
        st.info("💡 You can click inside the terminal below to type, press ENTER for calibration, or use shortcuts like Shift to end early.")
        
        pi_ip = get_local_ip()
        components.iframe(f"http://{pi_ip}:8282", height=500, scrolling=True)
        
        st.write("")
        
        if st.button("⏹️ Force Kill Process", type="primary", use_container_width=True):
            st.session_state.recording_process.terminate()
            subprocess.run(["pkill", "-f", "lerobot-record"])
            subprocess.run(["pkill", "-f", "ttyd"])
            st.session_state.recording_process = None
            st.rerun()

# -------------------------------
# ZAKŁADKA 4: SYSTEM CONFIG (UDEV)
# -------------------------------
with tab_udev:
    st.header("Udev Manager")
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, "r") as f:
            lines = f.readlines()
            content = "".join(lines)
        
        found_aliases = sorted(list(set(re.findall(r'SYMLINK\+="(.*?)"', content))))
        for al in found_aliases:
            col_s, col_d = st.columns([5, 1])
            dev_path = f"/dev/{al}"
            
            with col_s:
                if os.path.exists(dev_path):
                    real_port = os.path.realpath(dev_path)
                    st.success(f"🟢 **{al}** – Connected (`-> {real_port}`)")
                else:
                    st.error(f"🔴 **{al}** – Disconnected")
                    
            with col_d:
                if st.button("🗑️", key=f"del_{al}", use_container_width=True):
                    new_c = "".join([l for l in lines if f'SYMLINK+="{al}"' not in l])
                    save_udev_rules(new_c)
                    st.rerun()
    else:
        st.info("No udev rules file found yet.")
    
    st.divider()
    st.subheader("➕ Add/Edit Device")
    if "step" not in st.session_state: st.session_state.step = 0
    
    try:
        from robocrew.scripts.robocrew_setup_usb_modules import capture_devices, build_rule
        if st.session_state.step == 0:
            target = st.text_input("Alias name (e.g. camera_center)")
            if st.button("Start Wizard") and target:
                st.session_state.target = target
                st.session_state.base = { (d["subsystem"], d["kernel"], d["phys"]): d for d in capture_devices() }
                st.session_state.step = 1; st.rerun()
        elif st.session_state.step == 1:
            st.warning(f"Disconnect `{st.session_state.target}` now.")
            if st.button("Done"):
                curr = { (d["subsystem"], d["kernel"], d["phys"]): d for d in capture_devices() }
                diff = set(st.session_state.base.keys()) - set(curr.keys())
                if diff:
                    st.session_state.lost = st.session_state.base[list(diff)[0]]
                    st.session_state.base = curr; st.session_state.step = 2; st.rerun()
        elif st.session_state.step == 2:
            st.info("Plug it into the target port.")
            if st.button("Connected"):
                curr = { (d["subsystem"], d["kernel"], d["phys"]): d for d in capture_devices() }
                diff = set(curr.keys()) - set(st.session_state.base.keys())
                if diff:
                    new_dev = curr[list(diff)[0]]
                    rule = build_rule(new_dev, st.session_state.target)
                    existing = []
                    if os.path.exists(RULES_FILE):
                        with open(RULES_FILE, "r") as f: existing = f.readlines()
                    final = [l for l in existing if f'SYMLINK+="{st.session_state.target}"' not in l]
                    final.append(rule + "\n")
                    save_udev_rules("".join(final))
                    st.session_state.step = 0; st.success("Saved!"); st.rerun()
    except: st.error("Setup scripts missing. Ensure robocrew.scripts is installed.")