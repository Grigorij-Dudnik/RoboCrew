# Use a pipeline as a high-level helper
from transformers import pipeline

pipe = pipeline("image-text-to-text", model="google/gemma-3n-E4B-it")
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "be big dzik"}
        ]
    },
]
pipe(text=messages)