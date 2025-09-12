import asyncio
import contextlib
import logging
import os
import shutil
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def require_ffmpeg() -> None:
    """Ensure ffmpeg binary is available in PATH.

    Raises:
        RuntimeError: if ffmpeg is not found.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found in PATH. Please install ffmpeg to enable Opus encoding."
        )


@dataclass
class AudioRecording:
    """Information about an active audio recording."""

    output_path: "Path"
    process: asyncio.subprocess.Process
    stderr_task: asyncio.Task[None]
    bytes_written: int = 0


@asynccontextmanager
async def record_audio(
    source: str,
    output_path: "Path",
    *,
    sample_rate: int,
    channels: int,
    bitrate: str,
    container: str,
) -> "AsyncIterator[AudioRecording]":
    """Record audio from PulseAudio source to file using FFmpeg.

    Args:
        source: PulseAudio source name (e.g., "sink_name.monitor")
        output_path: Output file path (format determined by extension)
        sample_rate: PCM sample rate
        channels: Number of channels
        bitrate: Opus bitrate
        container: Opus container

    Yields:
        AudioRecording with process info and output path
    """
    # Ensure ffmpeg is available before starting recording
    require_ffmpeg()

    # Build FFmpeg arguments
    ff_args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "pulse",
        "-i",
        source,
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "libopus",
        "-b:a",
        bitrate,
        "-application",
        "voip",
        "-f",
        container,
        output_path.as_posix(),
    ]

    logger.debug("starting audio recording: %s", " ".join(ff_args))

    # Start FFmpeg process
    proc = await asyncio.create_subprocess_exec(
        *ff_args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    # Pump stderr to logs
    async def _pump_stderr() -> None:
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            logger.debug("[ffmpeg] %s", line.decode(errors="ignore").rstrip())

    stderr_task = asyncio.create_task(_pump_stderr())
    recording = AudioRecording(
        output_path=output_path,
        process=proc,
        stderr_task=stderr_task,
    )

    try:
        yield recording
    finally:
        # Stop recording gracefully
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                proc.terminate()
            try:
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(proc.wait()), timeout=2.0)
            except Exception:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()

        # Stop stderr pump
        stderr_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await stderr_task

        # Get final file size
        try:
            recording.bytes_written = os.path.getsize(output_path.as_posix())
        except Exception:
            recording.bytes_written = 0

        logger.debug(
            "audio recording finished: path=%s bytes=%d",
            output_path.as_posix(),
            recording.bytes_written,
        )
