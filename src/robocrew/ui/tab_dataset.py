# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import subprocess
import shutil
from pathlib import Path
from utils import get_local_ip

def render_dataset_tab():
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
            l_port = st.text_input("Teleop Port", "/dev/ttyACM4")
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