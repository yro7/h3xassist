"""Recording and processing manager for API."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from h3xassist.errors import MeetingNotFoundError
from h3xassist.meeting_recorder import MeetingRecorder
from h3xassist.models.recording import RecordingMeta, RecordingStatus
from h3xassist.settings import settings

if TYPE_CHECKING:
    from uuid import UUID

    from h3xassist.api.managers.websocket import ConnectionManager
    from h3xassist.postprocess.service import PostprocessService
    from h3xassist.scheduler.scheduler import MeetingScheduler
    from h3xassist.storage.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class RecordingManager:
    """Manages active recordings and their lifecycle."""

    def __init__(
        self,
        store: "RecordingStore",
        connection_manager: "ConnectionManager",
        scheduler: "MeetingScheduler",
        postprocess_service: "PostprocessService",
    ) -> None:
        self._store = store
        self._connection_manager = connection_manager
        self._scheduler = scheduler
        self._postprocess_service = postprocess_service

        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._run_tasks: set[asyncio.Task[None]] = set()
        self._recorders: dict[UUID, MeetingRecorder] = {}

    def _determine_language(self, meeting_language: str | None) -> str | None:
        """Determine language for ASR transcription based on priority:
        1. Meeting-specific language (highest priority)
        2. Global default language from settings
        3. None for auto-detection (lowest priority)
        """
        # Priority 1: Meeting-specific language
        if meeting_language is not None:
            return meeting_language

        # Priority 2: Global default language
        if settings.models.default_language is not None:
            return settings.models.default_language

        # Priority 3: Auto-detection
        return None

    async def _run(self) -> None:
        """Run the recording manager."""
        self._stop.clear()
        logger.info("Recording manager started")

        try:
            while not self._stop.is_set():
                # Create tasks for waiting on stop signal and next meeting
                stop_task = asyncio.create_task(self._stop.wait(), name="stop_wait")
                meeting_task = asyncio.create_task(
                    self._scheduler.get_next_meeting(), name="get_next_meeting"
                )

                try:
                    # Wait for first completed task
                    done, pending = await asyncio.wait(
                        [stop_task, meeting_task], return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel any pending tasks to avoid resource leaks
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                    # Check if stop was requested
                    if stop_task in done:
                        logger.info("Stop signal received, exiting recording manager loop")
                        break

                    # Handle meeting task completion
                    if meeting_task in done:
                        try:
                            meeting_result = meeting_task.result()
                            logger.info("Running meeting: %s", meeting_result)
                            task = asyncio.create_task(self._run_meeting(meeting_result))
                            self._run_tasks.add(task)  # type: ignore[arg-type]  # false positive
                            task.add_done_callback(self._run_tasks.discard)  # type: ignore[arg-type]  # false positive
                        except Exception as e:
                            logger.error("Error processing meeting task result: %s", e)

                except Exception as e:
                    logger.error("Error in recording manager loop: %s", e)
                    # Continue the loop despite errors
                    continue

        except Exception as e:
            logger.error("Fatal error in recording manager: %s", e)
            raise
        finally:
            logger.info("Recording manager stopped")

    async def _run_meeting(self, meeting_id: "UUID") -> None:
        """Run a meeting with proper status management."""
        logger.info("Running meeting: %s", meeting_id)
        handle = self._store.get(meeting_id)

        try:
            recorder = MeetingRecorder(handle, self._store)
            self._recorders[meeting_id] = recorder
            should_continue = await recorder.record()

            # Start post-processing
            if should_continue:
                logger.info("Enqueuing post-processing for meeting: %s", meeting_id)
                self._postprocess_service.enqueue(meeting_id)
            else:
                logger.info("Meeting cancelled: %s", meeting_id)
        except Exception as e:
            logger.error("Meeting recording failed for %s: %s", meeting_id, e)
            meta = handle.read_meta()
            if meta is not None:
                meta.status = RecordingStatus.ERROR
                meta.error_message = str(e)
                handle.write_meta(meta)
            raise
        finally:
            self._recorders.pop(meeting_id, None)

    def start(self) -> None:
        """Start the recording manager."""
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the recording manager."""
        self._stop.set()
        if self._task:
            with contextlib.suppress(Exception):
                await self._task

    async def start_meeting(self, meeting_id: "UUID") -> None:
        """Start a meeting."""
        try:
            handle = self._store.get(meeting_id)
        except FileNotFoundError:
            raise MeetingNotFoundError(meeting_id) from None
        meta = handle.read_meta()
        if meta is None:
            raise MeetingNotFoundError(meeting_id) from None
        meta.scheduled_start = datetime.now(UTC)
        handle.write_meta(meta)

    async def end_meeting(self, meeting_id: "UUID") -> None:
        """End a meeting."""
        recorder = self._recorders.get(meeting_id)
        if recorder is None:
            raise MeetingNotFoundError(meeting_id) from None
        recorder.trigger_graceful_stop(is_cancelled=False)

    async def cancel_meeting(self, meeting_id: "UUID") -> None:
        """Cancel a meeting."""
        recorder = self._recorders.get(meeting_id)
        if recorder is None:
            self._store.delete(meeting_id)
            return
        recorder.trigger_graceful_stop(is_cancelled=True)
        await asyncio.sleep(1)  # Give time for the recording to be cancelled
        self._store.delete(meeting_id)

    def create_manual_recording(
        self,
        subject: str,
        url: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        language: str | None = None,
        profile: str = "default",
        use_school_meet: bool = False,
    ) -> "UUID":
        """Create a manual recording."""
        recording_id = uuid4()

        meta = RecordingMeta(
            id=recording_id,
            subject=subject,
            url=url,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            source="manual",
            status=RecordingStatus.SCHEDULED,
            language=self._determine_language(language),
            profile=profile,
            use_school_meet=use_school_meet,
        )

        handle = self._store.create(recording_id)
        handle.write_meta(meta)

        logger.info("Created manual recording: %s (%s)", subject, recording_id)
        return recording_id

    def update_recording_meta(self, meeting_id: "UUID", updates: dict[str, Any]) -> None:
        """Update recording metadata."""
        try:
            handle = self._store.get(meeting_id)
        except FileNotFoundError:
            raise MeetingNotFoundError(meeting_id) from None

        meta = handle.read_meta()
        if meta is None:
            raise MeetingNotFoundError(meeting_id) from None

        # Update allowed fields
        for field, value in updates.items():
            if hasattr(meta, field):
                setattr(meta, field, value)

        handle.write_meta(meta)
        logger.info("Updated recording metadata: %s", meeting_id)

    def reprocess_recording(self, meeting_id: "UUID", language: str) -> None:
        """Reprocess recording with new language settings.

        This method:
        1. Updates recording language
        2. Clears existing processing results
        3. Resets status to READY
        4. Enqueues for reprocessing
        """
        try:
            handle = self._store.get(meeting_id)
        except FileNotFoundError:
            raise MeetingNotFoundError(meeting_id) from None

        meta = handle.read_meta()
        if meta is None:
            raise MeetingNotFoundError(meeting_id) from None

        # Only allow reprocessing of completed or errored recordings
        if meta.status not in [RecordingStatus.COMPLETED, RecordingStatus.ERROR]:
            raise ValueError(f"Cannot reprocess recording in status: {meta.status}")

        # Update language
        meta.language = language

        # Reset status to READY for reprocessing
        meta.status = RecordingStatus.READY
        meta.error_message = None
        meta.postprocess_stage = None

        # Save updated metadata
        handle.write_meta(meta)

        # Clear existing results
        handle.clear_results()

        # Enqueue for reprocessing
        self._postprocess_service.enqueue(meeting_id)

        logger.info("Reprocessing recording %s with language: %s", meeting_id, language)
