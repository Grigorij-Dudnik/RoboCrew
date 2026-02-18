import os
import sys
import subprocess
import urllib.request
import time

# --- PATH CONFIGURATION ---
# Get the absolute path of the current script directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# All assets will be stored in this subfolder
DATA_DIR = os.path.join(BASE_DIR, "piper_data")

# Full paths for the model, config, and output audio
MODEL_PATH = os.path.join(DATA_DIR, "en_amy.onnx")
CONFIG_PATH = os.path.join(DATA_DIR, "en_amy.onnx.json")    
OUTPUT_WAV = os.path.join(DATA_DIR, "speech.wav")

# Download URLs (Amy Low voice)
MODEL_URL = "https://github.com/rhasspy/piper/releases/download/v1.0.0/voice-en-gb-amy-low.onnx"
CONFIG_URL = "https://github.com/rhasspy/piper/releases/download/v1.0.0/voice-en-gb-amy-low.onnx.json"

def install_dependencies():
    """Install required python packages if they are missing."""
    # Added 'pathvalidate' as it's a hidden dependency for Piper on many systems
    packages = ["piper-tts", "pygame", "pathvalidate"]
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            print(f"Installing {package}...")
            args = [sys.executable, "-m", "pip", "install", package]
            # Handle Linux/macOS global install restrictions
            if os.name != "nt" and "venv" not in sys.prefix:
                args.append("--break-system-packages")
            subprocess.check_call(args)

def setup_voice():
    """Ensure data directory exists and download voice files if missing."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # Download model if not exists or file is corrupted (too small)
    if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) < 100:
        print(f"Downloading model to {MODEL_PATH}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        
    # Download config if not exists
    if not os.path.exists(CONFIG_PATH) or os.path.getsize(CONFIG_PATH) < 100:
        print(f"Downloading config to {CONFIG_PATH}...")
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)

def speak_and_play(text):
    """Synthesize text to speech and play it immediately."""
    try: 
        # Execute Piper as a module
        # We use absolute paths to avoid 'File Not Found' errors
        result = subprocess.run([
            sys.executable, "-m", "piper",
            "--model", MODEL_PATH,
            "--config", CONFIG_PATH,
            "--output_file", OUTPUT_WAV
        ], input=text.encode('utf-8'), check=True, capture_output=True)
        
    except subprocess.CalledProcessError as e:
        # Log specific Piper error message (very useful for debugging)
        print(f"Piper Process Error: {e.stderr.decode()}")
        return
    except Exception as e:
        print(f"Unexpected Error during synthesis: {e}")
        return

    # Audio Playback using Pygame
    try:
        import pygame
        pygame.mixer.init()
        # Load using the full absolute path
        pygame.mixer.music.load(OUTPUT_WAV)
        pygame.mixer.music.play()
        
        print("Playing synthesized speech...")
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
            
        pygame.mixer.quit()
    except Exception as e:
        print(f"Playback Error: {e}")

if __name__ == "__main__":
    # Initialize environment
    install_dependencies()
    setup_voice()

    # Verify files are present before starting
    if os.path.exists(MODEL_PATH) and os.path.exists(CONFIG_PATH):
        test_message = "The voice system is initialized. Everything is working correctly."
        speak_and_play(test_message)
    else:
        print("Error: Voice files are missing. Check your internet connection.")