# -*- coding: utf-8 -*-
"""
Polly - Polish TTS module using Piper voice synthesis.
(Get it? POLish + talking like a parrot = Polly!)
"""
import subprocess
from piper.voice import PiperVoice
from pathlib import Path

# Global voice instances (cached by model path)
_voices = {}


def _get_voice(model_path):
    """Get or initialize the voice instance for a given model."""
    if model_path not in _voices:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        _voices[model_path] = PiperVoice.load(model_path)
    return _voices[model_path]


def say(text, model_path):
    """
    Synthesize and play text using Polish TTS.
    
    Args:
        text (str): Text to speak
        model_path (str): Path to ONNX model file (required)
    """
    voice = _get_voice(model_path)
    
    # Get audio chunks
    audio_chunks = list(voice.synthesize(text))
    
    if audio_chunks:
        # Start aplay process
        sample_rate = audio_chunks[0].sample_rate
        process = subprocess.Popen(
            ["aplay", "-r", str(sample_rate), "-f", "S16_LE", "-t", "raw", "-q"],
            stdin=subprocess.PIPE
        )
        
        # Stream audio chunks to aplay
        for chunk in audio_chunks:
            process.stdin.write(chunk.audio_int16_bytes)
        
        process.stdin.close()
        process.wait()


if __name__ == "__main__":
    # Test the module
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python polly.py <path_to_model.onnx>")
        print("Example: python polly.py /path/to/pl_PL-gosia-medium.onnx")
        sys.exit(1)
    
    model = sys.argv[1]
    say("Test syntezy mowy w języku polskim.", model_path=model)
    print("Audio played successfully")