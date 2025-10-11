import pyaudio
import wave
import threading
import time
import os
import sys
import audioop

class SoundReceiver:
    """
    Record from an input device into a RAM circular buffer.
    - buffer_seconds: size of circular buffer in seconds
    - chunk, format, channels, rate configure the stream
    Methods:
      start_listening(device_index=None)  # non-blocking, fills/overwrites circular buffer
      stop()
      is_listening() -> bool
      get_buffer_bytes() -> bytes  # oldest..newest content currently in buffer
      get_last(seconds) -> bytes
      save_to_wav(path)  # writes current buffer contents to WAV
    """
    def __init__(self, buffer_seconds=15, chunk=2048,
                 fmt=pyaudio.paInt16, channels=1, rate=48000):
        self.CHUNK = chunk
        self.FORMAT = fmt
        self.CHANNELS = channels
        self.RATE = rate
        self.BUFFER_SECONDS = buffer_seconds
        # parse DEVICE_INDEX env var into an int if present, else None
        env_idx = os.getenv("DEVICE_INDEX")
        if env_idx is not None:
            try:
                self.DEVICE_INDEX = int(env_idx)
            except (ValueError, TypeError):
                print(f"Warning: DEVICE_INDEX='{env_idx}' is not a valid integer; ignoring.")
                self.DEVICE_INDEX = None
        else:
            self.DEVICE_INDEX = None

        self._p = pyaudio.PyAudio()
        self._sample_width = self._p.get_sample_size(self.FORMAT)
        self._bytes_per_second = int(self.RATE * self.CHANNELS * self._sample_width)
        self._capacity = int(self._bytes_per_second * self.BUFFER_SECONDS)

        self._buffer = bytearray(self._capacity)
        self._write_pos = 0
        self._has_wrapped = False
        self._lock = threading.Lock()

        self._stream = None
        self._listening = False

    def _write_to_buffer(self, data: bytes):
        with self._lock:
            n = len(data)
            if n == 0:
                return
            end_space = self._capacity - self._write_pos
            if n <= end_space:
                self._buffer[self._write_pos:self._write_pos + n] = data
                self._write_pos += n
                if self._write_pos == self._capacity:
                    self._write_pos = 0
                    self._has_wrapped = True
            else:
                self._buffer[self._write_pos:] = data[:end_space]
                rest = n - end_space
                self._buffer[0:rest] = data[end_space:]
                self._write_pos = rest
                self._has_wrapped = True

    def _callback(self, in_data, frame_count, time_info, status):
        if in_data:
            self._write_to_buffer(in_data)
        return (None, pyaudio.paContinue)


    def start_listening(self, device_index=None, frames_per_buffer=None):
        if self._listening:
            return
        try:
            self._stream = self._p.open(format=self.FORMAT,
                                       channels=self.CHANNELS,
                                       rate=self.RATE,
                                       input=True,
                                       input_device_index=self.DEVICE_INDEX,
                                       frames_per_buffer=frames_per_buffer,
                                       stream_callback=self._callback)
        except Exception as e:
            raise RuntimeError(f"Failed to open input stream: {e}")
        self._stream.start_stream()
        self._listening = True

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

    def get_last(self, seconds: float) -> bytes:
        if seconds <= 0:
            return b''
        bytes_needed = int(min(seconds * self._bytes_per_second, self._capacity))
        data = self.get_buffer_bytes()
        if len(data) <= bytes_needed:
            return data
        return data[-bytes_needed:]

    def save_to_wav(self, path: str):
        data = self.get_buffer_bytes()
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self.RATE)
            wf.writeframes(data)

    # RMS helpers
    def get_rms(self, data: bytes) -> float:
        """Return RMS level for raw PCM bytes (paInt16 width expected)."""
        return float(audioop.rms(self.get_last(0.1), self._sample_width))


# Minimal CLI demo
if __name__ == "__main__":
    rec = SoundReceiver(buffer_seconds=15, chunk=2048, channels=1, rate=48000)
    try:
        # optionally set DEVICE_INDEX env var before running, or pass device_index to start_listening
        rec.start_listening()  # non-blocking
        print("Listening for 10 seconds (buffering in RAM)...")
        time.sleep(10)
        print("Saving last 5 seconds to recent_from_buffer.wav")
        recent = rec.get_last(5.0)
        with wave.open("recent_from_buffer.wav", "wb") as wf:
            wf.setnchannels(rec.CHANNELS)
            wf.setsampwidth(rec._sample_width)
            wf.setframerate(rec.RATE)
            wf.writeframes(recent)
    finally:
        rec.stop()