from smolagents import CodeAgent, InferenceClientModel, ToolCallingAgent, LiteLLMModel, TransformersModel
from langfuse import get_client
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from phoenix.otel import register
from tools import move_forward, turn

from dotenv import find_dotenv
from time import perf_counter


find_dotenv()
dotenv_time = perf_counter()
# langfuse or arize
# register()
# SmolagentsInstrumentor().instrument()


tool_calling_agent_system_prompt = "You are mobile robot with two arms. Your task is to go forward and turn."



class LLMAgent(ToolCallingAgent):
    def __init__(self, model_id, tools, system_prompt=None):
        model = LiteLLMModel(model_id=model_id)
        super().__init__(model=model, tools=tools)
        self.prompt_templates["system_prompt"] = system_prompt or tool_calling_agent_system_prompt




