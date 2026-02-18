from langchain_core.tools import tool
from robocrew.core.memory import Memory
from voice_synth import speak_and_play
import pyttsx3


@tool
def finish_task():
    """Claim that task is finished and go idle. Call this tool when you 200% sure the task is complete."""
    return "Task finished"


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


def create_say(sound_receiver=None):
    """
    Factory function to create the 'say' tool with optional sound_receiver integration.
    
    Args:
        sound_receiver: Optional SoundReceiver instance. If provided, listening will be
                       paused during speech to avoid the robot hearing itself.
    """
    @tool
    def say(query: str):
        """
        Speak a sentence aloud to the user.
        Use this to communicate verbally with the user, for example to greet them,
        answer questions, or provide status updates.
        """        
        # Stop listening if sound receiver is active (to avoid hearing ourselves)
        if sound_receiver is not None:
            sound_receiver.stop_listening()
        
        try:
            speak_and_play(query)
        finally:
            # Resume listening after speech
            if sound_receiver is not None:
                sound_receiver.start_listening()
        
        return f"Said: {query}"
    
    return say

@tool
def save_checkpoint(checkpont_query: str):
    """
    Call this tool when you complete an important step in the task to not forget about it.
    For example, if your task is to go to kitchen and cook a dinner, call this tool with "Reached kitchen" when you are in the kitchen.
    This tool will add the checkpoint info to the agent's system message for future context.
    """
    # The actual logic is handled in LLMAgent.invoke_tool
    return f"Checkpoint saved: {checkpont_query}"
