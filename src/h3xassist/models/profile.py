"""Profile models."""

from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Browser profile configuration."""

    name: str = Field(..., description="Profile name")
    path: str = Field(..., description="Profile directory path")
