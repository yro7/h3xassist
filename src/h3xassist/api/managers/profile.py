"""Profile management for API."""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

from h3xassist.browser.session import ExternalBrowserSession
from h3xassist.errors import ProfileExistsError, ProfileNotFoundError
from h3xassist.models.profile import ProfileConfig
from h3xassist.settings import settings

logger = logging.getLogger(__name__)


from h3xassist.browser.profiles import ProfileManager as BaseProfileManager


class ProfileManager(BaseProfileManager):
    """API-facing profile manager.
    
    Can be used to add API-specific extensions to the base ProfileManager.
    """
    pass
