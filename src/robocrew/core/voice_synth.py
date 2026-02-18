import os
import sys
import subprocess
import urllib.request
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "piper_data")

MODEL_PATH = os.path.join(DATA_DIR, "en_amy.onnx")
CONFIG_PATH = os.path.join(DATA_DIR, "en_amy.onnx.json")    
OUTPUT_WAV = os.path.join(DATA_DIR, "speech.wav")

MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx"
CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low/en_US-amy-low.onnx.json"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(MODEL_PATH):
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH
                               )

def instal_dependency():
    packages = ["piper-tts", "pygame"]
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            print(f"Installing {package}...")
            args = [sys.executable, "-m", "pip", "install", package]
            if os.name != "nt":  # If not Windows, add --user flag
                args.append("--break-system-packages")
            subprocess.check_call(args)


MODEL_FILE = "en_amy.onnx"
CONFIG_FILE = "en_amy.onnx.json"

def setup_voice():
    if not os.path.exists(MODEL_FILE):
        print("Downloading voice model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_FILE)

print(f"model exists: {os.path.exists(MODEL_FILE)}/ config exists: {os.path.exists(CONFIG_FILE)}")


def speak_and_play(text):
    output_wav = "speech.wav"
    try: 
        subprocess.run([sys.executable, "-m", "piper", "--model", MODEL_PATH, "--config", CONFIG_PATH, "--output_file", output_wav], input=text.encode('utf-8'), check=True)
    except Exception as e:
        print(f"Error during speech synthesis: {e}")
        return



   
    import pygame
    pygame.mixer.init()
    pygame.mixer.music.load(output_wav)
    pygame.mixer.music.play()
    print("Playing synthesized speech...")
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    pygame.mixer.quit()

if __name__ == "__main__":
    instal_dependency()
    setup_voice()

    message = "Hello, this is a test of the voice synthesis system. I hope you can hear me clearly. Have a great day!"
    speak_and_play(message)