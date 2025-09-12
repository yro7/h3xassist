"""Settings API router."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from h3xassist.models.api import MessageResponse
from h3xassist.settings import AppSettings, save_settings, settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/schema")
async def get_settings_schema() -> dict[str, Any]:
    """Get JSON schema for settings."""
    try:
        schema = settings.model_json_schema()

        # Add UI metadata for frontend
        schema["ui_metadata"] = {
            "sections": [
                {
                    "key": "general",
                    "title": "General",
                    "icon": "Settings",
                    "description": "Basic application identity and display naming",
                },
                {
                    "key": "models",
                    "title": "Models",
                    "icon": "Brain",
                    "description": "Speech model selection and cache configuration",
                },
                {
                    "key": "browser",
                    "title": "Browser",
                    "icon": "Globe",
                    "description": "Browser profiles configuration and automation settings",
                },
                {
                    "key": "audio",
                    "title": "Audio",
                    "icon": "Volume2",
                    "description": "Audio pipeline parameters and encoding settings",
                },
                {
                    "key": "paths",
                    "title": "Storage",
                    "icon": "FolderOpen",
                    "description": "Filesystem paths for meetings and data storage",
                },
                {
                    "key": "postprocess",
                    "title": "Processing",
                    "icon": "Cpu",
                    "description": "Post-processing service options and concurrency",
                },
                {
                    "key": "recording",
                    "title": "Recording",
                    "icon": "Mic",
                    "description": "Recording metrics and behavior settings",
                },
                {
                    "key": "integrations",
                    "title": "Integrations",
                    "icon": "Link",
                    "description": "External integrations configuration (Outlook, Calendar)",
                },
                {
                    "key": "speaker",
                    "title": "Speaker Assignment",
                    "icon": "Users",
                    "description": "Speaker assignment algorithm parameters",
                },
                {
                    "key": "summarization",
                    "title": "Summarization",
                    "icon": "FileText",
                    "description": "LLM-based summarization settings and limits",
                },
                {
                    "key": "export",
                    "title": "Export",
                    "icon": "Upload",
                    "description": "Export settings for summaries and integrations",
                },
            ]
        }

        return schema
    except Exception as e:
        logger.error("Failed to get settings schema: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get settings schema") from e


@router.get("", response_model=AppSettings)
async def get_settings() -> AppSettings:
    """Get current settings."""
    try:
        return AppSettings()  # spin up a fresh instance with settings from file
    except Exception as e:
        logger.error("Failed to get settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get settings") from e


@router.put("", response_model=MessageResponse)
async def update_settings(new_settings: AppSettings) -> MessageResponse:
    """Update settings and save to file."""
    try:
        # Save settings to file
        save_settings(new_settings)

        return MessageResponse(message="Settings updated successfully")
    except Exception as e:
        logger.error("Failed to update settings: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update settings") from e
