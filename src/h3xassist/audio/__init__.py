# Audio pipeline components
from .recorder import record_audio, require_ffmpeg
from .virtual import CreatedSink, virtual_sink

__all__ = [
    "CreatedSink",
    "record_audio",
    "require_ffmpeg",
    "virtual_sink",
]
