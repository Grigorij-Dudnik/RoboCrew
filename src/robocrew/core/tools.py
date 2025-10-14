from langchain_core.tools import tool


@tool
def finish_task():
    """Claim that task is finished and go idle. You need to ensure the task is actually finished before calling this tool."""
    return "Task finished"

