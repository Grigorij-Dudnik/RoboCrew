import pyaudio
import wave
import threading
import time
import audioop
import time
from openai import OpenAI
import io
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())


class SoundReceiver:
    def __init__(self, sounddevice_index, task_queue=None, wakeword="robot"):
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 48000
        self.BUFFER_SECONDS = 2
        self.frames_per_buffer = 2048
        self.recording_loop_delay = 0.2
        # parse DEVICE_INDEX env var into an int if present, else None
        self.DEVICE_INDEX = sounddevice_index
        self.wakeword = wakeword

        self._p = pyaudio.PyAudio()
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
        while self._listening:
            loop_start_time = time.perf_counter()
            # print(f"rms: {self.get_rms()}")
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
            if self.wakeword in transcription.text.lower():
                self.task_queue.put(transcription.text)


    def start_listening(self):
        print(f"Starting SoundReceiver on device index {self.DEVICE_INDEX}")
        if self._listening:
            return
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
        self._listening = True
        self.reciver_thread.start()

    def stop(self):
        if not self._listening:
            return
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        finally:
            try:
                self._p.terminate()
            except Exception:
                pass
            self._listening = False

    def is_listening(self):
        return self._listening

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
        """Return RMS level for raw PCM bytes (paInt16 width expected)."""
        return float(audioop.rms(self.get_last_recorded_bytes(seconds=0.2), self._sample_width))
    

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