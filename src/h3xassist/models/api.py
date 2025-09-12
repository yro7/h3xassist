"""API-specific models."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    detail: Any = Field(None, description="Additional error details")


class MessageResponse(BaseModel):
    """Standard message response."""

    message: str = Field(..., description="Response message")


class RefreshSignal(BaseModel):
    """WebSocket refresh signal."""


class ReprocessRequest(BaseModel):
    """Request to reprocess a recording with different language settings."""

    language: str = Field(
        ..., description="Language code for transcription (e.g., 'en', 'uk', 'es')"
    )
