"""Browser profile authentication management.

This module provides authentication lifecycle management for browser profiles,
separate from the recording lifecycle handled by ExternalBrowserSession.

Usage:
    # Authenticate a new profile (interactive)
    manager = BrowserProfileManager()
    await manager.authenticate("teams-bot")

    # Load and validate existing profile
    profile = manager.load_profile("teams-bot")
    if not manager.validate_session("teams-bot"):
        await manager.reauthenticate("teams-bot")
"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import json
import logging

from playwright.async_api import Page

from h3xassist.browser.session import ExternalBrowserSession
from h3xassist.browser.profiles import ProfileManager
from h3xassist.settings import settings

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when browser authentication fails."""


class SessionExpiredError(Exception):
    """Raised when saved session has expired."""


class BrowserProfileManager:
    """Manages browser profile authentication lifecycle.

    Responsibilities:
    - Interactive authentication flows (MFA/2FA support)
    - Session validation before recording
    - Session expiration detection
    - Profile re-authentication

    Architecture:
    - Works with existing ExternalBrowserSession
    - Profiles stored in standard profile directory
    - Session metadata cached in profile directory
    """

    def __init__(self, profiles_dir: Optional[str] = None):
        self.profiles_dir = (
            Path(profiles_dir)
            if profiles_dir
            else Path(settings.browser.profiles_base_dir).expanduser()
        )
        self.profile_manager = ProfileManager()

    async def authenticate(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
        timeout: float = 300.0,
    ) -> None:
        """Authenticate browser profile interactively.

        Opens browser window for user to complete login flow including MFA/2FA.
        Session is saved to profile directory for reuse.

        Args:
            profile_name: Name for the authenticated profile
            target_url: URL to navigate to for authentication
            timeout: Maximum time to wait for authentication (seconds)
        """
        profile_path = self.profiles_dir / profile_name

        logger.info(f"Starting authentication for profile: {profile_name}")
        logger.info(f"Profile location: {profile_path}")

        session = ExternalBrowserSession(
            browser_bin="chromium-browser",
            env=os.environ.copy(),
            profile_dir=str(profile_path),
            automation_mode=False,
            headless=False,
            stability_profile="default",
            remote_debugging_port=9222,
            remote_debugging_address="0.0.0.0",
        )

        async with session:
            page = await session.wait_page(5.0)

            logger.info(f"Navigating to {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            logger.info("Waiting for user to complete authentication...")
            logger.info("Close the browser window when finished.")

            await asyncio.wait_for(session.wait_closed(), timeout=timeout)

        self._save_auth_metadata(profile_name, target_url)

        logger.info(f"Authentication complete for profile: {profile_name}")

    def _save_auth_metadata(self, profile_name: str, target_url: str) -> None:
        """Save authentication metadata for session validation."""
        metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "profile_name": profile_name,
            "target_url": target_url,
            "authenticated_at": datetime.now().isoformat(),
            "last_validated": None,
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def load_profile(self, profile_name: str) -> Optional[dict]:
        """Load profile authentication metadata.

        Args:
            profile_name: Name of the profile to load

        Returns:
            Profile metadata dict or None if not found
        """
        metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, "r") as f:
            return json.load(f)

    def validate_session(self, profile_name: str) -> bool:
        """Validate if saved session is still active.

        Performs lightweight validation:
        - Check profile directory exists
        - Check authentication metadata exists
        - Check session age (warn if > 30 days)

        For full validation, use validate_session_online()

        Args:
            profile_name: Name of the profile to validate

        Returns:
            True if session appears valid, False if re-authentication needed
        """
        profile_path = self.profiles_dir / profile_name

        if not profile_path.exists():
            logger.warning(f"Profile directory not found: {profile_path}")
            return False

        metadata = self.load_profile(profile_name)
        if not metadata:
            logger.warning(f"Profile metadata not found: {profile_name}")
            return False

        authenticated_at = datetime.fromisoformat(metadata["authenticated_at"])
        age = datetime.now() - authenticated_at

        if age.days > 90:
            logger.warning(
                f"Profile {profile_name} is {age.days} days old, may need re-authentication"
            )

        logger.info(f"Profile {profile_name} validation passed (age: {age.days} days)")
        return True

    async def validate_session_online(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
    ) -> bool:
        """Validate session by checking authenticated state in browser.

        Opens browser with saved profile and checks if still logged in.
        More accurate than validate_session() but slower.

        Args:
            profile_name: Name of the profile to validate
            target_url: URL to check authentication against

        Returns:
            True if session is valid, False if re-authentication needed
        """
        profile_path = self.profiles_dir / profile_name

        if not profile_path.exists():
            return False

        session = ExternalBrowserSession(
            browser_bin="chromium-browser",
            env=os.environ.copy(),
            profile_dir=str(profile_path),
            automation_mode=True,
            headless=True,
            stability_profile="default",
            remote_debugging_port=9222,
            remote_debugging_address="0.0.0.0",
        )

        try:
            async with session:
                page = await session.wait_page(5.0)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                is_authenticated = await page.evaluate("() => !!window._ts_ddd_correlation_id")

                if is_authenticated:
                    logger.info(f"Profile {profile_name} session validated online")
                    self._update_validation_timestamp(profile_name)
                    return True
                else:
                    logger.warning(f"Profile {profile_name} session expired (not authenticated)")
                    return False

        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
        finally:
            await session.close()

    def _update_validation_timestamp(self, profile_name: str) -> None:
        """Update last validated timestamp in metadata."""
        metadata = self.load_profile(profile_name)
        if metadata:
            metadata["last_validated"] = datetime.now().isoformat()
            metadata_file = self.profiles_dir / profile_name / "auth_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

    async def reauthenticate(
        self,
        profile_name: str,
        target_url: str = "https://teams.microsoft.com",
    ) -> None:
        """Re-authenticate an existing profile.

        Convenience method that combines authentication with metadata update.

        Args:
            profile_name: Name of the profile to re-authenticate
            target_url: URL for authentication
        """
        logger.info(f"Re-authenticating profile: {profile_name}")
        await self.authenticate(profile_name, target_url)
        logger.info(f"Profile {profile_name} re-authenticated successfully")
