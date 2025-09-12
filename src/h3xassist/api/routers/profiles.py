"""Profiles API router."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from h3xassist.api.dependencies import ProfileManagerDep
from h3xassist.errors import ProfileExistsError, ProfileNotFoundError
from h3xassist.models.api import MessageResponse
from h3xassist.models.profile import ProfileConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"])


class CreateProfileRequest(BaseModel):
    name: str = Field(..., description="Profile name")


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., description="New profile name")


@router.get("", response_model=list[ProfileConfig])
async def list_profiles(manager: ProfileManagerDep) -> list[ProfileConfig]:
    """List all profiles."""
    try:
        return manager.list_profiles()
    except Exception as e:
        logger.error("Failed to list profiles: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list profiles") from e


@router.post("", response_model=ProfileConfig)
async def create_profile(
    request: CreateProfileRequest, manager: ProfileManagerDep
) -> ProfileConfig:
    """Create a new profile."""
    try:
        return manager.create_profile(request.name)
    except (ValueError, ProfileExistsError):
        raise
    except Exception as e:
        logger.error("Failed to create profile %s: %s", request.name, e)
        raise HTTPException(status_code=500, detail="Failed to create profile") from e


@router.get("/{profile_name}", response_model=ProfileConfig)
async def get_profile(profile_name: str, manager: ProfileManagerDep) -> ProfileConfig:
    """Get a specific profile."""
    try:
        return manager.get_profile(profile_name)
    except ProfileNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to get profile %s: %s", profile_name, e)
        raise HTTPException(status_code=500, detail="Failed to get profile") from e


@router.put("/{profile_name}", response_model=ProfileConfig)
async def update_profile(
    profile_name: str, request: UpdateProfileRequest, manager: ProfileManagerDep
) -> ProfileConfig:
    """Update profile (rename)."""
    try:
        return manager.update_profile(profile_name, request.name)
    except (ProfileNotFoundError, ProfileExistsError, ValueError):
        raise
    except Exception as e:
        logger.error("Failed to update profile %s: %s", profile_name, e)
        raise HTTPException(status_code=500, detail="Failed to update profile") from e


@router.delete("/{profile_name}", response_model=MessageResponse)
async def delete_profile(profile_name: str, manager: ProfileManagerDep) -> MessageResponse:
    """Delete a profile."""
    try:
        manager.delete_profile(profile_name)
        return MessageResponse(message=f"Profile '{profile_name}' deleted")
    except ProfileNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to delete profile %s: %s", profile_name, e)
        raise HTTPException(status_code=500, detail="Failed to delete profile") from e


@router.post("/{profile_name}/launch", response_model=MessageResponse)
async def launch_profile(profile_name: str, manager: ProfileManagerDep) -> MessageResponse:
    """Launch browser with specific profile."""
    try:
        await manager.launch_profile(profile_name)
        return MessageResponse(message=f"Browser launched with profile '{profile_name}'")
    except ProfileNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to launch profile %s: %s", profile_name, e)
        raise HTTPException(status_code=500, detail="Failed to launch profile") from e
