from robocrew.core.tools import remember_thing, recall_thing
from robocrew.core.skills import load_skills
from dotenv import find_dotenv, load_dotenv
import time
import base64
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model


load_dotenv(find_dotenv())


base_system_prompt = """
## ROBOT SPECS
- Mobile household robot with two arms

## NAVIGATION RULES
- Check angle grid at top of image - target must be within ±15° of center before moving forward
- Watch for obstacles in your path - if obstacle blocks the way, navigate around it first
- Never call move_forward 3+ times if nothing changes
- If target is off-center: use turn_left or turn_right to align BEFORE moving forward
- Reference floor meters only if floor visible and scale not on objects
- Watch for obstacles between you and target - plan path to avoid them
"""

class LLMAgent():
    def __init__(
            self,
            model: str,
            tools: list,
            main_camera,
            name: str | None = None,
            system_prompt: str | None = None,
            thinking_level: str | None = None,
            camera_fov: float = 90,
            servo_controler=None,
            history_len: int | None = None,
            use_memory: bool = False,
            skills: list | None = None,
            skills_dir=None,
            skill_context=None,
        ):
        """
        model: name of the model to use (e.g. 'google_genai:gemini-3.1-pro-preview').
        tools: list of langchain tools.
        main_camera: robot front camera object.
        name: optional agent name shown in logs (e.g. 'Planner', 'Controller').
        system_prompt: custom system prompt - optional.
        thinking_level: Gemini 3.x thinking effort level. Options: 'minimal', 'low', 'medium', 'high'.
            Gemini 3.1 Pro supports 'low' and 'high' only. Gemini 3 Flash supports all four levels.
        camera_fov: field of view (degrees) of the main camera.
        history_len: number of newest request-response pairs to keep in context.
        use_memory: set to True to enable long-term memory (requires sqlite3).
        skills: optional SKILL.md folder names or paths.
        skills_dir: base directory for skill names.
        skill_context: object passed to optional skill tool factories.
        """
        system_prompt = system_prompt or base_system_prompt
        self.name = name
        
        if use_memory:
            
            tools.append(remember_thing)
            tools.append(recall_thing)
            memory_prompt = (
                " You have a memory. When you find important things (like a specific room, object, or person) "
                "or complete a navigation step, use the `remember_thing` tool to save it for later. "
                "Do not wait for the user to tell you to remember. Be proactive."
            )
            system_prompt += memory_prompt

        self.task = None
        self.idle = True
        self.navigation_mode = "normal"  # or "precision"

        if skills:
            skills_prompt, skills_tools = load_skills(skills, skills_dir=skills_dir, context=skill_context)
            system_prompt += "\n\n" + skills_prompt
            tools.extend(skills_tools)

        model_kwargs = {}
        if thinking_level is not None:
            model_kwargs["generation_config"] = {"thinking_config": {"thinking_level": thinking_level.upper()}}

        llm = init_chat_model(model, model_kwargs=model_kwargs or {})
        #llm = init_chat_model(model="google/gemini-3-flash-preview", model_provider="openai", base_url="https://openrouter.ai/api/v1", api_key=getenv("OPENROUTER_API_KEY"))
        self.llm = llm.bind_tools(tools)#, parallel_tool_calls=False)
        self.tools = tools
        self.tool_name_to_tool = {tool.name: tool for tool in self.tools}
        self.system_message = SystemMessage(content=system_prompt)
        self.message_history = [self.system_message]
        self.history_len = history_len
        # cameras
        self.main_camera = main_camera
        self.camera_fov = camera_fov
        self.servo_controler = servo_controler

        if self.servo_controler and self.servo_controler.left_arm_head_usb:
            self.servo_controler.reset_head_position()
            self.servo_controler.set_saved_position("default", "both")  # optionally if you have saved positions (example 5_xlerobot_test_save_recall_positions), set a default position for both arms before starting the agent.


    def invoke_tool(self, tool_call):
        # convert string to real function
        requested_tool = self.tool_name_to_tool[tool_call["name"]]
        args = tool_call["args"]
        trace_config = self.trace_config(f"{self.name} / {tool_call['name']}")
        if trace_config:
            tool_output = requested_tool.invoke(args, config=trace_config)
        else:
            tool_output = requested_tool.invoke(args)
        # f aitional output is present
        if isinstance(tool_output, tuple) and len(tool_output) == 2:
            additional_output = HumanMessage(content=tool_output[1])
            tool_output = tool_output[0]
        else:
            additional_output = None
        return ToolMessage(tool_output, tool_call_id=tool_call["id"]), additional_output

    def trace_config(self, run_name=None):
        if not self.name:
            return None
        return {
            "run_name": run_name or self.name,
            "tags": [f"agent:{self.name}"],
            "metadata": {"agent_name": self.name},
        }
    
    def cut_off_context(self, nr_of_loops):
        """
        Trims the message history in the state to keep only the most recent context for the agent.
        """        
        ai_indices = [i for i, msg in enumerate(self.message_history) if msg.type == "human"]
        if len(ai_indices) >= nr_of_loops:
            start_index = ai_indices[-nr_of_loops]
            self.message_history = [self.system_message] + self.message_history[start_index:]

    def fetch_camera_images_base64(self):
            image_bytes = self.main_camera.capture_image(camera_fov=self.camera_fov, navigation_mode=self.navigation_mode)
            return [base64.b64encode(image_bytes).decode('utf-8')]

    def extra_loop_content(self):
        return []

    def main_loop_content(self):
        camera_images = self.fetch_camera_images_base64()
        
        content=[
                {"type": "text", "text": "Main camera view:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{camera_images[0]}"}
                }
        ]
        if self.task:
            content.append({"type": "text", "text": f"\n\nYour task is: '{self.task}'"})
        
        content.extend(self.extra_loop_content())

        message = HumanMessage(content)
        return self.invoke_llm_with_message(message)

    def invoke_llm_with_message(self, message):
        self.message_history.append(message)
        trace_config = self.trace_config()
        if trace_config:
            response = self.llm.invoke(self.message_history, config=trace_config)
        else:
            response = self.llm.invoke(self.message_history)
        print(response.content)
        reasoning_tokens = response.usage_metadata.get('output_token_details', {}).get('reasoning', 0)
        if reasoning_tokens:
            print(f"[thinking: {reasoning_tokens} tokens]")
        for tool_call in response.tool_calls:
            print(f"Calling {tool_call['name']} with {tool_call['args']} args")
        
        
        self.message_history.append(response)
        if self.history_len:
            self.cut_off_context(self.history_len)
        return self.execute_tool_calls(response.tool_calls)

    def execute_tool_calls(self, tool_calls):
        result = None
        for tool_call in tool_calls:
            tool_response, additional_response = self.invoke_tool(tool_call)
            self.message_history.append(tool_response)
            if additional_response:
                self.message_history.append(additional_response)
            if tool_call["name"] == "go_to_precision_mode":
                self.navigation_mode = "precision"
            elif tool_call["name"] == "go_to_normal_mode":
                self.navigation_mode = "normal"
            if tool_call["name"] == "finish_task":
                report = tool_call["args"].get("report", "Task finished")
                self.task = None
                self.idle = True
                print(f"Task finished: {report}")
                result = report
        return result

    def cleanup(self):
        if self.servo_controler:
            print("Disconnecting servo controller...")
            self.servo_controler.disconnect()

    def check_for_new_input(self):
        return False

    def go(self):
        try:
            while True:
                if self.task or self.check_for_new_input():
                    self.idle = False
                if not self.idle:
                    self.main_loop_content()
                else:
                    # idle mode
                    time.sleep(0.5)

        except KeyboardInterrupt:
            print("Interrupted by user, shutting down.")

        finally:
            self.cleanup()
