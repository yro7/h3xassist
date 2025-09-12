"""Recordings API router."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from h3xassist.api.dependencies import PostprocessServiceDep, RecordingManagerDep
from h3xassist.errors import MeetingNotFoundError
from h3xassist.models.api import MessageResponse, ReprocessRequest
from h3xassist.models.recording import RecordingMeta, Transcript
from h3xassist.postprocess.summarize import MeetingSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recordings", tags=["recordings"])


class CreateRecordingRequest(BaseModel):
    subject: str = Field(..., description="Meeting subject")
    url: str = Field(..., description="Meeting URL")
    scheduled_start: datetime = Field(..., description="Meeting scheduled start time")
    scheduled_end: datetime = Field(..., description="Meeting scheduled end time")
    language: str | None = Field(None, description="Meeting language")
    profile: str = Field("default", description="Browser profile")
    use_school_meet: bool = Field(False, description="Use school Google Meet mode")


class UpdateRecordingRequest(BaseModel):
    subject: str | None = Field(None, description="Meeting subject")
    language: str | None = Field(None, description="Meeting language")
    profile: str | None = Field(None, description="Browser profile")
    use_school_meet: bool | None = Field(None, description="Use school Google Meet mode")


@router.get("", response_model=list[RecordingMeta])
async def list_recordings(manager: RecordingManagerDep) -> list[RecordingMeta]:
    """List all recordings."""
    try:
        recording_ids = manager._store.list_recordings()
        recordings = []

        for recording_id in recording_ids:
            try:
                handle = manager._store.get(recording_id)
                meta = handle.read_meta()
                if meta:
                    recordings.append(meta)
            except Exception as e:
                logger.warning("Failed to load recording %s: %s", recording_id, e)
                continue

        return sorted(recordings, key=lambda x: x.scheduled_start, reverse=True)
    except Exception as e:
        logger.error("Failed to list recordings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list recordings") from e


@router.post("", response_model=RecordingMeta)
async def create_recording(
    request: CreateRecordingRequest, manager: RecordingManagerDep
) -> RecordingMeta:
    """Create a new manual recording."""
    try:
        recording_id = manager.create_manual_recording(
            subject=request.subject,
            url=request.url,
            scheduled_start=request.scheduled_start,
            scheduled_end=request.scheduled_end,
            language=request.language,
            profile=request.profile,
            use_school_meet=request.use_school_meet,
        )

        # Get created recording
        handle = manager._store.get(recording_id)
        meta = handle.read_meta()
        if not meta:
            raise HTTPException(status_code=500, detail="Failed to create recording")

        return meta
    except Exception as e:
        logger.error("Failed to create recording: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create recording") from e


@router.get("/{recording_id}", response_model=RecordingMeta)
async def get_recording(recording_id: UUID, manager: RecordingManagerDep) -> RecordingMeta:
    """Get a specific recording."""
    try:
        handle = manager._store.get(recording_id)
        meta = handle.read_meta()
        if not meta:
            raise MeetingNotFoundError(recording_id) from None

        return meta
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to get recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to get recording") from e


@router.put("/{recording_id}", response_model=RecordingMeta)
async def update_recording(
    recording_id: UUID, request: UpdateRecordingRequest, manager: RecordingManagerDep
) -> RecordingMeta:
    """Update recording metadata."""
    try:
        # Build updates dict
        updates: dict[str, Any] = {}
        if request.subject is not None:
            updates["subject"] = request.subject
        if request.language is not None:
            updates["language"] = request.language
        if request.profile is not None:
            updates["profile"] = request.profile
        if request.use_school_meet is not None:
            updates["use_school_meet"] = request.use_school_meet

        manager.update_recording_meta(recording_id, updates)

        # Return updated recording
        handle = manager._store.get(recording_id)
        meta = handle.read_meta()
        if not meta:
            raise MeetingNotFoundError(recording_id) from None

        return meta
    except MeetingNotFoundError:
        raise
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to update recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to update recording") from e


@router.delete("/{recording_id}")
async def delete_recording(recording_id: UUID, manager: RecordingManagerDep) -> MessageResponse:
    """Cancel and delete recording."""
    try:
        await manager.cancel_meeting(recording_id)
        return MessageResponse(message="Recording cancelled and deleted")
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to delete recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete recording") from e


@router.post("/{recording_id}/start")
async def start_recording(recording_id: UUID, manager: RecordingManagerDep) -> MessageResponse:
    """Start recording."""
    try:
        await manager.start_meeting(recording_id)
        return MessageResponse(message="Recording started")
    except MeetingNotFoundError:
        raise
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to start recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to start recording") from e


@router.post("/{recording_id}/stop")
async def stop_recording(recording_id: UUID, manager: RecordingManagerDep) -> MessageResponse:
    """Stop recording gracefully."""
    try:
        await manager.end_meeting(recording_id)
        return MessageResponse(message="Recording stopped")
    except MeetingNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to stop recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to stop recording") from e


@router.get("/{recording_id}/audio")
async def get_recording_audio(recording_id: UUID, manager: RecordingManagerDep) -> FileResponse:
    """Download recording audio file."""
    try:
        handle = manager._store.get(recording_id)
        if not handle.audio.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        return FileResponse(
            path=handle.audio, filename=f"recording_{recording_id}.ogg", media_type="audio/ogg"
        )
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to get recording audio %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to get recording audio") from e


@router.get("/{recording_id}/transcript")
async def get_recording_transcript(
    recording_id: UUID, manager: RecordingManagerDep
) -> "Transcript":
    """Get recording transcript."""
    try:
        handle = manager._store.get(recording_id)
        transcript = handle.read_transcript()

        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        return transcript
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to get recording transcript %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to get recording transcript") from e


@router.get("/{recording_id}/summary")
async def get_recording_summary(
    recording_id: UUID, manager: RecordingManagerDep
) -> "MeetingSummary":
    """Get recording summary."""
    try:
        handle = manager._store.get(recording_id)
        summary = handle.read_summary()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        return summary
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to get recording summary %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to get recording summary") from e


@router.post("/{recording_id}/postprocess")
async def postprocess_recording(
    recording_id: UUID, manager: RecordingManagerDep, postprocess_service: PostprocessServiceDep
) -> MessageResponse:
    """Add recording to postprocess queue."""
    try:
        # Check if recording exists
        handle = manager._store.get(recording_id)
        meta = handle.read_meta()
        if not meta:
            raise MeetingNotFoundError(recording_id) from None

        # Enqueue for postprocessing
        postprocess_service.enqueue(recording_id)

        return MessageResponse(message="Recording added to postprocess queue")
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to enqueue recording %s for postprocessing: %s", recording_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to enqueue recording for postprocessing"
        ) from e


@router.post("/{recording_id}/reprocess")
async def reprocess_recording(
    recording_id: UUID, request: ReprocessRequest, manager: RecordingManagerDep
) -> MessageResponse:
    """Reprocess recording with new language settings."""
    try:
        manager.reprocess_recording(recording_id, request.language)
        return MessageResponse(message=f"Reprocessing started with language: {request.language}")
    except MeetingNotFoundError:
        raise
    except ValueError as e:
        # Status check failed
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError:
        raise MeetingNotFoundError(recording_id) from None
    except Exception as e:
        logger.error("Failed to reprocess recording %s: %s", recording_id, e)
        raise HTTPException(status_code=500, detail="Failed to reprocess recording") from e
