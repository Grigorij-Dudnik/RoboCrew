# -*- coding: utf-8 -*-
import streamlit as st
import json
import os

VLA_FILE = "vla_tools.json"

def load_vla():
    return json.load(open(VLA_FILE, "r")) if os.path.exists(VLA_FILE) else []

def save_vla(data):
    json.dump(data, open(VLA_FILE, "w"))

def render_vla_tab():    
    if "vla_cfg" not in st.session_state:
        st.session_state.vla_cfg = load_vla()
    if "edit_idx" not in st.session_state:
        st.session_state.edit_idx = None
        
    cfg = st.session_state.vla_cfg
    
    # --- LISTA NARZĘDZI ---
    if cfg:
        for i, t in enumerate(cfg):
            t.setdefault("active", True)
            bg_color = "rgba(19, 130, 70, 0.2)" if t["active"] else "rgba(180, 40, 40, 0.2)"
            st.markdown(f"<style>div[data-testid='stHorizontalBlock']:has(.vla-row-{i}) {{ background-color: {bg_color}; border-radius: 5px; padding: 5px; }}</style>", unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns([0.5, 4, 0.5, 0.5], vertical_alignment="center")
            if c1.checkbox("Toggle", t["active"], key=f"act_{i}", label_visibility="collapsed") != t["active"]:
                t["active"] = not t["active"]; save_vla(cfg); st.rerun()
            
            c2.markdown(f"<span class='vla-row vla-row-{i}'></span>🦾 **{t['tool_name']}** (`{t['policy_name']}`)", unsafe_allow_html=True)
            
            if c3.button("📝", key=f"edit_btn_{i}", help="Edytuj"):
                st.session_state.edit_idx = i
                st.rerun()
            if c4.button("🗑️", key=f"del_vla_{i}"):
                cfg.pop(i); save_vla(cfg); st.rerun()
    else:
        st.info("No custom VLA tools defined.")
        
    st.divider()

    # --- FORMULARZ (DODAWANIE / EDYCJA) ---
    idx = st.session_state.edit_idx
    is_edit = idx is not None
    cur = cfg[idx] if is_edit else {}

    with st.form("vla_form", clear_on_submit=not is_edit):
        st.subheader("📝 Edit Tool" if is_edit else "➕ Add New VLA Manipulation Tool")
        c1, c2 = st.columns(2)
        name = c1.text_input("Tool Name", placeholder="Pick_up_object", value=cur.get("tool_name", ""))
        desc = c2.text_input("Description", placeholder="Tool description that LLM sees", value=cur.get("tool_description", ""))
        prompt = c1.text_input("Task Prompt", placeholder="Task instruction that VLA sees", value=cur.get("task_prompt", ""))
        server = c2.text_input("Server Address", cur.get("server_address", "0.0.0.0:8080"))
        
        c3, c4, c5 = st.columns(3)
        p_name = c3.text_input("Policy Repo", placeholder="username/policy-name", value=cur.get("policy_name", ""))
        policy_types = ["act", "smolvla", "pi0", "pi05", "groot", "xvla"]
        p_type = c4.selectbox("Type", policy_types, index=policy_types.index(cur.get("policy_type", "act")))
        p_dev = c5.selectbox("Device", ["cpu", "cuda", "mps"], index=["cpu", "cuda", "mps"].index(cur.get("policy_device", "cpu")))
        
        c6, c7 = st.columns(2)
        port = c6.text_input("Arm Port", cur.get("arm_port", "/dev/arm_right"))
        ex_time = c7.number_input("Execution Time (s)", 5, 120, cur.get("execution_time", 30))
        
        submit_label = "Save" if is_edit else "➕ Add Tool"
        if st.form_submit_button(submit_label, use_container_width=True):
            new_data = {
                "tool_name": name, "tool_description": desc, "task_prompt": prompt, 
                "server_address": server, "policy_name": p_name, "policy_type": p_type,
                "policy_device": p_dev, "arm_port": port, "execution_time": ex_time,
                "active": cur.get("active", True)
            }
            if is_edit:
                cfg[idx] = new_data
                st.session_state.edit_idx = None
            else:
                cfg.append(new_data)
            
            save_vla(cfg)
            st.success("Saved! Restart the agent to apply changes.")
            st.rerun()

    if is_edit:
        if st.button("❌ Cancel Edit", use_container_width=True):
            st.session_state.edit_idx = None
            st.rerun()