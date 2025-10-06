from smolagents import ToolCallingAgent, LiteLLMModel, TransformersModel
#from openinference.instrumentation.smolagents import SmolagentsInstrumentor
#from phoenix.otel import register
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
from pydantic_ai import Agent


load_dotenv(find_dotenv())
dotenv_time = perf_counter()
# langfuse or arize
# register()
# SmolagentsInstrumentor().instrument()


tool_calling_agent_system_prompt = "You are mobile robot with two arms."



class LLMAgent(Agent):
    def __init__(self, model, tools, system_prompt=None):
        system_prompt = system_prompt or tool_calling_agent_system_prompt
        super().__init__(model=model, tools=tools, system_prompt=system_prompt)
        self.message_history = []


    def go(self):
        while True:
            response = self.run_sync("go")
            print("Agent response:", response)

if __name__ == "__main__":
    agent = LLMAgent(
        model="openai:gpt-4.1-nano",
        tools=[
            # move_forward,
            # turn_right,
            # turn_left,
            # stop
        ]
    )
    result = agent.go()
    print(result)