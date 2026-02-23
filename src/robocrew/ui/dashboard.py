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

st.set_page_config(page_title="RoboCrew Dashboard", layout="wide", page_icon="🤖")

# --- Hardware Diagnostic Helper ---
def get_hardware_status():
    """Checks if critical hardware paths exist in the system."""
    devices = {
        "Main Camera": "/dev/camera_center",
        "Right Arm": "/dev/arm_right",
        "Left Arm": "/dev/arm_left"
    }
    # Zwraca słownik {nazwa: True/False}
    return {name: os.path.exists(path) for name, path in devices.items()}

# --- Agent Session State Management ---
if "agent" not in st.session_state:
    st.session_state.agent = None

def init_agent():
    """Initializes the agent and its tools."""
    try:
        # Konfiguracja zgodnie z Twoim przykładem
        main_camera = RobotCamera("/dev/camera_center")
        servo_controller = ServoControler("/dev/arm_right", "/dev/arm_left")
        
        # Inicjalizacja listy narzędzi
        tools = [
            create_move_forward(servo_controller),
            create_move_backward(servo_controller),
            create_turn_left(servo_controller),
            create_turn_right(servo_controller),
            create_look_around(servo_controller, main_camera)
        ]
        
        # Tworzenie agenta
        agent = XLeRobotAgent(
            model="google_genai:gemini-3-flash-preview",
            tools=tools,
            main_camera=main_camera,
            servo_controler=servo_controller,
            history_len=8
        )
        st.session_state.agent = agent
        st.success("Success: All systems operational!")
    except Exception as e:
        st.error(f"Hardware initialization failed: {e}")

# --- Sidebar: Hardware Health & Controls ---
with st.sidebar:
    st.header("🔌 Hardware Health")
    hw_status = get_hardware_status()
    
    # Wyświetlanie statusu urządzeń (Zielony/Czerwony)
    for name, connected in hw_status.items():
        if connected:
            st.success(f"● {name}: Connected")
        else:
            st.error(f"○ {name}: Disconnected")
    
    st.divider()
    
    # Przycisk inicjalizacji (opcjonalnie zablokowany, jeśli brak sprzętu)
    if st.button("🚀 Initialize Robot", use_container_width=True):
        init_agent()
    
    # Manual Override (tylko gdy agent jest zainicjowany)
    if st.session_state.agent:
        st.subheader("🕹️ Manual Control")
        ctrl = st.session_state.agent.servo_controler
        m_col1, m_col2, m_col3 = st.columns(3)
        
        with m_col2:
            if st.button("⬆️"):
                # Używamy distance_meters zgodnie z walidacją pydantic
                create_move_forward(ctrl).invoke({"distance_meters": 0.1})
        with m_col1:
            if st.button("⬅️"):
                # Używamy angle_degrees zgodnie z walidacją pydantic
                create_turn_left(ctrl).invoke({"angle_degrees": 15})
        with m_col3:
            if st.button("➡️"):
                create_turn_right(ctrl).invoke({"angle_degrees": 15})

# --- Main Dashboard ---
st.title("RoboCrew Control Center")

if st.session_state.agent is None:
    st.info("Robot is in standby. Check hardware status and click 'Initialize Robot' to start.")
else:
    agent = st.session_state.agent
    tab_chat, tab_udev = st.tabs(["💬 Conversation", "🛠️ System Config"])

    with tab_chat:
        col_viz, col_chat = st.columns([1, 1])
        
        with col_viz:
            st.subheader("Vision Feedback")
            try:
                # Pobieranie obrazu z kamery przez agenta
                images = agent.fetch_camera_images_base64()
                if images:
                    # width='stretch' zamiast przestarzałego use_container_width
                    st.image(f"data:image/jpeg;base64,{images[0]}", width="stretch")
            except Exception as e:
                st.error(f"Vision error: {e}")

        with col_chat:
            st.subheader("LLM Agent Log")
            # Kontener na historię rozmowy
            chat_container = st.container(height=500)
            with chat_container:
                for msg in agent.message_history:
                    if msg.type == "system": continue
                    role = "user" if msg.type == "human" else "assistant"
                    with st.chat_message(role):
                        if isinstance(msg.content, str):
                            st.write(msg.content)
                        else:
                            st.caption("[Visual data transmitted]")

            # Pole tekstowe dla nowych zadań
            if prompt := st.chat_input("Enter new task for the robot..."):
                agent.task = prompt
                with st.spinner("Processing loop..."):
                    # Wywołanie pojedynczego kroku pętli agenta
                    agent.main_loop_content()
                st.rerun()

    with tab_udev:
        st.header("Udev Rules Manager")
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
