import os
import sys
import subprocess
import urllib.request
import time
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame


DATA_DIR = "/home/pi/.cache/robocrew"
MODEL_PATH = os.path.join(DATA_DIR, "en_amy.onnx")
CONFIG_PATH = os.path.join(DATA_DIR, "en_amy.onnx.json")    
OUTPUT_WAV = os.path.join(DATA_DIR, "speech.wav")


def setup_voice():
    if not os.path.exists(DATA_DIR):
        print(f"Tworzenie folderu: {DATA_DIR}")
        os.makedirs(DATA_DIR, exist_ok=True)
    # Download model if not exists or file is corrupted (too small)
    if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) < 100:
        print(f"Downloading model to {MODEL_PATH}...")
        model_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx"
        urllib.request.urlretrieve(model_url, MODEL_PATH)
    # Download config
    if not os.path.exists(CONFIG_PATH) or os.path.getsize(CONFIG_PATH) < 100:
        print(f"Downloading config to {CONFIG_PATH}...")
        config_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx.json"
        urllib.request.urlretrieve(config_url, CONFIG_PATH)


def speak_and_play(text):
    setup_voice() 
    """Synthesize text to speech and play it immediately."""
    result = subprocess.run([
        sys.executable, "-m", "piper",
        "--model", MODEL_PATH,
        "--config", CONFIG_PATH,
        "--output_file", OUTPUT_WAV
    ], input=text.encode('utf-8'), check=True, capture_output=True)
    
    pygame.mixer.init(frequency=22050)
    pygame.mixer.music.load(OUTPUT_WAV)
    pygame.mixer.music.play()
    
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
        
    pygame.mixer.quit()

