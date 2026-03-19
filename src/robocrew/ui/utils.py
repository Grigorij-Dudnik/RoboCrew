# -*- coding: utf-8 -*-
import os
import re
import socket
import subprocess
import streamlit as st

RULES_FILE = "/etc/udev/rules.d/99-robocrew.rules"

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
        with open(RULES_FILE, "r") as f:
            content = f.read()
        aliases = sorted(list(set(re.findall(r'SYMLINK\+="(.*?)"', content))))
    
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