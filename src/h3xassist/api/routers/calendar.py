"""Calendar API router."""

import logging

from fastapi import APIRouter, HTTPException

from h3xassist.api.dependencies import CalendarSyncDep
from h3xassist.models.api import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/sync", response_model=MessageResponse)
async def sync_calendar(sync_service: CalendarSyncDep) -> MessageResponse:
    """Trigger calendar synchronization."""
    try:
        await sync_service.sync_now()
        return MessageResponse(message="Calendar synchronization completed")
    except Exception as e:
        logger.error("Failed to sync calendar: %s", e)
        raise HTTPException(status_code=500, detail="Failed to sync calendar") from e
