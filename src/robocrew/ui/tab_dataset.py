# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from utils import get_local_ip
from huggingface_hub import HfFolder, HfApi, login, logout

def render_dataset_tab():
    # Odczyt tokena bezpośrednio z pliku, do którego HF domyślnie go zapisuje
    hf_token_path = Path.home() / ".cache" / "huggingface" / "token"
    cached_token = None
    if hf_token_path.exists():
        with open(hf_token_path, "r") as f:
            cached_token = f.read().strip()
            
    current_token = cached_token or HfFolder.get_token() or os.environ.get("HF_TOKEN")
    
    if current_token:
        os.environ["HF_TOKEN"] = current_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = current_token
    
    if not current_token:
        st.warning("🔒 You need to provide your Hugging Face token to record and upload datasets.")
        st.info("You can get your token from [Hugging Face Settings](https://huggingface.co/settings/tokens). Make sure it has 'write' permissions.")
        hf_token = st.text_input("Hugging Face Token", type="password")
        
        if st.button("Login"):
            if hf_token:
                try:
                    HfApi(token=hf_token).whoami()
                    
                    # Ręczny zapis tokenu do pliku cache (jako fallback)
                    hf_token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(hf_token_path, "w") as f:
                        f.write(hf_token)
                        
                    HfFolder.save_token(hf_token)
                    try:
                        login(token=hf_token, add_to_git_credential=True)
                    except TypeError:
                        login(token=hf_token)
                    st.success("Successfully logged in!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to login or token is invalid. Error: {e}")
            else:
                st.error("Please enter a token.")
        return

    c_empty, c_logout = st.columns([0.85, 0.15])
    if c_logout.button("🚪 Logout"):
        os.environ.pop("HF_TOKEN", None)
        os.environ.pop("HUGGING_FACE_HUB_TOKEN", None)
        HfFolder.delete_token()
        
        # Ręczne kasowanie pliku cache
        if hf_token_path.exists():
            hf_token_path.unlink()
            
        try:
            logout()
        except Exception:
            pass
        st.rerun()

    rec = st.session_state.recording_process
    is_rec = rec is not None and rec.poll() is None
    if not is_rec and st.session_state.recording_process is not None:
        st.session_state.recording_process = None

    with st.form("data_form"):
        st.subheader("Dataset Parameters")
        c1, c2 = st.columns(2)
        repo = c1.text_input("Repo ID", placeholder="username/robocrew-dataset")
        task = c2.text_input("Task", placeholder="e.g. Collect tissue to the bin.")
        
        c1_b, c2_b, c3_b = st.columns(3)
        num_ep = c1_b.number_input("Episodes", value=30, min_value=1)
        time_ep = c2_b.number_input("Episode Time (s)", value=12, min_value=1)
        reset_time = c3_b.number_input("Reset Time (s)", value=0, min_value=0)
        
        st.subheader("Robot Configuration")
        c3, c4 = st.columns(2)
        with c3:
            robot_type = st.selectbox("Robot Type", ["so101_follower"])
            f_port = st.selectbox("Robot Port", ["/dev/arm_right", "/dev/arm_left"])
            robot_id = st.text_input("Robot Calibration Name", placeholder="my_awesome_follower_arm")
            cam1 = st.selectbox("Camera 1 Port", ["/dev/camera_center"])
            
        with c4:
            teleop_type = st.selectbox("Teleop Type", ["so101_leader"])
            l_port = st.text_input("Teleop Port", placeholder="/dev/ttyACM4")
            teleop_id = st.text_input("Teleop Calibration Name", placeholder="my_awesome_leader_arm")
            cam2 = st.selectbox("Camera 2 Port", ["/dev/camera_right", "/dev/camera_left"])
        
        c5, c6 = st.columns(2)
        overwrite_record = c5.checkbox("⚠️ Overwrite existing dataset", value=False)
        play_sounds = c6.checkbox("🔊 Play Sounds", value=False)
            
        st.divider()
        start = st.form_submit_button("▶️ Record Dataset", disabled=is_rec)

    if start:
        if st.session_state.agent:
            try:
                st.session_state.agent.main_camera.release()
                st.session_state.agent.servo_controler.disconnect()
            except Exception as e: 
                st.warning(f"Hardware resources cleanup warning: {e}")
            st.session_state.agent = None
            
        if overwrite_record:
            local_dir = Path.home() / ".cache" / "huggingface" / "lerobot" / repo
            if local_dir.exists():
                try:
                    shutil.rmtree(local_dir)
                    st.toast(f"Deleted old dataset at {local_dir}", icon="🗑️")
                except Exception as e:
                    st.error(f"Failed to delete old dataset: {e}")
        
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
        
        ttyd_cmd = ["ttyd", "-W", "-p", "8282"] + lerobot_cmd
        
        env = os.environ.copy()
        if current_token:
            env["HF_TOKEN"] = current_token
        
        st.session_state.recording_process = subprocess.Popen(ttyd_cmd, env=env)
        st.rerun()

    if is_rec:
        st.divider()
        st.subheader("🖥️ Interactive LeRobot Terminal")
        
        components.iframe(f"http://{get_local_ip()}:8282", height=500, scrolling=True)
        
        if st.button("⏹️ Stop Recording & Upload Dataset", type="primary"):
            st.info("Wysyłanie sygnału zatrzymania... Poczekaj na zakończenie wysyłania (uploadu) w terminalu wyżej.")
            subprocess.run(["pkill", "-2", "-f", "lerobot-record"])