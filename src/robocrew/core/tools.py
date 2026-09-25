from langchain_core.tools import tool


@tool
def finish_task(report: str = "Task finished"):
    """Signal that the current task is complete or cannot be completed.
    Provide a brief report of what was accomplished or why you're stuck.

    Call this when:
    - Task is done
    - You are stuck and cannot make progress after 3+ attempts"""
    return report


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
