import streamlit as st
import subprocess
import os
import base64
from robocrew.core.LLMAgent import LLMAgent

st.set_page_config(page_title="RoboCrew Dashboard", layout="wide", page_icon="🤖")

# --- Inicjalizacja Agenta (Stan Sesji) ---
if "agent" not in st.session_state:
    st.session_state.agent = None
    st.session_state.logs = []

def initialize_agent(model_name, task):
    # Tutaj importujesz narzędzia tak jak w swoim example
    # Dla uproszczenia szablonu:
    from robocrew.core.camera import RobotCamera
    cam = RobotCamera("/dev/camera_center") 
    
    # Tworzysz instancję agenta (parametry dobierz pod swój robot)
    agent = LLMAgent(
        model=model_name,
        tools=[], # Dodaj swoje narzędzia tutaj
        main_camera=cam,
        history_len=8
    )
    agent.task = task
    st.session_state.agent = agent

# --- UI ---
st.title("🤖 RoboCrew Control Panel")

tab_chat, tab_udev = st.tabs(["💬 Konwersacja LLM", "🔧 Konfiguracja Udev"])

with tab_chat:
    if not st.session_state.agent:
        with st.form("init_form"):
            m = st.text_input("Model", value="google_genai:gemini-1.5-flash")
            t = st.text_area("Zadanie początkowe", value="Sprawdź otoczenie.")
            if st.form_submit_button("Uruchom Agenta"):
                initialize_agent(m, t)
                st.rerun()
    else:
        agent = st.session_state.agent
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Podgląd wizji")
            # Wyciągamy ostatni obraz z historii agenta
            for msg in reversed(agent.message_history):
                if hasattr(msg, 'content') and isinstance(msg.content, list):
                    for item in msg.content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            st.image(item["image_url"]["url"], use_column_width=True)
                            break

        with col2:
            st.subheader("Czat z Agentem")
            for msg in agent.message_history:
                if msg.type == "system": continue
                role = "user" if msg.type == "human" else "assistant"
                with st.chat_message(role):
                    if isinstance(msg.content, str): st.write(msg.content)
                    else: st.write("[Wysłano dane wizualne/narzędzia]")

            if prompt := st.chat_input("Nowe polecenie..."):
                agent.task = prompt
                with st.spinner("Robot działa..."):
                    agent.main_loop_content() # Wywołujemy 1 krok pętli
                st.rerun()

with tab_udev:
    st.header("Zarządzanie regułami udev")
    if st.button("Skanuj urządzenia (lsusb)"):
        res = subprocess.run(["lsusb"], capture_output=True, text=True)
        st.code(res.stdout)
    
    with st.form("udev_gen"):
        v_id = st.text_input("Vendor ID (np. 1a86)")
        p_id = st.text_input("Product ID (np. 7523)")
        s_name = st.text_input("Nazwa (SYMLINK, np. arm_right)")
        if st.form_submit_button("Generuj regułę"):
            rule = f'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{v_id}", ATTRS{{idProduct}}=="{p_id}", SYMLINK+="{s_name}"'
            st.success("Zapisz to w /etc/udev/rules.d/99-robocrew.rules:")
            st.code(rule)