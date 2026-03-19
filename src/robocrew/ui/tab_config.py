# -*- coding: utf-8 -*-
import streamlit as st
import os
import re
from utils import RULES_FILE, save_udev_rules

def render_config_tab():
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
                    new_c = "".join([l for l in lines if f'SYMLINK\+="{al}"' not in l])
                    success, err = save_udev_rules(new_c)
                    if success:
                        st.rerun()
                    else:
                        st.error(f"Failed to delete udev rule: {err}")
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
                    final = [l for l in existing if f'SYMLINK\+="{st.session_state.target}"' not in l]
                    final.append(rule + "\n")
                    success, err = save_udev_rules("".join(final))
                    
                    if success:
                        st.session_state.step = 0
                        st.success("Saved!")
                        st.rerun()
                    else:
                        st.error(f"Failed to save rule: {err}")
                        
    except ImportError: 
        st.error("Setup scripts missing. Ensure robocrew.scripts is installed.")
    except Exception as e:
        st.error(f"Unexpected error in Setup Wizard: {e}")