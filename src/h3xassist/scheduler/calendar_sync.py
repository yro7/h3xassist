"""Calendar synchronization service."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from h3xassist.integrations.outlook import OutlookClient
from h3xassist.models.recording import RecordingMeta, RecordingStatus
from h3xassist.settings import settings

if TYPE_CHECKING:
    from uuid import UUID

    from h3xassist.integrations.outlook import CalendarEvent
    from h3xassist.storage.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class CalendarSyncService:
    """Synchronizes meetings from external calendars."""

    def __init__(self, store: "RecordingStore", sync_interval_minutes: int) -> None:
        self._store = store
        self._sync_interval = timedelta(minutes=sync_interval_minutes)
        self._outlook_client: OutlookClient | None = None
        self._running = False
        self._sync_task: asyncio.Task[None] | None = None

        # Track external IDs to detect duplicates
        self._external_ids: dict[str, UUID] = {}
        self._load_external_ids()

    def _load_external_ids(self) -> None:
        """Load external IDs from existing meetings."""
        for meeting_id in self._store.list_recordings():
            handle = self._store.get(meeting_id)
            meta = handle.read_meta()
            if meta is not None and meta.external_id:
                self._external_ids[meta.external_id] = meeting_id

    async def start(self) -> None:
        """Start the sync service."""
        if self._running:
            return

        self._running = True

        # Initial sync
        await self.sync_now()

        # Start periodic sync
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("Calendar sync started")

    async def stop(self) -> None:
        """Stop the sync service."""
        if not self._running:
            return

        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task

        logger.info("Calendar sync stopped")

    async def _sync_loop(self) -> None:
        """Main sync loop."""
        while self._running:
            await asyncio.sleep(self._sync_interval.total_seconds())
            if self._running:
                await self.sync_now()

    async def sync_now(self) -> None:
        """Perform calendar sync now."""
        if not self._outlook_client:
            try:
                self._outlook_client = OutlookClient()
            except Exception as e:
                logger.warning("Outlook not available: %s", e)
                return

        try:
            events = await self._outlook_client.list_upcoming()
            for event in events:
                await self._process_event(event)
        except Exception:
            logger.exception("Sync failed")

    async def _process_event(self, event: "CalendarEvent") -> None:
        """Process a calendar event."""
        # Skip without meeting URL
        if not event.online_meeting_url:
            return

        # Parse times
        start = self._parse_time(event.start)
        end = self._parse_time(event.end)

        if not start:
            return

        if not end:
            end = start + timedelta(hours=1)

        # Check if exists
        existing_id = self._external_ids.get(event.event_id)

        if existing_id:
            # Update existing
            try:
                handle = self._store.get(existing_id)
                meta = handle.read_meta()

                if meta is not None and meta.status == RecordingStatus.SCHEDULED:
                    meta.subject = event.subject or meta.subject
                    meta.url = event.online_meeting_url
                    meta.scheduled_start = start
                    meta.scheduled_end = end
                    handle.write_meta(meta)

            except FileNotFoundError:
                # Was deleted, recreate
                self._external_ids.pop(event.event_id, None)
                await self._create_meeting(event, start, end)
        else:
            # Create new
            await self._create_meeting(event, start, end)

    async def _create_meeting(self, event: "CalendarEvent", start: datetime, end: datetime) -> None:
        """Create meeting from calendar event."""
        meeting_id = uuid4()

        meta = RecordingMeta(
            id=meeting_id,
            subject=event.subject or "Untitled",
            url=event.online_meeting_url,
            scheduled_start=start,
            scheduled_end=end,
            source="outlook",
            external_id=event.event_id,
            status=RecordingStatus.SCHEDULED,
            language=settings.models.default_language,
            profile=settings.browser.default_profile_name,
            use_school_meet=False,
        )

        handle = self._store.create(meeting_id)
        handle.write_meta(meta)
        self._external_ids[event.event_id] = meeting_id

        logger.info("Created meeting: %s", event.subject)

    def _parse_time(self, time_str: str | None) -> datetime | None:
        """Parse ISO time string."""
        if not time_str:
            return None

        try:
            if time_str.endswith("Z"):
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            elif "+" in time_str or time_str.count("-") >= 3:
                return datetime.fromisoformat(time_str)
            else:
                return datetime.fromisoformat(time_str).replace(tzinfo=UTC)
        except Exception:
            return None
