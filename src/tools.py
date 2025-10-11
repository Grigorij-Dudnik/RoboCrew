from langchain_core.tools import tool


@tool
def finish_task():
    """claim that task is finished and go idle."""
    return "Task finished"

