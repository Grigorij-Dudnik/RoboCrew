from smolagents import ToolCallingAgent, LiteLLMModel, TransformersModel

#from phoenix.otel import register
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
from pydantic_ai import Agent

from langfuse import get_client
langfuse = get_client()


load_dotenv(find_dotenv())
dotenv_time = perf_counter()
# langfuse or arize
# register()
Agent.instrument_all()


tool_calling_agent_system_prompt = "You are mobile robot with two arms."



class LLMAgent(Agent):
    def __init__(self, model, tools, system_prompt=None):
        system_prompt = system_prompt or tool_calling_agent_system_prompt
        super().__init__(model=model, tools=tools, system_prompt=system_prompt)
        self.message_history = []


    def go(self):
        while True:
            response = self.run_sync("ok", message_history=self.message_history)
            self.message_history.extend(response.new_messages())
            print(response.new_messages())

if __name__ == "__main__":

    def do_nothing():
        print("Doing nothing...")
        return "Doing nothing."
    agent = LLMAgent(
        model="openai:gpt-4.1-nano",
        tools=[
            do_nothing,
        ]
    )
    result = agent.go()
    print(result)