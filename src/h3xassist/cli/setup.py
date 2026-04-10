import asyncio
import contextlib
import logging
import os
import shutil
import time
import warnings
from datetime import datetime
from pathlib import Path

import typer
from O365 import Account
from O365.utils.token import FileSystemTokenBackend
from rich.panel import Panel

from h3xassist.browser.session import ExternalBrowserSession
from h3xassist.settings import settings
from h3xassist.ui import console

logger = logging.getLogger(__name__)

app = typer.Typer(help="Setup and configuration commands", no_args_is_help=True)


# Browser configuration
async def open_browser_for_profile(browser: str, profile: str, profiles_dir: str) -> None:
    base = (
        Path(profiles_dir).expanduser()
        if profiles_dir
        else Path(settings.browser.profiles_base_dir).expanduser()
    )
    name = profile or settings.browser.default_profile_name
    profile_path = base / name
    profile_dir = str(profile_path)
    session = ExternalBrowserSession(
        browser_bin=browser,
        env=os.environ.copy(),
        profile_dir=profile_dir,
        automation_mode=False,
    )
    async with session:
        await session.wait_closed()


@app.command("browser")
def browser_configure(
    browser: str = typer.Option("chromium-browser", help="Browser binary"),
    profile: str = typer.Option(default=settings.browser.default_profile_name, help="Profile name"),
    profiles_dir: str = typer.Option(
        default=settings.browser.profiles_base_dir, help="Profiles base directory"
    ),
) -> None:
    """Configure browser profiles."""
    asyncio.run(open_browser_for_profile(browser, profile, profiles_dir))


# Outlook authentication
async def _authorize() -> int:
    try:
        if settings.integrations.outlook is None:
            console.print("[error]Outlook settings are missing. Run 'h3xassist configure' first.")
            return 2
        token_file_path = Path(settings.integrations.outlook.token_cache_path).expanduser()
        token_path = str(token_file_path.parent)
        token_name = token_file_path.name
        backend = FileSystemTokenBackend(token_path=token_path, token_filename=token_name)
        account = Account(
            credentials=settings.integrations.outlook.client_id,
            tenant_id=settings.integrations.outlook.tenant_id,
            token_backend=backend,
            auth_flow_type="public",
        )
        console.print(Panel("Starting Outlook device authorization...", style="cyan", expand=False))

        ok = await asyncio.to_thread(
            account.authenticate, requested_scopes=["offline_access", "Calendars.Read"]
        )
        if not ok:
            console.print("[error]Authorization failed[/error]")
            return 2
        with contextlib.suppress(Exception):
            os.chmod(str(token_file_path), 0o600)
        console.print("[ok]Authorization succeeded.[/ok]")
        return 0
    except Exception as e:
        msg = str(e)
        if "AADSTS7000218" in msg or "invalid_client" in msg:
            console.print(
                Panel(
                    "[error]Authorization failed (invalid_client)[/error]\n\n"
                    "Tips:\n"
                    "- Ensure the Azure App is configured as a Public client/native app.\n"
                    "- Enable the 'Allow public client flows' setting in Azure AD.\n"
                    "- Use correct Tenant and Client IDs.",
                    style="red",
                    expand=False,
                )
            )
        else:
            console.print(f"[error]Authorization failed[/error]: {msg}")
        return 2


@app.command("outlook")
def outlook_login() -> None:
    """Microsoft Outlook/Graph authentication."""
    code = asyncio.run(_authorize())
    raise SystemExit(code)


# Models management
async def download_models(
    model_dir: str | None,
    lang: list[str],
    hf_token: str | None,
    compute_type: str,
    device: str | None,
) -> None:
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        torch = None  # type: ignore[assignment]
        cuda_available = False
    device = device or ("cuda" if cuda_available else "cpu")
    s = settings
    cache_dir = (
        os.path.expanduser(model_dir) if model_dir else os.path.expanduser(s.models.cache_dir)
    )
    hf_token = hf_token or s.models.hf_token

    logger.info("Preparing models")
    logger.info("  Model           : %s (fixed)", s.models.whisperx_model_name)
    logger.info("  Device          : %s (cuda_available=%s)", device, cuda_available)
    logger.info("  Cache directory : %s", cache_dir)
    logger.info("  Languages (align): %s", ", ".join(lang))
    logger.info("  Compute type    : %s", compute_type)
    logger.info("  HF token present: %s", bool(hf_token))

    # Ensure cache dir exists and is writable
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        logger.error("Cache directory is not writable: %s (%s)", cache_dir, e)
        raise

    # Reduce noisy FFmpeg extension logs from torio
    with contextlib.suppress(Exception):
        logging.getLogger("torio._extension.utils").setLevel(logging.ERROR)

    def _work() -> None:
        # ASR model
        try:
            logger.info(
                "Downloading ASR model '%s' (compute=%s)",
                s.models.whisperx_model_name,
                compute_type,
            )
            repo = f"Systran/faster-whisper-{s.models.whisperx_model_name}"
            if repo is not None:
                last_err: Exception | None = None
                for attempt in range(1, 3 + 1):
                    try:
                        logger.info("Fetching %s (attempt %s/%s)", repo, attempt, 3)
                        import whisperx

                        _ = whisperx.load_model(
                            s.models.whisperx_model_name,
                            device,
                            compute_type=compute_type,
                            download_root=cache_dir,
                        )
                        logger.info("ASR snapshot ready")
                        last_err = None
                        break
                    except Exception as e:
                        last_err = e
                        logger.warning(
                            "ASR snapshot failed (attempt %s): %s", attempt, str(e).split("\n")[0]
                        )
                        time.sleep(1.5 * attempt)
                if last_err is not None:
                    raise last_err
        except Exception as e:
            logger.error("ASR model download failed: %s", e, exc_info=True)
            raise

        # Alignment (requires language)
        align_langs = lang or ["en"]
        for align_lang in align_langs:
            try:
                logger.info("Downloading alignment model (language=%s)", align_lang)
                import whisperx

                _align, _meta = whisperx.load_align_model(language_code=align_lang, device=device)
                logger.info("Alignment model ready (language=%s)", align_lang)
            except Exception as e:
                logger.error(
                    "Alignment model download failed (language=%s): %s",
                    align_lang,
                    e,
                    exc_info=True,
                )
                raise

        # Diarization pipeline (needs HF token)
        try:
            logger.info("Preparing diarization pipeline")
            from whisperx.diarize import DiarizationPipeline

            _dia = DiarizationPipeline(device=device, use_auth_token=hf_token)
            logger.info("Diarization pipeline ready")
        except Exception as e:
            logger.error("Diarization pipeline init failed: %s", e, exc_info=True)
            raise

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            await asyncio.to_thread(_work)
    except Exception as e:
        logger.error("Model download failed: %s", e, exc_info=True)
        return
    logger.info("Model download completed")


@app.command("models")
def models_download(
    model_dir: str | None = typer.Option(
        None, help="Local cache directory for models (defaults to settings)"
    ),
    lang: list[str] = typer.Option(["en"], help="Languages for alignment model (repeat --lang)"),  # noqa: B008
    hf_token: str | None = typer.Option(
        None, help="HuggingFace token for diarization (overrides config if provided)"
    ),
    compute_type: str = typer.Option("float16", help="Compute type for ASR model"),
    device: str | None = typer.Option(None, help="Device override: cuda|cpu (default: auto)"),
) -> None:
    """Download and manage AI models."""
    asyncio.run(download_models(model_dir, lang, hf_token, compute_type, device))


@app.command("browser-auth")
def browser_authentication(
    profile: str = typer.Option(
        default="teams-bot", help="Profile name for authenticated browser session"
    ),
    target_url: str = typer.Option(
        default="https://teams.microsoft.com", help="URL to authenticate against"
    ),
    profiles_dir: str = typer.Option(
        default=settings.browser.profiles_base_dir, help="Profiles base directory"
    ),
) -> None:
    """Authenticate browser profile for automated meetings.

    This opens a browser window where you can log into your account
    and complete any MFA/2FA flows. The authenticated session is saved
    to the specified profile for reuse in automated recordings.
    """
    from h3xassist.browser.auth import BrowserProfileManager, AuthenticationError

    console.print(
        Panel(
            "[cyan]Browser Profile Authentication[/cyan]\n\n"
            "This will open a browser window.\n"
            "1. Log into your account\n"
            f"2. Navigate to {target_url}\n"
            "3. Complete any MFA/2FA challenges\n"
            "4. Close the browser when done\n\n"
            "The authenticated session will be saved for automated meetings.",
            style="cyan",
            expand=False,
        )
    )

    manager = BrowserProfileManager(profiles_dir=profiles_dir)

    async def auth_flow():
        await manager.authenticate(profile, target_url)

    try:
        asyncio.run(auth_flow())

        console.print(
            Panel(
                "[ok]Authentication complete![/ok]\n\n"
                f"Profile saved to: {Path(profiles_dir).expanduser() / profile}\n\n"
                "Next steps:\n"
                "1. In web interface, select this profile when creating recordings\n"
                "2. Bot will use authenticated session to join meetings\n"
                "3. Session persists across container restarts",
                style="green",
                expand=False,
            )
        )
    except AuthenticationError as e:
        console.print(
            Panel(
                f"[error]Authentication failed: {e}[/error]\n\n"
                "Please try again. Ensure you have a stable internet connection.",
                style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)


@app.command("browser-auth-docker")
def browser_authentication_docker(
    profile: str = typer.Option(
        default="teams-bot", help="Profile name for authenticated browser session"
    ),
    target_url: str = typer.Option(
        default="https://teams.microsoft.com", help="URL to authenticate against"
    ),
) -> None:
    """Authenticate browser profile inside Docker container with X11 forwarding.

    Requires Docker container to have X11 forwarding enabled.
    Run with: docker exec -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ...
    """
    display = os.environ.get("DISPLAY")
    if not display:
        console.print(
            Panel(
                "[error]DISPLAY environment variable not set[/error]\n\n"
                "Run this command with X11 forwarding:\n"
                "docker exec -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix <container> h3xassist browser-auth-docker",
                style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)

    if not os.path.exists("/tmp/.X11-unix"):
        console.print("[warning]X11 socket not found, but continuing...[/warning]")

    browser = "chromium-browser" if shutil.which("chromium-browser") else "chromium"

    browser_authentication(
        profile=profile, target_url=target_url, profiles_dir=settings.browser.profiles_base_dir
    )


@app.command("validate-profile")
def validate_profile(
    profile: str = typer.Option(default="teams-bot", help="Profile name to validate"),
    online: bool = typer.Option(default=False, help="Perform online validation (opens browser)"),
    profiles_dir: str = typer.Option(
        default=settings.browser.profiles_base_dir, help="Profiles base directory"
    ),
) -> None:
    """Validate browser profile session.

    Checks if saved authentication session is still valid.
    Use --online flag for accurate validation (opens browser).
    """
    from h3xassist.browser.auth import BrowserProfileManager

    manager = BrowserProfileManager(profiles_dir=profiles_dir)

    if online:
        console.print(f"[info]Validating profile '{profile}' online...[/info]")

        async def validate():
            is_valid = await manager.validate_session_online(profile)
            return is_valid

        is_valid = asyncio.run(validate())

        if is_valid:
            console.print(
                Panel(
                    f"[ok]Profile '{profile}' is valid and authenticated[/ok]",
                    style="green",
                    expand=False,
                )
            )
        else:
            console.print(
                Panel(
                    f"[warning]Profile '{profile}' session expired[/warning]\n\n"
                    "Re-authenticate with: h3xassist browser-auth --profile {profile}",
                    style="yellow",
                    expand=False,
                )
            )
    else:
        is_valid = manager.validate_session(profile)

        if is_valid:
            metadata = manager.load_profile(profile)
            if metadata:
                auth_date = datetime.fromisoformat(metadata["authenticated_at"])
                age = (datetime.now() - auth_date).days
                console.print(
                    Panel(
                        f"[ok]Profile '{profile}' appears valid[/ok]\n\n"
                        f"Authenticated: {age} days ago\n"
                        f"Location: {Path(profiles_dir).expanduser() / profile}",
                        style="green",
                        expand=False,
                    )
                )
            else:
                console.print(f"[info]Profile '{profile}' directory exists[/info]")
        else:
            console.print(
                Panel(
                    f"[error]Profile '{profile}' not found or invalid[/error]",
                    style="red",
                    expand=False,
                )
            )
