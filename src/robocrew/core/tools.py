from langchain_core.tools import tool
from robocrew.core.memory import Memory
from robocrew.core.utils import stop_listening_during_tool_execution
from robocrew.core.voice_synth import speak_and_play


@tool
def finish_task(report: str = "Task finished"):
    """Signal that the current task is complete or cannot be completed.
    Provide a brief report of what was accomplished or why you're stuck.

    Call this when:
    - Task is done
    - You are stuck and cannot make progress after 3+ attempts"""
    return report


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
    @stop_listening_during_tool_execution(sound_receiver)
    def say(query: str):
        """
        Speak a sentence aloud to the user.
        Use this to communicate verbally with the user, for example to greet them,
        answer questions, or provide status updates.
        """
        speak_and_play(query)
        return f"Said: {query}"
    return say


def create_execute_subtask(executor):
    """
    Factory function to create the 'execute_subtask' tool for the Planner agent.
    Takes a controller LLMAgent instance and returns a tool that delegates
    subtasks to it, blocking until the controller finishes.
    """
    @tool
    def execute_subtask(reasoning: str, subtask: str) -> str:
        """Delegate a concrete subtask to the robot controller.
        Write the 'reasoning' parameter first, before writing 'subtask'!

        reasoning: Think step by step about what you see and why you chose this subtask.
        The executor handles low-level navigation and manipulation.
        Blocks until the controller finishes. Returns a completion report."""
        executor.task = subtask
        result = None
        while executor.task:
            result = executor.main_loop_content()
        return result
    return execute_subtask
