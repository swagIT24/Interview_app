from typing import Optional


class VADProcessor:
    """
    Buffers incoming binary audio chunks from a WebSocket stream.
    End-of-speech is signalled externally (browser sends {"type": "end_of_speech"}).
    Call add_chunk() for each binary frame, flush() when speech ends.
    """

    def __init__(self):
        self._buffer = bytearray()

    def add_chunk(self, data: bytes) -> None:
        self._buffer.extend(data)

    def flush(self) -> Optional[bytes]:
        if not self._buffer:
            return None
        audio = bytes(self._buffer)
        self.reset()
        return audio

    def reset(self) -> None:
        self._buffer = bytearray()

    @property
    def has_audio(self) -> bool:
        return len(self._buffer) > 0
