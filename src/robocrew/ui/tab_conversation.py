# -*- coding: utf-8 -*-
import streamlit as st
try: import speech_recognition as sr
except: pass

def render_conversation_tab():
    if not st.session_state.agent: return st.info("LLM Agent offline.")
    
    # CSS: Ukrycie strzałki w st.chat_input i usunięcie zbędnych marginesów
    st.markdown("""
        <style>
        button[data-testid="stChatInputSubmitButton"] { display: none !important; }
        div[data-testid="stChatInput"] { margin-right: 0 !important; }
        </style>
    """, unsafe_allow_html=True)

    col_v, col_c = st.columns([1, 1])
    
    with col_v:
        try:
            imgs = st.session_state.agent.fetch_camera_images_base64()
            if imgs: st.image(f"data:image/jpeg;base64,{imgs[0]}", width="stretch")
        except: st.error("Vision broken")
        
        # Puste miejsce, do którego zaraz wstrzykniemy przycisk STOP i spinner
        status_container = st.container()
                
    with col_c:
        chat_container = st.container(height=370)
        with chat_container:
            for msg in st.session_state.agent.message_history:
                if msg.type == "system": continue
                if msg.type == "tool":
                    with st.chat_message("assistant"):
                        with st.expander(f"🛠️ {msg.name or 'System Action'}"): st.write(msg.content)
                    continue
                with st.chat_message("user" if msg.type == "human" else "assistant"):
                    if isinstance(msg.content, str): st.write(msg.content)
                    elif isinstance(msg.content, list):
                        for item in msg.content:
                            if item.get("type") == "text": st.write(item.get("text"))
                            elif item.get("type") == "image_url": st.markdown("🖼️ *[Image]*")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls: st.info(f"⚙️ {tc['name']}")
        
        c_in, c_mic = st.columns([4.2, 2.8], vertical_alignment="bottom")
        with c_in: p_text = st.chat_input("Command...", disabled=st.session_state.agent_active)
        with c_mic: audio = st.audio_input("Mic", disabled=st.session_state.agent_active, label_visibility="collapsed")
        
        final_p = p_text
        if audio and audio != st.session_state.get("last_audio"):
            st.session_state.last_audio = audio
            try:
                r = sr.Recognizer()
                with sr.AudioFile(audio) as src: final_p = r.recognize_google(r.record(src))
            except: status_container.error("Mic error")

        if final_p:
            st.session_state.agent.task, st.session_state.agent_active, st.session_state.agent_step = final_p, True, 0
            st.rerun()

    # Logika agenta odpalana na końcu, ale renderowana w lewej kolumnie
    if st.session_state.agent_active:
        with status_container:
            if st.button("🛑 STOP", use_container_width=True):
                st.session_state.agent_active, st.session_state.agent.task = False, None
                st.rerun()
                
            with st.spinner(f"🧠 Step {st.session_state.agent_step+1}"):
                res = st.session_state.agent.main_loop_content()
                st.session_state.agent_step += 1
        
        last_msg = st.session_state.agent.message_history[-1]
        
        # Zakończ jeśli narzędzie finish_task to zgłosi, LUB jeśli ostatnia wiadomość to czyste AI bez użycia narzędzi
        if res == "Task finished, going idle." or (last_msg.type == "ai" and not getattr(last_msg, "tool_calls", [])):
            st.session_state.agent_active, st.session_state.agent.task = False, None
            
        st.rerun()