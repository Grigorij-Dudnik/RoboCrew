# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def generate():
    client = genai.Client(
        api_key=os.environ.get("GOOGLE_API_KEY"),
    )

    model = "gemini-robotics-er-1.5-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""You are mobile robot. what to do?"""),
            ],
        ),
    ]
    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="go_forward",
                    description="move robot forward",
                    parameters={},
                ),
            ])
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config = types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True,
        ),
        tools=tools,
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        #print(chunk.text if chunk.function_calls is None else chunk.function_calls[0])
        print(chunk)

if __name__ == "__main__":
    generate()
