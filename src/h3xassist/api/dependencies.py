"""FastAPI dependency providers."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends

from h3xassist.api.managers.profile import ProfileManager
from h3xassist.api.managers.recording import RecordingManager
from h3xassist.api.managers.websocket import ConnectionManager
from h3xassist.postprocess.factory import create_postprocess_service
from h3xassist.postprocess.service import PostprocessService
from h3xassist.scheduler.calendar_sync import CalendarSyncService
from h3xassist.scheduler.scheduler import MeetingScheduler
from h3xassist.settings import settings
from h3xassist.storage.recording_store import RecordingStore

connection_manager = ConnectionManager()
store = RecordingStore(
    (Path(settings.paths.base_dir) / "recordings").expanduser(),
    on_update=lambda _: connection_manager.send_refresh_signal_sync(),
)
calendar_sync = CalendarSyncService(store, settings.integrations.calendar_sync_interval_minutes)
scheduler = MeetingScheduler(store)
postprocess_service = create_postprocess_service(store)

recording_manager = RecordingManager(store, connection_manager, scheduler, postprocess_service)
profile_manager = ProfileManager()


async def get_calendar_sync() -> CalendarSyncService:
    return calendar_sync


async def get_scheduler() -> MeetingScheduler:
    return scheduler


async def get_connection_manager() -> ConnectionManager:
    return connection_manager


async def get_recording_manager() -> RecordingManager:
    return recording_manager


async def get_postprocess_service() -> PostprocessService:
    return postprocess_service


async def get_profile_manager() -> ProfileManager:
    return profile_manager


CalendarSyncDep = Annotated[CalendarSyncService, Depends(get_calendar_sync)]
SchedulerDep = Annotated[MeetingScheduler, Depends(get_scheduler)]
ConnectionManagerDep = Annotated[ConnectionManager, Depends(get_connection_manager)]
RecordingManagerDep = Annotated[RecordingManager, Depends(get_recording_manager)]
PostprocessServiceDep = Annotated[PostprocessService, Depends(get_postprocess_service)]
ProfileManagerDep = Annotated[ProfileManager, Depends(get_profile_manager)]
