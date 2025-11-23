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
    Useful when you need to find something or remember where a room is.
    """
    return robot_memory.search_memory(query)

