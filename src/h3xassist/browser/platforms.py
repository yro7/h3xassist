import asyncio
import contextlib
import logging
import re
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from playwright.async_api import Frame, Locator, Page

    from h3xassist.browser.session import ExternalBrowserSession


TEAMS_JS_OBSERVER = r"""(panelSel) => {
  const panel = document.querySelector(panelSel);
  if (!panel) return false;
  const getRow = function(el){
    const txt = (el.innerText || '').trim();
    const parts = txt.split('\n').map(function(s){return s.trim();}).filter(function(s){return s.length>0});
    if (parts.length >= 2 && parts[0].length >= 2 && parts[0].length <= 60) {
      return { speaker: parts[0], text: parts.slice(1).join(' ') };
    }
    if (txt.indexOf(':') !== -1) {
      var idx = txt.indexOf(':');
      var name = txt.substring(0, idx).trim();
      var body = txt.substring(idx+1).trim();
      if (name.length <= 60 && body.length > 0) return { speaker: name, text: body };
    }
    return null;
  };
  var last = '';
  var emit = function(row){
    var key = row.speaker + '|' + row.text;
    if (key === last) return;
    last = key;
    if (row.speaker && window.h3x_push_caption) { try { window.h3x_push_caption(row.speaker); } catch(e){} }
  };
  var obs = new MutationObserver(function(list){
    for (var i=0;i<list.length;i++){
      var m = list[i];
      var nodes = [];
      for (var j=0;j<m.addedNodes.length;j++){ var n = m.addedNodes[j]; if (n && n.nodeType===1) nodes.push(n); }
      if (m.type === 'characterData' && m.target && m.target.parentElement) nodes.push(m.target.parentElement);
      for (var k=0;k<nodes.length;k++){
        var cur = nodes[k];
        var steps = 0;
        while (cur && cur !== panel && steps++ < 4){
          var r = getRow(cur);
          if (r){ emit(r); break; }
          cur = cur.parentElement;
        }
      }
    }
  });
  obs.observe(panel, { subtree: true, childList: true, characterData: true });
  window.__h3xCaptionsObserver = obs;
  return true;
}"""


class PlatformController(Protocol):
    url_pattern: re.Pattern[str]

    def __init__(self, session: "ExternalBrowserSession", name: str, url: str) -> None:
        """Initialize controller with browser session, display name, and meeting URL."""

    async def join(self) -> None:
        """Navigate to URL and complete pre-join flow (mute name/camera, click Join)."""

    def iter_speakers(self) -> "AsyncGenerator[str, None]":
        """Yield current speaker names as they appear (platform-specific implementation)."""

    async def wait_meeting_end(self) -> None:
        """Block until meeting ends (platform-specific criterion).

        For Teams: wait until the Leave button disappears.
        """

    async def leave_meeting(self) -> None:
        """Attempt a graceful leave from the meeting UI (click "Leave")."""


logger = logging.getLogger(__name__)


class MeetController:
    url_pattern = re.compile(r"^(?:https?://)?(?:www\.)?meet\.google\.com/")

    def __init__(self, session: "ExternalBrowserSession", name: str, url: str) -> None:
        self._session = session
        self._name = name
        self._url = url
        self._page: Page | None = None

    async def join(self) -> None:
        self._page = self._session.get_default_page() or await self._session.wait_page(5.0)
        await self._page.goto(self._url, wait_until="load", timeout=30000)
        # Pre-join: mute mic and cam
        try:
            await self._page.keyboard.press("Ctrl+D")  # toggle mic
            await self._page.keyboard.press("Ctrl+E")  # toggle cam
        except Exception as e:
            logger.warning("Meet pre-join: toggling mic/cam failed: %s", e, exc_info=True)
        name_field = self._page.get_by_placeholder(re.compile("name", re.IGNORECASE))
        try:
            await name_field.fill(self._name, timeout=10000)
        except Exception as e:
            logger.warning("Meet pre-join: filling name failed: %s", e, exc_info=True)
        join_btn = self._page.get_by_role("button", name=re.compile(r"join", re.IGNORECASE))
        await join_btn.click(timeout=1000)

    async def iter_speakers(self) -> "AsyncGenerator[str, None]":
        """Meet does not yet support speaker extraction via captions."""
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        while False:
            yield ""  # type: ignore[unreachable]

    async def wait_meeting_end(self) -> None:
        # No implementation for Meet yet; just wait for page close
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        await self._page.wait_for_event("close")

    async def leave_meeting(self) -> None:
        # No-op for now
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        return


class SchoolMeetController:
    """Google Meet controller for school/organization accounts that require 'Join anyway' button."""

    url_pattern = re.compile(r"^(?:https?://)?(?:www\.)?meet\.google\.com/")

    def __init__(self, session: "ExternalBrowserSession", name: str, url: str) -> None:
        self._session = session
        self._name = name
        self._url = url
        self._page: Page | None = None

    async def join(self) -> None:
        self._page = self._session.get_default_page() or await self._session.wait_page(5.0)
        await self._page.goto(self._url, wait_until="load", timeout=30000)
        await self._page.wait_for_load_state("domcontentloaded")

        # Give time for all elements to load
        with contextlib.suppress(Exception):
            await self._page.wait_for_timeout(1000)

        logger.info("SchoolMeet pre-join: page loaded, looking for join options")

        # 1) First disable mic and camera (BEFORE joining)
        try:
            # Ctrl+D - toggle microphone (disable)
            await self._page.keyboard.press("Control+D")
            await self._page.wait_for_timeout(300)
            # Ctrl+E - toggle camera (disable)
            await self._page.keyboard.press("Control+E")
            await self._page.wait_for_timeout(300)
            logger.info("SchoolMeet: disabled mic and camera via keyboard shortcuts")
        except Exception as e:
            logger.warning("SchoolMeet: keyboard shortcuts failed: %s", e, exc_info=True)

        # 2) Click "Other ways to join" to open menu
        try:
            other_ways_btn = self._page.locator('[jsname="ix0Hvc"]').first
            if await other_ways_btn.count() > 0:
                await other_ways_btn.wait_for(state="visible", timeout=10000)
                await other_ways_btn.click(timeout=2000)
                logger.info("SchoolMeet: clicked 'Other ways to join' button")
                await self._page.wait_for_timeout(1000)
            else:
                logger.info("SchoolMeet: 'Other ways to join' button not found")
        except Exception as e:
            logger.warning("SchoolMeet: failed to click 'Other ways to join': %s", e, exc_info=True)

        # 3) Now click "Join anyway" button
        try:
            # Look for button by jsname or text
            join_anyway = self._page.locator('[jsname="Qx7uuf"]').first
            if await join_anyway.count() == 0:
                # If not found by jsname, search by text
                join_anyway = self._page.locator('button:has-text("Приєднатися також")').first
                if await join_anyway.count() == 0:
                    join_anyway = self._page.locator('button:has-text("Join anyway")').first

            if await join_anyway.count() > 0:
                await join_anyway.wait_for(state="visible", timeout=10000)
                await join_anyway.click(timeout=2000)
                logger.info("SchoolMeet: clicked 'Join anyway' button")
                # Wait for page to reload
                await self._page.wait_for_load_state("domcontentloaded")
                await self._page.wait_for_timeout(2000)
            else:
                logger.info("SchoolMeet: 'Join anyway' button not found, continuing")
        except Exception as e:
            logger.warning("SchoolMeet: failed to click 'Join anyway': %s", e, exc_info=True)

        # 4) Confirm join - wait for meeting elements to appear
        logger.info("SchoolMeet: waiting for meeting to start")
        try:
            # Use verified selectors from analysis
            await self._page.wait_for_selector(
                '[jsname="CQylAd"], [aria-label*="Завершити дзвінок" i], [aria-label*="Leave call" i], [aria-label*="End call" i]',
                state="attached",
                timeout=30000,
            )
            logger.info("SchoolMeet: successfully joined the meeting")
        except Exception as e:
            logger.warning("SchoolMeet: could not confirm join: %s", e)

        logger.info("SchoolMeet: setup complete - audio recording only, no speaker detection")

    async def iter_speakers(self) -> "AsyncGenerator[str, None]":
        """No speaker detection for SchoolMeetController - audio recording only."""
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        logger.info("SchoolMeet: speaker detection disabled - audio only mode")

        # Return empty generator - no speaker detection
        return
        yield  # type: ignore[unreachable]

    async def wait_meeting_end(self) -> None:
        """Wait for the meeting to end or user to leave."""
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        try:
            # Wait for leave button to disappear (means we left)
            await self._page.wait_for_selector(
                '[jsname="CQylAd"], [aria-label*="Завершити дзвінок" i], [aria-label*="Leave call" i], [aria-label*="End call" i]',
                state="detached",
                timeout=0,  # no timeout
            )
        except Exception:
            # Page closed or navigation - assume meeting ended
            return

    async def leave_meeting(self) -> None:
        """Click the leave button to exit the meeting."""
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        try:
            # Use verified selector jsname="CQylAd" for leave button
            leave_btn = self._page.locator('[jsname="CQylAd"]').first
            if await leave_btn.count() == 0:
                # Fallback via aria-label
                leave_btn = self._page.locator(
                    '[aria-label*="Завершити дзвінок" i], [aria-label*="Leave call" i], [aria-label*="End call" i]'
                ).first

            if await leave_btn.count() > 0:
                await leave_btn.click(timeout=2000)
                logger.info("SchoolMeet: clicked leave button")
        except Exception as e:
            logger.warning("SchoolMeet: failed to leave meeting: %s", e)


class TeamsController:
    url_pattern = re.compile(
        r"^(?:https?://)?(?:[a-z0-9-]+\.)?(?:teams\.microsoft\.com|teams\.live\.com)/"
    )

    def __init__(self, session: "ExternalBrowserSession", name: str, url: str) -> None:
        self._session = session
        self._name = name
        self._url = url
        self._page: Page | None = None

    async def join(self) -> None:
        self._page = self._session.get_default_page() or await self._session.wait_page(5.0)
        await self._page.goto(self._url, wait_until="load", timeout=30000)
        await self._page.wait_for_load_state("domcontentloaded")
        # give SPA time to stabilize before searching elements
        with contextlib.suppress(Exception):
            await self._page.wait_for_timeout(500)
        logger.info("Teams pre-join: page loaded, frames=%s", len(self._page.frames))

        # Helper: search locator in all frames with waiting
        async def wait_locator_across_frames(
            selector: str,
            *,
            use_text: bool = False,
            timeout_ms: int = 20000,
        ) -> "tuple[Page | Frame | None, Locator | None]":
            if self._page is None:
                raise RuntimeError("Controller hasn't been initialized - join() not called")

            loop = asyncio.get_running_loop()
            start = loop.time()
            timeout_s = timeout_ms / 1000
            while loop.time() - start < timeout_s:
                try:
                    loc = (
                        self._page.get_by_text(selector, exact=True)
                        if use_text
                        else self._page.locator(selector)
                    )
                    if await loc.count():
                        return self._page, loc.first
                except Exception:
                    # possible navigation/repaint — try again
                    pass
                for frame in self._page.frames:
                    try:
                        floc = (
                            frame.get_by_text(selector, exact=True)
                            if use_text
                            else frame.locator(selector)
                        )
                        if await floc.count():
                            return frame, floc.first
                    except Exception:
                        # this frame might have reloaded — ignore and continue
                        continue
                await asyncio.sleep(0.3)
            return None, None

        # (no-audio click removed by request)

        # 2) Disable camera (switch data-tid="toggle-video")
        try:
            frame, loc = await wait_locator_across_frames(
                'input[role="switch"][data-tid="toggle-video"]', timeout_ms=15000
            )
            if loc is not None:
                checked = await loc.is_checked()
                logger.debug("Teams pre-join: camera switch found (checked=%s)", checked)
                if checked:
                    await loc.click(timeout=1000)
                    logger.info("Teams pre-join: camera toggled off")
            else:
                logger.debug("Teams pre-join: camera switch not found; continuing")
        except Exception as e:
            logger.warning("Teams pre-join: camera toggle failed: %s", e, exc_info=True)

        # 2.1) Disable microphone (switch data-tid="toggle-mute")
        try:
            frame, mic = await wait_locator_across_frames(
                'input[role="switch"][data-tid="toggle-mute"]', timeout_ms=15000
            )
            if mic is not None:
                title = (await mic.get_attribute("title")) or ""
                logger.debug("Teams pre-join: mic switch found (title=%r)", title)
                # If tooltip says "Mute mic" — currently enabled, need to disable
                # If "Unmute mic" — already disabled
                if "mute mic" in title.lower() and "unmute" not in title.lower():
                    await mic.click(timeout=1000)
                    logger.info("Teams pre-join: mic toggled off")
            else:
                logger.debug("Teams pre-join: mic switch not found; continuing")
        except Exception as e:
            logger.warning("Teams pre-join: mic toggle failed: %s", e, exc_info=True)

        # 3) Enter name
        try:
            # search for placeholder 'Type your name'
            found_frame, name_loc = await wait_locator_across_frames(
                'input[placeholder*="Type your name"]', timeout_ms=20000
            )
            if name_loc is None:
                found_frame, name_loc = await wait_locator_across_frames(
                    'input[placeholder*="name"]', timeout_ms=5000
                )
            if name_loc is not None:
                await name_loc.fill(self._name, timeout=5000)
                frame_id = getattr(found_frame, "url", None)
                logger.debug("Teams pre-join: filled name in frame=%s", frame_id or "root")
            else:
                logger.debug("Teams pre-join: name field not found; continuing")
        except Exception as e:
            logger.warning("Teams pre-join: filling name failed: %s", e, exc_info=True)

        # 4) Click Join now
        try:
            # wait for button up to 20s in all frames
            frame, btn = await wait_locator_across_frames("#prejoin-join-button", timeout_ms=20000)
            if btn is None:
                frame, btn = await wait_locator_across_frames(
                    'button:has-text("Join now")', timeout_ms=5000
                )
            if btn is not None:
                await btn.click(timeout=2000)
                frame_id = getattr(frame, "url", None)
                logger.debug("Teams pre-join: clicked Join in frame=%s", frame_id or "root")
            else:
                logger.debug("Teams pre-join: join button not found; leaving pre-join as-is")
        except Exception as e:
            logger.warning("Teams pre-join: clicking Join failed: %s", e, exc_info=True)

        # Confirm in-meeting: wait for Leave button on root page (stable per your DOM)
        logger.debug("Teams pre-join: waiting for join confirmation")
        try:
            await self._page.wait_for_selector(
                '#hangup-button, button[title="Leave"], [role="button"][aria-label="Leave"], button[aria-label*="Leave" i]',
                state="attached",
                timeout=600000,
            )
            logger.info("Teams: Leave button detected — join confirmed")
        except Exception as e:
            logger.warning("Teams join not confirmed within timeout: %s", e)

        # Enable Captions via More → Captions (robust with retries)
        try:
            logger.debug("Teams: opening More menu")
            more_loc = self._page.locator(
                '#callingButtons-showMoreBtn, button[aria-label="More"], [role="button"][aria-label="More"]'
            ).first
            await more_loc.wait_for(state="visible", timeout=7000)
            for attempt in range(3):
                try:
                    await more_loc.click(timeout=2000)
                    break
                except Exception:
                    await self._page.wait_for_timeout(200 + attempt * 200)

            logger.debug("Teams: clicking Captions")
            captions_loc = self._page.locator(
                '#closed-captions-button, [role="menuitem"][aria-label="Captions"], [role="menuitem"]:has-text("Captions")'
            ).first
            await captions_loc.wait_for(state="visible", timeout=7000)
            clicked = False
            for attempt in range(3):
                try:
                    await captions_loc.click(timeout=2000)
                    clicked = True
                    break
                except Exception:
                    await self._page.wait_for_timeout(250 + attempt * 150)
            if not clicked:
                # Last resort: force click in case of minor instability/overlay
                with contextlib.suppress(Exception):
                    await captions_loc.click(timeout=2000, force=True)

            # Wait for captions panel to appear
            await self._page.wait_for_selector(
                '[aria-label="Live Captions"]', state="attached", timeout=5000
            )
            logger.debug("Teams: Captions enabled")
        except Exception as e:
            logger.warning("Teams: failed to enable Captions via More menu: %s", e, exc_info=True)

    async def iter_speakers(self) -> "AsyncGenerator[str, None]":
        """Yield speaker names from Teams Live Captions (async iterator).

        Implements a lightweight MutationObserver injected into the page and
        streams distinct speaker names via an asyncio.Queue.
        """
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=128)

        async def _push(speaker: str) -> None:
            try:
                await queue.put(str(speaker))
            except Exception:
                logger.exception("failed to enqueue caption speaker")

        # JS observer injected into page

        await self._page.expose_function("h3x_push_caption", _push)
        ok = await self._page.evaluate(TEAMS_JS_OBSERVER, "[aria-label='Live Captions']")
        if not ok:
            logger.warning("Live Captions panel not found; speakers iterator will be silent")

        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            with contextlib.suppress(Exception):
                await self._page.evaluate(
                    "() => { try { window.__h3xCaptionsObserver && window.__h3xCaptionsObserver.disconnect(); } catch(e){} }"
                )

    async def wait_meeting_end(self) -> None:
        # Wait until Leave button disappears; if the page closes earlier, this raises and should be handled by caller
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        try:
            await self._page.wait_for_selector(
                '#hangup-button, button[title="Leave"], [role="button"][aria-label="Leave"], button[aria-label*="Leave" i]',
                state="detached",
                timeout=0,  # no timeout; we will await indefinitely until detached
            )
        except Exception:
            # If page closed or frame navigated away, consider as ended
            return

    async def leave_meeting(self) -> None:
        # Try click Leave; ignore any failures
        if self._page is None:
            raise RuntimeError("Controller hasn't been initialized - join() not called")
        selectors = '#hangup-button, button[title="Leave"], [role="button"][aria-label="Leave"], button[aria-label*="Leave" i]'
        with contextlib.suppress(Exception):
            btn = await self._page.wait_for_selector(selectors, state="visible", timeout=2000)
            if btn is None:
                raise RuntimeError("Leave button not found")
            await btn.click(timeout=1000)


PLATFORMS: list[type[PlatformController]] = [MeetController, SchoolMeetController, TeamsController]


def pick_platform(
    session: "ExternalBrowserSession", name: str, url: str, use_school_meet: bool = False
) -> PlatformController:
    """Pick and initialize appropriate platform controller based on URL.

    Args:
        session: Browser session for page management
        name: Display name for the meeting
        url: Meeting URL to navigate to
        use_school_meet: If True and URL is Google Meet, use SchoolMeetController
                        for school/organization accounts
    """

    # Special handling for Google Meet
    if MeetController.url_pattern.search(url):
        if use_school_meet:
            return SchoolMeetController(session, name, url)
        return MeetController(session, name, url)

    # Check other platforms
    for cls in [TeamsController]:
        if cls.url_pattern.search(url):
            return cls(session, name, url)

    raise RuntimeError(f"Unsupported meeting URL: {url}")
