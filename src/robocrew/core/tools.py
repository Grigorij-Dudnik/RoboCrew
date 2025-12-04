from langchain_core.tools import tool


@tool
def finish_task():
    """Claim that task is finished and go idle. You need to ensure the task is actually finished before calling this tool."""
    return "Task finished"

from robocrew.core.memory import Memory

robot_memory = Memory()

@tool
def remember_thing(text: str):
    """
    Save a fact or observation to memory. 
    Useful for remembering locations (e.g., 'The kitchen is down the hall') or other important details.
    """
    return robot_memory.add_memory(text)

@tool
def recall_thing(query: str):
    """
    Search memory for information.
    Useful when you need to find something or remind you where a room is.
    """
    return robot_memory.search_memory(query)

# Global reference to sound_receiver for TTS tool to pause/resume listening
_sound_receiver = None

def set_sound_receiver(receiver):
    """Set the global sound receiver reference for TTS integration."""
    global _sound_receiver
    _sound_receiver = receiver

@tool
def say(query: str):
    """
    Speak a sentence aloud to the user.
    Use this to communicate verbally with the user, for example to greet them,
    answer questions, or provide status updates.
    """
    import pyttsx3
    
    # Pause listening if sound receiver is active (to avoid hearing ourselves)
    if _sound_receiver is not None:
        _sound_receiver.pause_listening()
    
    try:
        engine = pyttsx3.init()
        engine.say(query)
        engine.runAndWait()
    finally:
        # Resume listening after speech
        if _sound_receiver is not None:
            _sound_receiver.resume_listening()
    
    return f"Said: {query}"
