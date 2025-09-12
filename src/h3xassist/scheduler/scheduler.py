"""Meeting scheduler with internal queue."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from h3xassist.models.recording import RecordingStatus

if TYPE_CHECKING:
    from uuid import UUID

    from h3xassist.models.recording import RecordingMeta
    from h3xassist.storage.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class MeetingScheduler:
    """Schedules and triggers meeting recordings.

    Responsibilities:
    - Monitor scheduled meetings
    - Trigger recordings at the right time
    - Provide meeting IDs via async iterator
    """

    def __init__(
        self,
        store: "RecordingStore",
        *,
        check_interval: int = 30,
        lookahead_minutes: int = 2,
        max_queue_size: int = 100,
    ) -> None:
        """Initialize scheduler.

        Args:
            store: Recording store for meeting persistence
            check_interval: How often to check for meetings (seconds)
            lookahead_minutes: Start recording N minutes before meeting
            max_queue_size: Maximum queue size
        """
        self._store = store
        self._check_interval = check_interval
        self._lookahead = timedelta(minutes=lookahead_minutes)

        # Internal queue
        self._queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=max_queue_size)

        self._running = False
        self._scheduler_task: asyncio.Task[None] | None = None

        # Track meetings we've already queued to avoid duplicates
        self._queued_meetings: set[UUID] = set()

    def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Meeting scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        if not self._running:
            return

        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task

        logger.info("Meeting scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - checks and triggers meetings."""
        try:
            while self._running:
                await self._check_and_queue_meetings()
                await asyncio.sleep(self._check_interval)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler loop crashed")
            self._running = False

    async def _check_and_queue_meetings(self) -> None:
        """Check for meetings that need to be started."""
        now = datetime.now(UTC)

        # Load all meetings from store
        for meeting_id in self._store.list_recordings():
            # Skip if already queued
            if meeting_id in self._queued_meetings:
                continue

            try:
                handle = self._store.get(meeting_id)
                meta = handle.read_meta()

                if meta is None:
                    continue  # type: ignore[unreachable]

                # Only process scheduled meetings
                if meta.status != RecordingStatus.SCHEDULED:
                    continue

                # Check if it's time to start
                time_until_start = meta.scheduled_start - now

                # Should we trigger it?
                if time_until_start <= self._lookahead:
                    # Don't trigger if too late (>10 min past start)
                    if time_until_start < timedelta(minutes=-10):
                        # Mark as skipped
                        meta.status = RecordingStatus.SKIPPED
                        handle.write_meta(meta)
                        logger.info(
                            "Meeting %s skipped (too late): %s",
                            meeting_id,
                            meta.subject,
                        )
                        continue

                    # Queue the meeting ID
                    await self._queue_meeting(meeting_id, meta)

            except Exception:
                logger.exception("Error checking meeting %s", meeting_id)

    async def _queue_meeting(self, meeting_id: "UUID", meta: "RecordingMeta") -> None:
        """Queue a meeting for recording."""
        # Put meeting ID in queue
        await self._queue.put(meeting_id)
        self._queued_meetings.add(meeting_id)

        logger.info(
            "Queued meeting %s for recording: %s",
            meeting_id,
            meta.subject,
        )

    async def get_next_meeting(self) -> "UUID":
        """Get next meeting ID from queue (blocks until available).

        Returns:
            UUID of the next meeting to process

        Usage:
            async for meeting_id in scheduler:
                # Process meeting
        """
        meeting_id = await self._queue.get()
        self._queued_meetings.discard(meeting_id)
        return meeting_id

    def __aiter__(self) -> "MeetingScheduler":
        """Make scheduler an async iterator."""
        return self

    async def __anext__(self) -> "UUID":
        """Get next meeting from queue."""
        if not self._running:
            raise StopAsyncIteration
        return await self.get_next_meeting()

    def pending_count(self) -> int:
        """Get number of meetings pending in queue."""
        return self._queue.qsize()

    def is_queued(self, meeting_id: "UUID") -> bool:
        """Check if meeting is already queued."""
        return meeting_id in self._queued_meetings
