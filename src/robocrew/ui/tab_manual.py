import streamlit as st
from robocrew.robots.XLeRobot.tools import (
    create_move_forward, \
    create_move_backward, \
    create_turn_left, \
    create_turn_right, \
    create_strafe_left, \
    create_strafe_right
)

def render_manual_tab():
    if st.session_state.agent:
        col_c, col_btn = st.columns([2, 1])
        with col_c:
            try:
                imgs = st.session_state.agent.fetch_camera_images_base64()
                if imgs: st.image(f"data:image/jpeg;base64,{imgs[0]}", width="stretch")
            except Exception as e:
                st.error(f"Vision link broken: {e}")
                
        with col_btn:
            ctrl = st.session_state.agent.servo_controler
            
            c1, c2, c3 = st.columns(3)
            if c1.button("↺", key="t_l", use_container_width=True): create_turn_left(ctrl).invoke({"angle_degrees": 15}); st.rerun()
            if c2.button("⬆️", key="m_f", use_container_width=True): create_move_forward(ctrl).invoke({"distance_meters": 0.1}); st.rerun()
            if c3.button("↻", key="t_r", use_container_width=True): create_turn_right(ctrl).invoke({"angle_degrees": 15}); st.rerun()
            
            c4, c5, c6 = st.columns(3)
            if c4.button("⬅️", key="s_l", use_container_width=True): create_strafe_left(ctrl).invoke({"distance_meters": 0.1}); st.rerun()
            if c5.button("⬇️", key="m_b", use_container_width=True): create_move_backward(ctrl).invoke({"distance_meters": 0.1}); st.rerun()
            if c6.button("➡️", key="s_r", use_container_width=True): create_strafe_right(ctrl).invoke({"distance_meters": 0.1}); st.rerun()