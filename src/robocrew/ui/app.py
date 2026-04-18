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

st.set_page_config(page_title="RoboCrew Dashboard", layout="wide", page_icon="🦾")

st.markdown("""
    <style>
    [data-testid="stHeader"], [data-testid="stSidebarHeader"] { display: none !important; }
    .block-container, [data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }
    [data-testid="stMainBlockContainer"], [data-testid="stTabs"] { overflow: visible !important; }
    
    /* LIGHT MODE (DEFAULT) */
    [data-testid="stTabs"] > div > div:first-of-type {
        position: sticky !important; top: 0 !important; z-index: 9999 !important;
        background-color: rgb(255, 255, 255) !important; /* Solid White */
        padding: 1rem 0 0.5rem 0 !important;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2) !important;
    }
    
    /* DARK MODE OVERRIDE */
    @media (prefers-color-scheme: dark) {
        [data-testid="stTabs"] > div > div:first-of-type {
            background-color: rgb(14, 17, 23) !important; /* Streamlit Dark */
        }
    }
    
    button[data-baseweb="tab"] p { font-size: 1.15rem !important; }
    h2, h3 { margin-top: 0 !important; padding-top: 0 !important; }
    </style>
""", unsafe_allow_html=True)

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

@st.fragment(run_every="2s")
def render_hardware_health():
    st.markdown("### 🔌 Hardware Health")
    hw_status = get_hardware_status()
    
    if hw_status:
        status_lines = []
        for name, info in hw_status.items():
            if info["state"] == "undefined":
                status_lines.append(f"<span style='color:grey;'>⚪ **{name}**: {info['label']}</span>")
            elif info["state"] in ["disconnected", "error"]: 
                status_lines.append(f"🔴 **{name}**: {info['label']}")
            elif info["state"] == "warning": 
                status_lines.append(f"🟡 **{name}**: {info['label']}")
            else: 
                status_lines.append(f"🟢 **{name}**: {info['label']}")
        st.markdown("  \n".join(status_lines), unsafe_allow_html=True)
    else:
        st.info("No hardware aliases found.")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## RoboCrew Control Center")
    st.divider()

    render_hardware_health()
            
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
hw_status = get_hardware_status()
if hw_status:
    for name, info in hw_status.items():
        if info.get("required") and info["state"] in ["disconnected", "undefined"]:
            missing_required.append(name)

if missing_required:
    st.error(f"⚠️ Missing required hardware: **{', '.join(missing_required)}**.")
    st.info("Please use the Udev Rules Wizard below to connect the missing devices before proceeding.")
    render_config_tab()
elif st.session_state.recording_process:
    st.info("📌 You are currently recording a dataset. Navigation is locked.")
    render_dataset_tab()
else:
    tabs = st.tabs(["💬 Conversation", "🛠️ Config", "🦾 VLA Tools", "🎥 VLA Dataset", "🕹️ Manual"])
    funcs = [render_conversation_tab, render_config_tab, render_vla_tab, render_dataset_tab, render_manual_tab]
    
    for tab, render_func in zip(tabs, funcs):
        with tab:
            render_func()