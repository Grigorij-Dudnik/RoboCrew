# Polly 🦜

Polish TTS (Text-to-Speech) module using Piper voice synthesis.

*Get it? **POL**ish + talking like a parrot = **Polly**!*

## Installation

```bash
pip install -e .
```

## Requirements

- Python 3.6+
- piper-tts
- aplay (ALSA audio player)
- A Piper ONNX voice model

## Getting a Voice Model

Download a Polish voice model from [Piper voices](https://github.com/rhasspy/piper/releases). For example:
- `pl_PL-gosia-medium.onnx`

**Note:** Model files are not included in this repository due to licensing. You must download them separately.

## Usage

```python
import polly

# You must specify the path to your model file
MODEL = "/path/to/your/pl_PL-gosia-medium.onnx"

polly.say("Witaj świecie!", model_path=MODEL)
polly.say("Polly chce krakersa", model_path=MODEL)
```

Or run directly:

```bash
python polly.py /path/to/pl_PL-gosia-medium.onnx
```
