from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class CaptionInterval(BaseModel):
    speaker: str
    start: float
    end: float


class TranscriptSegment(CaptionInterval):
    text: str | None = None
    speaker_confidence: float | None = None


class Transcript(BaseModel):
    segments: list[TranscriptSegment] = Field(default_factory=list)


class CaptionIntervals(BaseModel):
    intervals: list[CaptionInterval] = Field(default_factory=list)


class RecordingStatus(StrEnum):
    SCHEDULED = "scheduled"
    RECORDING = "recording"
    PROCESSING = "processing"
    READY = "ready"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class RecordingMeta(BaseModel):
    """Unified recording metadata - combines Event + Recording data."""

    # Unique identifier
    id: UUID = Field(..., description="Recording ID")

    # Meeting metadata
    subject: str = Field(..., description="Meeting subject")
    url: str = Field(..., description="Meeting URL")
    scheduled_start: datetime = Field(..., description="Meeting scheduled start time")
    scheduled_end: datetime = Field(..., description="Meeting scheduled end time")
    source: str = Field("manual", description="Meeting source")
    external_id: str | None = Field(None, description="Meeting external ID")

    # Recording metadata
    actual_start: datetime | None = Field(None, description="Meeting actual start time")
    actual_end: datetime | None = Field(None, description="Meeting actual end time")
    duration_sec: float | None = Field(None, description="Meeting duration")
    bytes_written: int | None = Field(None, description="Meeting bytes written")
    end_reason: str | None = Field(None, description="Meeting end reason")
    postprocess_stage: str | None = Field(None, description="Postprocess stage")

    # Status (unified)
    status: RecordingStatus = Field(RecordingStatus.SCHEDULED, description="Meeting status")

    # Configuration
    language: str | None = Field(None, description="Meeting language")
    profile: str = Field("default", description="Meeting profile")
    use_school_meet: bool = Field(False, description="Use school Google Meet mode")

    error_message: str | None = Field(None, description="Meeting error message")
