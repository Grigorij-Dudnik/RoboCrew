import sys
import pyaudio
import wave
import threading
import numpy as np
import time
import os
import re
from openai import OpenAI
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())


class SoundReceiver:
    def __init__(self, sounddevice_index_or_alias, task_queue=None, wakeword="robot"):
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 48000
        self.BUFFER_SECONDS = 2
        self.frames_per_buffer = 2048
        self.recording_loop_delay = 0.2
        # parse DEVICE_INDEX env var into an int if present, else None
        if isinstance(sounddevice_index_or_alias, int) or sounddevice_index_or_alias is None:
            self.DEVICE_INDEX = sounddevice_index_or_alias
            device_alias = None
        elif isinstance(sounddevice_index_or_alias, str):
            self.DEVICE_INDEX = None
            device_alias = sounddevice_index_or_alias
        else:
            raise ValueError("sounddevice_index_or_alias must be an int, str, or None")
        self.wakeword = wakeword

        self._p = pyaudio.PyAudio()

        if self.DEVICE_INDEX is None and device_alias:
            try:
                self.DEVICE_INDEX = self._resolve_device_index(device_alias)
                print(f"✅ Resolved alias '{device_alias}' to PyAudio Device Index: {self.DEVICE_INDEX}")
            except Exception as e:
                print(f"⚠️ Warning: Could not resolve device alias '{device_alias}'.\n Error: {e}")
                self.DEVICE_INDEX = None
                sys.exit(1)

        self._sample_width = self._p.get_sample_size(self.FORMAT)
        self._bytes_per_second = int(self.RATE * self.CHANNELS * self._sample_width)
        self._buffer_capacity_bytes = int(self._bytes_per_second * self.BUFFER_SECONDS)
        self.task_queue = task_queue

        self._buffer = bytearray(self._buffer_capacity_bytes)
        self._write_pos = 0
        self._has_wrapped = False
        self._lock = threading.RLock()

        self._stream = None
        self._listening = False
        self._recording = False
        self.RMS_THRESHOLD = 400.0
        self.reciver_thread = threading.Thread(target=self._recorder_loop)
        self.reciver_thread.daemon = True
        self.recorded_frames = []
        self.first_timestamp_below_threshold = None
        self.num_recorded_buffers = 0
        self.openai_client = OpenAI()
        self.start_listening()

    def _resolve_device_index(self, alias):
            """Resolves a udev symlink alias to a PyAudio device index."""
            symlink_path = f"/dev/{alias}"

            if not os.path.exists(symlink_path):
                raise FileNotFoundError(f"Symlink {symlink_path} not found.")

            # 2. Resolve symlink to real path (e.g. /dev/snd/controlC2)
            real_path = os.path.realpath(symlink_path)

            # 3. Extract the ALSA Card Number (the '2' in 'controlC2')
            match = re.search(r"controlC(\d+)", real_path)
            if not match:
                raise ValueError(f"Could not parse ALSA card ID from {real_path}")
            
            alsa_card_index = int(match.group(1))

            # 4. Find the PyAudio device that matches this ALSA card index
            info_count = self._p.get_device_count()
            for i in range(info_count):
                info = self._p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    # ALSA names usually look like: "USB Audio Device: - (hw:2,0)"
                    # We search for "(hw:X," where X is our card index.
                    if f"(hw:{alsa_card_index}," in info['name']:
                        return i
            
            raise RuntimeError(f"ALSA Card {alsa_card_index} found, but no matching PyAudio device detected.")


    def _write_to_buffer(self, data: bytes):
        with self._lock:
            n = len(data)
            if n == 0:
                return
            end_space = self._buffer_capacity_bytes - self._write_pos
            if n <= end_space:
                self._buffer[self._write_pos:self._write_pos + n] = data
                self._write_pos += n
                if self._write_pos == self._buffer_capacity_bytes:
                    self._write_pos = 0
                    self._has_wrapped = True
            else:
                self._buffer[self._write_pos:] = data[:end_space]
                rest = n - end_space
                self._buffer[0:rest] = data[end_space:]
                self._write_pos = rest
                self._has_wrapped = True

    def _buffer_write_callback(self, in_data, frame_count, time_info, status):
        if in_data:
            self._write_to_buffer(in_data)
            if self._recording:
                with self._lock:
                    self.recorded_frames.append(in_data)
                    self.num_recorded_buffers = self.num_recorded_buffers+1
        return (None, pyaudio.paContinue)

    def _recorder_loop(self):
        while True:
            # Wait if not listening
            if not self._listening:
                time.sleep(0.1)
                continue
            loop_start_time = time.perf_counter()
            if not self._recording:
                
                if self.get_rms() > self.RMS_THRESHOLD:
                    self._recording = True
                    pre_roll_data = self.get_last_recorded_bytes(2.0)
                    with self._lock:
                        self.recorded_frames = [pre_roll_data]
            else:

                if self.get_rms() < self.RMS_THRESHOLD:
                    if self.first_timestamp_below_threshold is None:
                        self.first_timestamp_below_threshold = time.time()
                    elif time.time() - self.first_timestamp_below_threshold > 2.0:
                        self._recording = False
                        self.first_timestamp_below_threshold = None
                        # TUTAJ WHISPER BIERZE RECORDED FRAMES
                        with self._lock:
                            audio_data = b''.join(self.recorded_frames)
                            self.recorded_frames = []

                        print("Transcribing recorded audio...")
                        threading.Thread(
                            target=self._transcribe_audio, 
                            args=(audio_data,)
                        ).start()
                else:
                    self.first_timestamp_below_threshold = None
                        
            loop_execution_time = time.perf_counter() - loop_start_time 
            time.sleep(self.recording_loop_delay - loop_execution_time)


    def _transcribe_audio(self, audio_data: bytes) -> str:
        import io
        
        print(f"Buffer counter: {self.num_recorded_buffers}")
        # ONLY FOR NOW - TO AVOID SHORT WHEEL NOISES
        if self.num_recorded_buffers < 200: # Check for minimum audio length
            print("Audio data too short to transcribe.")
            return
        self.num_recorded_buffers = 0
        ram_buffer = io.BytesIO()
        ram_buffer.name = "recorded.wav"
        with wave.open(ram_buffer, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self.RATE)
            wf.writeframes(audio_data)
        ram_buffer.seek(0)


        transcription = self.openai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe", 
            file=ram_buffer
        )
        if transcription.text:  # If transcription is not ""
            print(f"transcription: {transcription.text}")
            if self.wakeword.lower() in transcription.text.lower():
                self.task_queue.put(transcription.text)


    def start_listening(self):
        print(f"Starting SoundReceiver on device index {self.DEVICE_INDEX}")
        if self._listening:
            return
        # Start stream if not already open
        if self._stream is None:
            try:
                self._stream = self._p.open(format=self.FORMAT,
                                           channels=self.CHANNELS,
                                           rate=self.RATE,
                                           input=True,
                                           input_device_index=self.DEVICE_INDEX,
                                           frames_per_buffer=self.frames_per_buffer,
                                           stream_callback=self._buffer_write_callback)
            except Exception as e:
                raise RuntimeError(f"Failed to open input stream: {e}")
            self._stream.start_stream()
            # Start the recorder thread only once
            if not self.reciver_thread.is_alive():
                self.reciver_thread.start()
        else:
            # Resume the stream if it was stopped
            self._stream.start_stream()
        self._listening = True

    def stop_listening(self):
        """Stop audio processing (used during TTS to avoid self-hearing)."""
        if not self._listening:
            return
        self._listening = False
        # Clear any ongoing recording to avoid capturing TTS audio
        with self._lock:
            self._recording = False
            self.recorded_frames = []
            self.first_timestamp_below_threshold = None
        # Stop the stream but don't close it (allows restart)
        if self._stream is not None:
            self._stream.stop_stream()

    def stop(self):
        """Fully stop and terminate the audio system."""
        self.stop_listening()
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            try:
                self._p.terminate()
            except Exception:
                pass

    def is_listening(self):
        return self._listening

    #ToDo: You can make this faster by taking only the end of buffer
    def get_buffer_bytes(self) -> bytes:
        with self._lock:
            if not self._has_wrapped:
                return bytes(self._buffer[:self._write_pos])
            return bytes(self._buffer[self._write_pos:] + self._buffer[:self._write_pos])

    def get_last_recorded_bytes(self, seconds: float) -> bytes:
        bytes_needed = int(min(seconds * self._bytes_per_second, self._buffer_capacity_bytes))
        data = self.get_buffer_bytes()
        if len(data) <= bytes_needed:
            return data
        return data[-bytes_needed:]

    # RMS helpers
    def get_rms(self) -> float:
        data = self.get_last_recorded_bytes(seconds=0.2)
        buffer_end = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        mean_square = np.sqrt(np.dot(buffer_end, buffer_end) / buffer_end.size)
        return float(mean_square)
    
    
    

# Minimal CLI demo
if __name__ == "__main__":
    rec = SoundReceiver()
    try:
        # optionally set DEVICE_INDEX env var before running, or pass device_index to start_listening
        rec.start_listening()  # non-blocking
        input("Recording... press Enter to stop and save buffer to recent_from_buffer.wav\n")
        print("Saving last 5 seconds to recent_from_buffer.wav")

    finally:
        rec.stop()