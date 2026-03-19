import streamlit as st
import subprocess
import logging

from utils import get_hardware_status
from agent_setup import init_agent
from tab_conversation import render_conversation_tab
from tab_manual import render_manual_tab
from tab_dataset import render_dataset_tab
from tab_config import render_config_tab
from tab_vla import render_vla_tab

logging.getLogger('watchdog').setLevel(logging.ERROR)

st.set_page_config(page_title="RoboCrew Dashboard", layout="wide", page_icon="🤖")

# --- STYLE CSS ---
st.markdown("""
    <style>
    /* 1. Ukrycie nagłówków i reset marginesów */
    [data-testid="stHeader"], [data-testid="stSidebarHeader"] { display: none !important; }
    .block-container, [data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }

    /* 2. CHIRURGICZNE ODBLOKOWANIE: Tylko wewnętrzne kontenery, zachowujemy natywny sidebar! */
    [data-testid="stMainBlockContainer"], [data-testid="stTabs"] {
        overflow: visible !important;
    }

    /* 3. ZAKŁADKI STICKY */
    [data-testid="stTabs"] > div > div:first-of-type {
        position: sticky !important;
        top: 0 !important;
        z-index: 9999 !important;
        background-color: rgb(14, 17, 23) !important; /* Tło pod zakładkami */
        padding: 1rem 0 0.5rem 0 !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Kosmetyka */
    button[data-baseweb="tab"] p { font-size: 1.15rem !important; }
    h2, h3 { margin-top: 0 !important; padding-top: 0 !important; }
    </style>
""", unsafe_allow_html=True)

# --- RESZTA KODU BEZ ZMIAN ---
if "agent" not in st.session_state:
    st.session_state.agent = None
if "init_error" not in st.session_state:
    st.session_state.init_error = ""
if "recording_process" not in st.session_state:
    st.session_state.recording_process = None
if "agent_active" not in st.session_state:
    st.session_state.agent_active = False
if "agent_step" not in st.session_state:
    st.session_state.agent_step = 0

if "init_attempted" not in st.session_state:
    st.session_state.init_attempted = True
    init_agent()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## RoboCrew Control Center")
    st.divider()

    st.markdown("### 🔌 Hardware Health")
    hw_status = get_hardware_status()
    
    if hw_status:
        status_lines = []
        for name, info in hw_status.items():
            if info["state"] == "disconnected":
                status_lines.append(f"<span style='color:grey;'>⚪ **{name}**: {info['label']}</span>")
            elif info["state"] == "error": 
                status_lines.append(f"🔴 **{name}**: {info['label']}")
            elif info["state"] == "warning": 
                status_lines.append(f"🟡 **{name}**: {info['label']}")
            else: 
                status_lines.append(f"🟢 **{name}**: {info['label']}")
        st.markdown("  \n".join(status_lines), unsafe_allow_html=True)
    else:
        st.info("No hardware aliases found.")
            
    st.divider()

    if st.button("🛑 EMERGENCY STOP", type="primary", use_container_width=True):
        if st.session_state.agent:
            st.session_state.agent.task = None
        st.session_state.agent_active = False
        st.session_state.agent_step = 0
        
        if st.session_state.recording_process:
            st.session_state.recording_process.terminate()
            subprocess.run(["pkill", "-f", "lerobot-record"])
            subprocess.run(["pkill", "-f", "ttyd"])
            st.session_state.recording_process = None
            
        st.toast("🛑 System force-stopped by user!", icon="🛑")
        st.rerun()

    if not st.session_state.agent and not st.session_state.recording_process:
        st.divider()
        if st.button("🔄 Retry Initialization", use_container_width=True):
            init_agent()
            st.rerun()

# --- MAIN UI ---
missing_required = []
if hw_status:
    for name, info in hw_status.items():
        if info.get("required") and info["state"] == "disconnected":
            missing_required.append(name)

if missing_required:
    pass # Message handled below before rendering tabs
elif st.session_state.recording_process:
    st.warning("🎥 Dataset recording is active! LLM Agent is suspended.")
elif not st.session_state.agent:
    st.error("Robot cannot be initialized.")

if missing_required:
    st.error(f"⚠️ Missing required hardware: **{', '.join(missing_required)}**.")
    st.info("Please use the Udev Rules Wizard below to connect the missing devices before proceeding.")
    render_config_tab()
else:
    tab_chat, tab_udev, tab_vla, tab_dataset, tab_manual = st.tabs(["💬 Conversation", "🛠️ Config", "🦾 VLA Tools", "🎥 Data Collection", "🕹️ Manual"])

    with tab_chat:
        render_conversation_tab()
    with tab_udev:
        render_config_tab()
    with tab_dataset:
        render_dataset_tab()
    with tab_vla:
        render_vla_tab()
    with tab_manual:
        render_manual_tab()