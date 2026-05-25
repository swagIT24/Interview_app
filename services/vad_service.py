import io
import wave
from math import gcd
from typing import Optional

import numpy as np
import torch
from scipy.signal import resample_poly

TARGET_SR = 16000
VAD_CHUNK = 512  # 32ms at 16kHz — required by silero

_model_cache = None


def _load_model():
    global _model_cache
    if _model_cache is None:
        from silero_vad import load_silero_vad
        _model_cache = load_silero_vad()
    return _model_cache


class VADProcessor:
    def __init__(self):
        from silero_vad import VADIterator
        model = _load_model()
        # Each connection gets its own VADIterator (owns the LSTM state)
        self._vad = VADIterator(
            model,
            threshold=0.5,
            sampling_rate=TARGET_SR,
            min_silence_duration_ms=1500,
            speech_pad_ms=300,
        )
        self._src_sr: int = 0
        self._up: int = 1
        self._down: int = 1
        self._pcm_16k: list = []
        self._partial: list = []

    def set_sample_rate(self, sr: int) -> None:
        if sr == self._src_sr:
            return
        self._src_sr = sr
        if sr != TARGET_SR:
            g = gcd(TARGET_SR, sr)
            self._up = TARGET_SR // g
            self._down = sr // g

    def add_bytes(self, data: bytes) -> bool:
        """
        Feed raw signed 16-bit LE PCM mono bytes at self._src_sr.
        Returns True when end-of-speech is detected.
        """
        n = len(data) // 2
        if n == 0:
            return False

        pcm = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0

        if self._src_sr and self._src_sr != TARGET_SR:
            pcm = resample_poly(pcm, self._up, self._down)

        self._pcm_16k.extend(pcm.tolist())
        self._partial.extend(pcm.tolist())

        while len(self._partial) >= VAD_CHUNK:
            chunk = torch.FloatTensor(self._partial[:VAD_CHUNK])
            self._partial = self._partial[VAD_CHUNK:]
            result = self._vad(chunk)
            if result and "end" in result:
                return True

        return False

    def flush(self) -> Optional[bytes]:
        """Return WAV bytes (16kHz mono 16-bit) of accumulated audio, or None."""
        if not self._pcm_16k:
            return None
        arr = np.array(self._pcm_16k, dtype=np.float32).clip(-1.0, 1.0)
        pcm16 = (arr * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_SR)
            wf.writeframes(pcm16.tobytes())
        self.reset()
        return buf.getvalue()

    def reset(self) -> None:
        self._vad.reset_states()
        self._pcm_16k.clear()
        self._partial.clear()

    @property
    def has_audio(self) -> bool:
        return bool(self._pcm_16k)
