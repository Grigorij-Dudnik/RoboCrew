# -*- coding: utf-8 -*-
import streamlit as st
import subprocess
import os

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

st.set_page_config(page_title="RoboCrew Web Console", layout="wide", page_icon="🤖")

# --- Zarządzanie Stanem Agenta (Session State) ---
if "agent" not in st.session_state:
    st.session_state.agent = None

def init_agent():
    """Inicjalizacja sprzetu i agenta zgodnie z Twoim setupem."""
    try:
        # Konfiguracja kamer i serwomechanizmów
        main_camera = RobotCamera("/dev/camera_center")
        servo_controller = ServoControler("/dev/arm_right", "/dev/arm_left")

        # Definicja narzedzi
        tools = [
            create_move_forward(servo_controller),
            create_move_backward(servo_controller),
            create_turn_left(servo_controller),
            create_turn_right(servo_controller),
            create_look_around(servo_controller, main_camera)
        ]

        # Inicjalizacja agenta LLM
        agent = XLeRobotAgent(
            model="google_genai:gemini-3-flash-preview",
            tools=tools,
            main_camera=main_camera,
            servo_controler=servo_controller,
            history_len=8
        )
        st.session_state.agent = agent
        st.success("Robot hardware and Agent initialized!")
    except Exception as e:
        st.error(f"Failed to initialize hardware: {e}")

# --- Pasek boczny: Sterowanie Reczne (Manual Override) ---
with st.sidebar:
    st.header("⚙️ System Control")
    if st.button("🔄 Initialize/Reset Robot"):
        init_agent()
        st.rerun()
    
    if st.session_state.agent:
        st.divider()
        st.subheader("🕹️ Manual Controls")
        # Wykorzystujemy pobrany wczesniej kontroler serw
        ctrl = st.session_state.agent.servo_controler
        
        m_col1, m_col2, m_col3 = st.columns(3)
        
        with m_col2:
            # Uzywamy 'distance_meters' zamiast 'distance'
            if st.button("⬆️"):
                create_move_forward(ctrl).invoke({"distance_meters": 0.1})
                st.toast("Moving forward 0.1m")
        
        with m_col1:
            # Uzywamy 'angle_degrees' zamiast 'angle' zgodnie z bledem Pydantic
            if st.button("⬅️"):
                create_turn_left(ctrl).invoke({"angle_degrees": 15})
                st.toast("Turning left 15°")
        
        with m_col3:
            # Uzywamy 'angle_degrees' zamiast 'angle'
            if st.button("➡️"):
                create_turn_right(ctrl).invoke({"angle_degrees": 15})
                st.toast("Turning right 15°")

# --- Glówny Interfejs ---
st.title("🤖 RoboCrew Dashboard")

if st.session_state.agent is None:
    st.warning("Please click 'Initialize Robot' in the sidebar to start.")
else:
    agent = st.session_state.agent
    tab_chat, tab_udev = st.tabs(["💬 Conversation", "🛠️ Udev Setup"])

    with tab_chat:
        col_viz, col_chat = st.columns([1, 1])

        with col_viz:
            st.subheader("Robot Vision")
            try:
                # Pobieranie obrazu base64 z Twojej metody LLMAgent
                images = agent.fetch_camera_images_base64()
                if images:
                    # 'width="stretch"' zamiast 'use_container_width'
                    st.image(f"data:image/jpeg;base64,{images[0]}", width="stretch")
            except Exception as e:
                st.error(f"Camera Error: {e}")

        with col_chat:
            st.subheader("Agent Chat")
            # Wyswietlanie historii z agent.message_history
            for msg in agent.message_history:
                if msg.type == "system": continue
                role = "user" if msg.type == "human" else "assistant"
                with st.chat_message(role):
                    if isinstance(msg.content, str):
                        st.write(msg.content)
                    else:
                        st.caption("[Visual Data Transmitted]")

            if prompt := st.chat_input("Enter command for the robot..."):
                agent.task = prompt # Ustawienie zadania
                with st.spinner("Processing..."):
                    # Wywolanie glównej petli Twojego agenta
                    agent.main_loop_content()
                st.rerun()

    with tab_udev:
        st.header("Udev Rules Assistant")
        if st.button("Scan USB Devices (lsusb)"):
            res = subprocess.run(['lsusb'], capture_output=True, text=True)
            st.code(res.stdout)
        
        with st.form("udev_form"):
            v_id = st.text_input("Vendor ID (e.g., 1a86)")
            p_id = st.text_input("Product ID (e.g., 7523)")
            s_name = st.text_input("Symlink Name (e.g., arm_right)")

            if st.form_submit_button("Generate Rule"):
                rule = f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{v_id}", ATTRS{{idProduct}}=="{p_id}", SYMLINK+="{s_name}"'
                st.code(rule, language="bash")
                st.info(f"Command: echo '{rule}' | sudo tee /etc/udev/rules.d/99-{s_name}.rules && sudo udevadm control --reload-rules")
