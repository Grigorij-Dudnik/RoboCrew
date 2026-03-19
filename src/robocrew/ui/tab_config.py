# -*- coding: utf-8 -*-
import streamlit as st
import os
import re
from utils import RULES_FILE, save_udev_rules

def render_config_tab():
    # Odczyt i wyświetlanie reguł (jeśli plik istnieje)
    lines = []
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, "r") as f: 
            lines = f.readlines()
            
        for al in sorted(set(re.findall(r'SYMLINK\+="(.*?)"', "".join(lines)))):
            col_s, col_d = st.columns([5, 1])
            dev_path = f"/dev/{al}"
            
            with col_s:
                if os.path.exists(dev_path): 
                    st.success(f"🟢 **{al}** – Connected (`-> {os.path.realpath(dev_path)}`)")
                else: 
                    st.error(f"🔴 **{al}** – Disconnected")
                    
            with col_d:
                if st.button("🗑️", key=f"del_{al}", use_container_width=True):
                    # Poprawiony warunek usuwania (bez backslasha)
                    if save_udev_rules("".join([l for l in lines if f'SYMLINK+="{al}"' not in l]))[0]: 
                        st.rerun()
                    else: 
                        st.error("Failed to delete.")
    else: 
        st.info("No udev rules file found yet.")
    
    st.divider()
    st.subheader("➕ Add/Edit Device")
    if "step" not in st.session_state: st.session_state.step = 0
    
    try:
        from robocrew.scripts.robocrew_setup_usb_modules import capture_devices, build_rule
        # Kompaktowy helper do pobierania stanu urządzeń
        get_devs = lambda: {(d["subsystem"], d["kernel"], d["phys"]): d for d in capture_devices()}
        
        if st.session_state.step == 0:
            alias_options = ["camera_center", "camera_left", "camera_right", "arm_left", "arm_right", "lidar", "Other..."]
            selected_alias = st.selectbox("Select Alias", alias_options)
            
            if selected_alias == "Other...":
                target = st.text_input("Custom Alias Name (e.g. lidar)")
            else:
                target = selected_alias
                
            if st.button("Start Wizard") and target:
                st.session_state.update({"target": target, "base": get_devs(), "step": 1})
                st.rerun()
                
        elif st.session_state.step == 1:
            st.warning(f"Disconnect `{st.session_state.target}` now.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Done"):
                    curr = get_devs()
                    if diff := set(st.session_state.base.keys()) - set(curr.keys()):
                        st.session_state.update({"base": curr, "step": 2})
                        st.rerun()
            with col2:
                if st.button("Cancel Wizard", type="secondary", use_container_width=True):
                    st.session_state.step = 0
                    st.rerun()
                    
        elif st.session_state.step == 2:
            st.info("Plug it into the target port.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Connected"):
                    curr = get_devs()
                    if diff := set(curr.keys()) - set(st.session_state.base.keys()):
                        rule = build_rule(curr[list(diff)[0]], st.session_state.target)
                        # Poprawiony warunek (bez backslasha) + dołączenie nowej reguły
                        final = [l for l in lines if f'SYMLINK+="{st.session_state.target}"' not in l] + [rule + "\n"]
                        
                        if save_udev_rules("".join(final))[0]:
                            st.session_state.step = 0
                            st.success("Saved!")
                            st.rerun()
                        else: 
                            st.error("Failed to save rule.")
            with col2:
                if st.button("Cancel Wizard", type="secondary", use_container_width=True, key="cancel_step2"):
                    st.session_state.step = 0
                    st.rerun()
                    
    except Exception as e: 
        st.error(f"Wizard Error: {e}")