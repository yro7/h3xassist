import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from h3xassist.audio.recorder import record_audio
from h3xassist.audio.virtual import virtual_sink
from h3xassist.browser.platforms import pick_platform
from h3xassist.browser.profiles import temp_profile_from_base
from h3xassist.browser.session import ExternalBrowserSession
from h3xassist.models.recording import CaptionInterval, CaptionIntervals, RecordingStatus
from h3xassist.settings import settings

if TYPE_CHECKING:
    from h3xassist.storage.recording_handle import RecordingHandle
    from h3xassist.storage.recording_store import RecordingStore

logger = logging.getLogger(__name__)


@dataclass
class RecordingResult:
    """Result of a successful meeting recording."""

    directory: str
    bytes_written: int
    duration_sec: float | None
    end_reason: str


@dataclass
class SpeakerState:
    """Tracks current speaker and timing for caption intervals."""

    current: str | None = None
    since: float | None = None


class MeetingRecorder:
    """Orchestrates meeting join, recording, and storage.

    Combines browser automation, audio recording, and speaker tracking
    into a single coordinated workflow.
    """

    def __init__(self, handle: "RecordingHandle", storage: "RecordingStore") -> None:
        self._handle = handle
        self._storage = storage
        self._stop_event = asyncio.Event()
        self._is_cancelled = False

    def trigger_graceful_stop(self, is_cancelled: bool = False) -> None:
        """Trigger graceful stop of the recording."""
        self._stop_event.set()
        self._is_cancelled = is_cancelled
        logger.info("Graceful stop triggered for recording (cancelled: %s)", is_cancelled)

    async def _determine_duration(self) -> float | None:
        """Determine the duration of the recording from audio.ogg file using ffprobe."""

        if not self._handle.audio.exists():
            return None

        ffprobe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            self._handle.audio.as_posix(),
        ]
        result = await asyncio.create_subprocess_exec(
            *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        return float(stdout.decode("utf-8").strip()) if result.returncode == 0 else None

    async def record(self) -> bool:
        """Record the meeting.

        Returns:
            RecordingResult with output directory and metadata
        """
        handle = self._handle

        end_reason: str = "unknown"

        meta = handle.read_meta()
        if meta is None:
            raise ValueError("Recording meta not found")

        meta.status = RecordingStatus.RECORDING
        handle.write_meta(meta)

        # Record the meeting using context managers
        async with (
            virtual_sink(description="H3XAssist Meeting Sink") as sink,
            record_audio(
                f"{sink.sink_name}.monitor",
                handle.audio,
                sample_rate=settings.audio.pcm_sample_rate,
                channels=settings.audio.pcm_channels,
                bitrate=settings.audio.opus.bitrate,
                container=settings.audio.opus.container,
            ) as recording,
            temp_profile_from_base(
                profile_name=meta.profile,
                profiles_dir=Path(settings.browser.profiles_base_dir).expanduser(),
            ) as profile_dir,
        ):
            # Setup browser session
            session = ExternalBrowserSession(
                browser_bin=settings.browser.browser_bin,
                env=os.environ.copy(),
                profile_dir=profile_dir,
                automation_mode=True,
                headless=not settings.browser.browser_visible,
                pulse_sink_serial=sink.object_serial,
                stream_stderr=True,
                log_file_path=handle.browser_log,
                stability_profile=settings.browser.stability_profile,
                force_turn_tcp=settings.browser.force_turn_tcp,
                disable_telemetry=settings.browser.disable_telemetry,
            )

            async with session:
                # Create platform controller and join meeting
                controller = pick_platform(
                    session,
                    settings.general.meeting_display_name,
                    meta.url,
                    use_school_meet=meta.use_school_meet,
                )
                await controller.join()

                meta = handle.read_meta()

                meta.actual_start = datetime.now(UTC)
                handle.write_meta(meta)

                logger.info("Joined meeting: %s", meta.subject)

                # Start timing from when we successfully joined
                loop = asyncio.get_running_loop()
                t0 = loop.time()

                # Track speakers
                speaker_state = SpeakerState()
                speaker_iter = controller.iter_speakers()

                async def speaker_tracker() -> None:
                    """Track speaker changes and record intervals."""
                    caption_intervals = CaptionIntervals()
                    try:
                        async for speaker in speaker_iter:
                            now_rel = loop.time() - t0
                            prev = speaker_state.current
                            since = speaker_state.since

                            if prev is None:
                                # First speaker
                                speaker_state.current = speaker
                                speaker_state.since = now_rel
                                continue

                            if speaker != prev:
                                # Speaker changed - close previous interval
                                start = float(since or now_rel)
                                end = float(now_rel)
                                if end > start:
                                    caption_intervals.intervals.append(
                                        CaptionInterval(speaker=prev, start=start, end=end)
                                    )
                                speaker_state.current = speaker
                                speaker_state.since = now_rel
                        handle.write_caption_intervals(caption_intervals)
                    except asyncio.CancelledError:
                        # Finalize last speaker interval on cancellation
                        now_rel = loop.time() - t0
                        prev = speaker_state.current
                        since = speaker_state.since
                        if prev and since and now_rel > since:
                            caption_intervals.intervals.append(
                                CaptionInterval(
                                    speaker=prev, start=float(since), end=float(now_rel)
                                )
                            )
                        handle.write_caption_intervals(caption_intervals)
                        raise

                # Start speaker tracking
                speaker_task = asyncio.create_task(speaker_tracker())

                try:
                    # Wait for meeting end, timeout, or stop signal
                    end_tasks = [
                        asyncio.create_task(controller.wait_meeting_end()),
                        asyncio.create_task(session.wait_closed()),
                        asyncio.create_task(self._stop_event.wait()),  # Graceful stop
                    ]

                    done, _ = await asyncio.wait(end_tasks, return_when=asyncio.FIRST_COMPLETED)

                    # Determine end reason
                    if end_tasks[2] in done:  # Stop event triggered
                        end_reason = "user-stop" if not self._is_cancelled else "user-cancelled"
                        # Try to gracefully leave the meeting
                        try:
                            await controller.leave_meeting()
                            logger.info("Gracefully left meeting after user stop")
                        except Exception as e:
                            logger.warning("Failed to leave meeting gracefully: %s", e)
                    elif end_tasks[1] in done:
                        end_reason = "browser-closed"
                    elif end_tasks[0] in done:
                        end_reason = "meeting-ended"
                    else:
                        end_reason = "timeout"

                    # Allow audio to drain
                    if self._is_cancelled:
                        logger.info("Meeting cancelled, shutting down...")
                        return False
                    else:
                        logger.info("Meeting ended (%s), draining audio...", end_reason)
                        await asyncio.sleep(float(settings.recording.drain_sec))

                finally:
                    # Cancel pending tasks
                    for task in [speaker_task, *end_tasks]:
                        if not task.done():
                            task.cancel()

                    # Wait for tasks to clean up
                    for task in [speaker_task]:
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.warning("Task cleanup error: %s", e)

        logger.info(
            "Recording completed: directory=%s bytes=%d reason=%s",
            handle.directory,
            recording.bytes_written,
            end_reason,
        )

        meta = handle.read_meta()
        assert meta is not None

        meta.actual_end = datetime.now(UTC)
        meta.end_reason = end_reason
        meta.bytes_written = recording.bytes_written
        meta.duration_sec = await self._determine_duration()
        meta.status = RecordingStatus.READY
        handle.write_meta(meta)

        return not self._is_cancelled
