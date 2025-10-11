import pyaudio
import wave
import sys

# Audio parameters tuned for Raspberry Pi
CHUNK = 4096        # Larger buffer to prevent overflow
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000        # Lower sample rate reduces CPU load
RECORD_SECONDS = 5
OUTPUT_FILENAME = "output.wav"

def find_usb_device():
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            name = info['name']
            if "USB PnP Sound Device" in name:
                print(f"Found USB device: {name} (Index: {i})")
                p.terminate()
                return i
    p.terminate()
    raise RuntimeError("USB PnP Sound Device not found!")

def record_audio():
    p = pyaudio.PyAudio()
    try:
        device_index = find_usb_device()

        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK,
            # Optional: add exception_on_overflow=False to suppress overflow errors
        )

        print(f"* Recording {RECORD_SECONDS} seconds at {RATE} Hz...")
        frames = []

        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK, exception_on_overflow=False)  # <-- key fix
            frames.append(data)

        print("* Done recording")

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save to WAV
        wf = wave.open(OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        print(f"Saved to {OUTPUT_FILENAME}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    record_audio()