import asyncio
import contextlib
import logging
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self, TextIO

from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from playwright.async_api import Browser as PWBrowser
    from playwright.async_api import BrowserContext, Page, Playwright

_CDP_RE = re.compile(r"DevTools listening on (ws://.*)")

logger = logging.getLogger(__name__)


class ExternalBrowserSession:
    """Launch external chromium-browser with CDP and control via Playwright.

    We do not rely on Playwright's bundled browsers to avoid extra installs.
    """

    def __init__(
        self,
        *,
        browser_bin: str = "chromium-browser",
        env: dict[str, str] | None = None,
        profile_dir: str,
        automation_mode: bool = True,
        headless: bool | None = None,
        app_url: str | None = None,
        stream_stderr: bool = False,
        pulse_sink_serial: str | None = None,
        log_file_path: Path | str | None = None,
        stability_profile: Literal["default", "software_safe", "gpu_balanced"] = "default",
        force_turn_tcp: bool = False,
        disable_telemetry: bool = True,
    ) -> None:
        self._browser_bin = browser_bin
        self._env = env if env is not None else os.environ.copy()
        self._profile_dir = profile_dir
        self._automation_mode = automation_mode
        self._headless = headless if headless is not None else automation_mode
        self._app_url = (
            app_url if app_url is not None else ("about:blank" if automation_mode else None)
        )
        self._proc: asyncio.subprocess.Process | None = None
        self._playwright: Playwright | None = None
        self._pw_browser: PWBrowser | None = None
        self._pw_context: BrowserContext | None = None
        self._default_page: Page | None = None
        self.cdp_url: str | None = None
        self._stream_stderr = stream_stderr
        self._stderr_task: asyncio.Task[None] | None = None
        # Audio routing via PipeWire Pulse compatibility (set by caller)
        self._pulse_sink_serial = pulse_sink_serial
        # Browser log file path
        self._log_file_path = Path(log_file_path) if log_file_path else None
        self._log_file: TextIO | None = None
        # Stability settings
        self._stability_profile = stability_profile
        self._force_turn_tcp = force_turn_tcp
        self._disable_telemetry = disable_telemetry

    async def __aenter__(self) -> Self:
        return await self.open()

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    # Public explicit lifecycle methods
    async def open(self) -> Self:
        self._playwright = await async_playwright().start()

        if not shutil.which(self._browser_bin):
            raise RuntimeError(f"Browser binary not found: {self._browser_bin}")

        user_data_dir = self._profile_dir
        os.makedirs(user_data_dir, exist_ok=True)

        args: list[str] = self._build_chromium_args(user_data_dir)

        logger.debug(
            "Launching external browser: bin=%s args=%s env(XDG_SESSION_TYPE=%s, WAYLAND_DISPLAY=%s, XDG_CURRENT_DESKTOP=%s)",
            self._browser_bin,
            " ".join(args[1:]),
            os.environ.get("XDG_SESSION_TYPE"),
            os.environ.get("WAYLAND_DISPLAY"),
            os.environ.get("XDG_CURRENT_DESKTOP"),
        )

        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=self._prepare_env(),
        )

        while True:
            assert self._proc.stderr is not None
            line = await self._proc.stderr.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            logger.debug("[chromium] %s", text)
            # Write initial logs to file if specified
            if self._log_file is not None:
                from datetime import UTC, datetime

                timestamp = datetime.now(UTC).isoformat()
                self._log_file.write(f"[{timestamp}] {text}\n")
                self._log_file.flush()
            m = _CDP_RE.search(text)
            if m:
                self.cdp_url = m.group(1)
                break

        if not self.cdp_url:
            raise RuntimeError("Could not find DevTools URL from browser stderr")

        self._pw_browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
        self._pw_context = self._pw_browser.contexts[0]
        self._default_page = self._pw_context.pages[0] if self._pw_context.pages else None
        logger.debug("connected to CDP: %s", self.cdp_url)
        logger.debug(
            "Playwright connected: contexts=%s pages=%s default_page=%s",
            len(self._pw_browser.contexts) if self._pw_browser else 0,
            len(self._pw_context.pages) if self._pw_context else 0,
            bool(self._default_page),
        )
        # Open log file if specified
        if self._log_file_path:
            self._log_file_path.parent.mkdir(parents=True, exist_ok=True)
            # Open file in append mode for writing
            self._log_file = open(self._log_file_path, "a", encoding="utf-8")  # noqa: SIM115
            # Write session start marker
            from datetime import UTC, datetime

            timestamp = datetime.now(UTC).isoformat()
            self._log_file.write(f"[{timestamp}] ===== Browser session started =====\n")
            self._log_file.write(f"[{timestamp}] Binary: {self._browser_bin}\n")
            self._log_file.write(f"[{timestamp}] Args: {' '.join(args[1:])}\n")
            self._log_file.write(
                f"[{timestamp}] Mode: {'automation' if self._automation_mode else 'user'}\n"
            )
            self._log_file.write(f"[{timestamp}] Stability profile: {self._stability_profile}\n")
            self._log_file.flush()

        if self._stream_stderr and self._proc and self._proc.stderr is not None:
            self._stderr_task = asyncio.create_task(self._pump_stderr(logger))
        return self

    async def close(self) -> None:
        if self._playwright:
            await self._playwright.stop()
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                # Shield wait from outer cancellations to avoid bubbling CancelledError
                await asyncio.wait_for(asyncio.shield(self._proc.wait()), timeout=1)
            except TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            with contextlib.suppress(Exception):
                await self._stderr_task
        if self._log_file is not None:
            from datetime import UTC, datetime

            timestamp = datetime.now(UTC).isoformat()
            self._log_file.write(f"[{timestamp}] ===== Browser session ended =====\n")
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None
        self._proc = None
        self._playwright = None
        self._pw_browser = None
        self._pw_context = None
        self._default_page = None
        self.cdp_url = None

    async def new_page(self) -> "Page":
        if not self._pw_context:
            raise RuntimeError("Playwright context not ready")
        return await self._pw_context.new_page()

    def get_default_page(self) -> "Page | None":
        return self._default_page

    async def wait_closed(self) -> None:
        if self._proc is not None:
            await self._proc.wait()

    async def wait_page(self, timeout: float = 5.0) -> "Page":
        """Wait until a page is available; create one if needed.

        Args:
            timeout: seconds to wait.

        Returns:
            Page: the available or newly created page.

        Raises:
            RuntimeError: if context/page did not become ready in time.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if self._pw_context:
                if self._pw_context.pages:
                    return self._pw_context.pages[0]
                try:
                    return await self._pw_context.new_page()
                except Exception:
                    pass
            await asyncio.sleep(0.1)
        raise RuntimeError("Playwright context/page not ready")

    async def _pump_stderr(self, logger: logging.Logger) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        while True:
            line = await self._proc.stderr.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            # Avoid duplicating the CDP line which we already logged; harmless if repeated
            logger.debug("[chromium] %s", text)
            # Write to log file if specified
            if self._log_file is not None:
                from datetime import UTC, datetime

                timestamp = datetime.now(UTC).isoformat()
                self._log_file.write(f"[{timestamp}] {text}\n")
                self._log_file.flush()

    def _build_chromium_args(self, user_data_dir: str) -> list[str]:
        """Build Chromium arguments with automation modes and stability profiles."""
        args: list[str] = [
            self._browser_bin,
            "--remote-debugging-port=0",
            f"--user-data-dir={user_data_dir}",
            # Automation essentials - always needed
            "--no-first-run",
            "--no-default-browser-check",
            "--no-service-autorun",
            "--test-type",
            # Always X11 per project policy
            "--ozone-platform=x11",
        ]

        # Automation mode vs User configuration mode
        if self._automation_mode:
            # Bot/automation specific flags
            args.extend(
                [
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                ]
            )
            if self._app_url:
                args.append(f"--app={self._app_url}")
        else:
            # User configuration mode
            args.append("--new-window")

        # Headless mode
        if self._headless:
            args.append("--headless=new")

        # Stability core - applied for enhanced profiles
        if self._stability_profile != "default":
            args.extend(
                [
                    "--disable-extensions",
                    "--disable-component-update",
                    "--disable-sync",
                    "--no-proxy-server",
                    "--password-store=basic",
                    "--use-mock-keychain",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                    "--autoplay-policy=no-user-gesture-required",
                ]
            )

        # GPU/Video stability profiles
        if self._stability_profile == "software_safe":
            args.extend(
                [
                    "--disable-gpu",
                    "--use-gl=swiftshader",
                    "--disable-features=VaapiVideoDecoder,AcceleratedVideoDecode",
                ]
            )
        elif self._stability_profile == "gpu_balanced":
            args.extend(
                [
                    "--use-gl=angle",
                    "--disable-features=VaapiVideoDecoder,AcceleratedVideoDecode",
                ]
            )

        # Network/WebRTC settings
        if self._force_turn_tcp:
            args.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")

        # Telemetry reduction
        if self._disable_telemetry:
            args.extend(
                [
                    "--metrics-recording-only",
                    "--disable-domain-reliability",
                ]
            )

        return args

    def _prepare_env(self) -> dict[str, str]:
        env = self._env.copy()
        if self._pulse_sink_serial:
            env["PULSE_SINK"] = self._pulse_sink_serial
        return env
