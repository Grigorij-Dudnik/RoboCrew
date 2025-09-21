from smolagents import CodeAgent, InferenceClientModel, ToolCallingAgent, LiteLLMModel, TransformersModel
from langfuse import get_client
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from phoenix.otel import register
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from tools import move_forward, turn

from dotenv import find_dotenv
from time import perf_counter


start = perf_counter()
find_dotenv()
dotenv_time = perf_counter()
print(f"dotenv time: {dotenv_time - start}")
# langfuse or arize
#lf = get_client()
register()
SmolagentsInstrumentor().instrument()
instrumentation_time = perf_counter()

print(f"instrumentation time: {instrumentation_time - dotenv_time}")

tool_calling_agent_system_prompt = "You are mobile robot with two arms. Your task is to go forward and turn."


class LLMAgent(ToolCallingAgent):
    def __init__(self, model, tools, system_prompt=None):
        super().__init__(model=model, tools=tools)
        self.prompt_templates["system_prompt"] = system_prompt or tool_calling_agent_system_prompt


model = LiteLLMModel(model_id="gpt-4.1-nano")
#model = TransformersModel(model_id="google/gemma-3n-E2B-it")

agent = LLMAgent(
    tools=[
        move_forward,
        turn
        ], 
        model=model
        )

result = agent.run("Start!")
