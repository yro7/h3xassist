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


class ProfileManager:
    """Manages browser profiles directory and operations."""

    def __init__(self) -> None:
        self._profiles_dir = Path(settings.browser.profiles_base_dir).expanduser()
        self._running_sessions: dict[str, asyncio.Task[None]] = {}

    def _validate_profile_name(self, name: str) -> None:
        """Validate profile name for security and filesystem compatibility."""
        if not name or not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(
                "Profile name must contain only letters, numbers, underscores and hyphens"
            )
        if len(name) > 50:
            raise ValueError("Profile name too long (max 50 characters)")

    def get_profiles_dir(self) -> Path:
        """Get the profiles base directory."""
        return self._profiles_dir

    def get_profile_path(self, profile_name: str) -> Path:
        """Get path to a specific profile."""
        return self._profiles_dir / profile_name

    def profile_exists(self, profile_name: str) -> bool:
        """Check if a profile exists."""
        return self.get_profile_path(profile_name).exists()

    def list_profiles(self) -> list[ProfileConfig]:
        """List all available profiles."""
        if not self._profiles_dir.exists():
            return []

        profiles = []
        for p in self._profiles_dir.iterdir():
            if p.is_dir():
                profiles.append(ProfileConfig(name=p.name, path=str(p)))

        return sorted(profiles, key=lambda x: x.name)

    def get_profile(self, profile_name: str) -> ProfileConfig:
        """Get a specific profile."""
        if not self.profile_exists(profile_name):
            raise ProfileNotFoundError(profile_name)

        profile_path = self.get_profile_path(profile_name)
        return ProfileConfig(name=profile_name, path=str(profile_path))

    def create_profile(self, profile_name: str) -> ProfileConfig:
        """Create a new profile."""
        self._validate_profile_name(profile_name)
        profile_path = self.get_profile_path(profile_name)

        if profile_path.exists():
            raise ProfileExistsError(profile_name)

        profile_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created profile: %s", profile_name)

        return ProfileConfig(name=profile_name, path=str(profile_path))

    def update_profile(self, profile_name: str, new_name: str) -> ProfileConfig:
        """Update profile (rename)."""
        self._validate_profile_name(new_name)

        if not self.profile_exists(profile_name):
            raise ProfileNotFoundError(profile_name)

        old_path = self.get_profile_path(profile_name)
        new_path = self.get_profile_path(new_name)

        if new_path.exists():
            raise ProfileExistsError(new_name)

        old_path.rename(new_path)
        logger.info("Renamed profile: %s -> %s", profile_name, new_name)

        return ProfileConfig(name=new_name, path=str(new_path))

    def delete_profile(self, profile_name: str) -> None:
        """Delete a profile."""
        if not self.profile_exists(profile_name):
            raise ProfileNotFoundError(profile_name)

        profile_path = self.get_profile_path(profile_name)
        shutil.rmtree(profile_path)
        logger.info("Deleted profile: %s", profile_name)

    async def launch_profile(self, profile_name: str) -> None:
        """Launch browser with specific profile."""
        if not self.profile_exists(profile_name):
            raise ProfileNotFoundError(profile_name)

        # Close previous session if exists
        if profile_name in self._running_sessions:
            self._running_sessions[profile_name].cancel()
            logger.info("Cancelled previous session for profile: %s", profile_name)

        profile_path = str(self.get_profile_path(profile_name))

        session = ExternalBrowserSession(
            browser_bin=settings.browser.browser_bin,
            env=os.environ.copy(),
            profile_dir=profile_path,
            automation_mode=False,
        )

        # Start session but don't wait - let it run independently
        async def launch_and_run() -> None:
            try:
                async with session:
                    await session.wait_closed()
            except Exception as e:
                logger.error("Browser session error for profile %s: %s", profile_name, e)
            finally:
                # Remove from tracking after completion
                self._running_sessions.pop(profile_name, None)

        # Track the task for proper cleanup
        task = asyncio.create_task(launch_and_run())
        self._running_sessions[profile_name] = task
        logger.info("Launched browser with profile: %s", profile_name)
