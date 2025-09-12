import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = os.path.expanduser("~/.config/h3xassist")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.yaml")


# ================= Hierarchical configuration models =================


class GeneralSettings(BaseModel):
    # Human-readable name shown to other participants when joining or presenting in meetings.
    meeting_display_name: str = Field(
        default="H3XAssist",
        title="Meeting display name",
        description="Human-readable name shown to other participants when joining or presenting in meetings.",
    )
    # Your handle/name to highlight personal tasks in summaries (e.g., ih3xcode or @ih3xcode).
    notes_owner_handle: str | None = Field(
        default=None,
        title="Notes owner handle",
        description="Your preferred handle or name used to highlight personal action items in summaries.",
    )


class ModelsSettings(BaseModel):
    # Identifier of WhisperX model to use for automatic speech recognition.
    whisperx_model_name: str = Field(
        default="large-v3",
        title="ASR model name",
        description="Identifier of the WhisperX model used for transcription.",
    )
    # Default language for ASR transcription (e.g. 'uk', 'en', 'de'). If None, auto-detect.
    default_language: str | None = Field(
        default=None,
        title="Default ASR language",
        description="Default language code for ASR transcription (e.g. 'uk', 'en', 'de'). If None, WhisperX will auto-detect the language.",
    )
    # Local directory to cache downloaded models and related assets.
    cache_dir: str = Field(
        default="~/.local/share/h3xassist/models",
        title="Models cache directory",
        description="Local directory where downloaded models and assets are cached.",
    )
    # Optional access token for Hugging Face, required for diarization or gated models.
    hf_token: str | None = Field(
        default=None,
        title="Hugging Face token",
        description="Optional access token used for diarization backends or gated models.",
    )
    device: str | None = Field(
        default=None,
        title="Device",
        description="Device to use for WhisperX model. If None, WhisperX will use the default device.",
    )
    compute_type: str = Field(
        default="float16",
        title="Compute type",
        description="Compute type to use for WhisperX model. float16 or int8",
    )
    batch_size: int = Field(
        default=16,
        title="Batch size",
        description="Batch size to use for WhisperX model.",
    )


class BrowserSettings(BaseModel):
    # Which browser to use.
    browser_bin: str = Field(
        default="chromium-browser",
        title="Browser binary",
        description="Which browser to use.",
    )
    # Whether to show the browser window.
    browser_visible: bool = Field(
        default=False,
        title="Browser visible",
        description="Whether to show the browser window. If False, the browser will be headless.",
    )
    # Folder where browser user-data directories are stored per profile.
    profiles_base_dir: str = Field(
        default="~/.config/h3xassist/browser-profiles",
        title="Browser profiles base directory",
        description="Base directory for browser user-data profiles.",
    )
    # Profile name to use when none is explicitly specified.
    default_profile_name: str = Field(
        default="default",
        title="Default browser profile name",
        description="Profile name used by default when a specific profile is not provided.",
    )
    # Browser stability profile for automated meeting recording.
    stability_profile: Literal["default", "software_safe", "gpu_balanced"] = Field(
        default="default",
        title="Browser stability profile",
        description="Stability profile for browser: 'default' (standard flags), 'software_safe' (CPU-only for max stability), 'gpu_balanced' (GPU enabled but no hardware video decode).",
    )
    # Force WebRTC to use TCP via TURN servers instead of UDP.
    force_turn_tcp: bool = Field(
        default=False,
        title="Force TURN TCP",
        description="Force WebRTC to use TCP via TURN servers instead of UDP for better network compatibility.",
    )
    # Disable browser telemetry and domain reliability reporting.
    disable_telemetry: bool = Field(
        default=True,
        title="Disable telemetry",
        description="Disable browser telemetry and domain reliability reporting for cleaner operation.",
    )


class OpusSettings(BaseModel):
    # Bitrate string (e.g. "24k", "32k") for Opus encoding.
    bitrate: str = Field(
        default="24k",
        title="Opus target bitrate",
        description="Target bitrate for Opus encoder, expressed as a string (e.g. '24k').",
    )
    # Output container to mux Opus audio into (e.g. ogg).
    container: str = Field(
        default="ogg",
        title="Opus container format",
        description="Container format for Opus output (e.g. 'ogg').",
    )


class AudioSettings(BaseModel):
    # Target PCM sampling rate used across pipeline (Hz).
    pcm_sample_rate: int = Field(
        default=16000,
        title="PCM sample rate (Hz)",
        description="Target PCM sampling rate used by the audio pipeline in Hertz.",
    )
    # Number of channels for PCM audio (1=mono, 2=stereo).
    pcm_channels: int = Field(
        default=1,
        title="PCM channels",
        description="Number of audio channels for PCM data (1=mono, 2=stereo).",
    )
    # Signed integer/float PCM format (e.g. s16, s32, f32).
    pcm_format: str = Field(
        default="s16",
        title="PCM sample format",
        description="Sample format for PCM audio (e.g. 's16', 's32', 'f32').",
    )
    # Bytes per PCM sample; derived from format and used for framing.
    pcm_bytes_per_sample: int = Field(
        default=2,
        title="PCM bytes per sample",
        description="Number of bytes per PCM sample; affects framing and buffer sizes.",
    )
    # Duration of a single audio frame for processing and encoding (ms).
    frame_ms: int = Field(
        default=10,
        title="Frame size (ms)",
        description="Duration of a single audio frame used during processing and encoding, in milliseconds.",
    )
    # Nested configuration for Opus encoder parameters.
    opus: OpusSettings = Field(
        default_factory=OpusSettings,
        title="Opus encoder settings",
        description="Nested configuration for Opus-related encoding parameters.",
    )


class HttpSettings(BaseModel):
    # Host to bind the HTTP server to.
    host: str = Field(
        default="127.0.0.1",
        title="HTTP host",
        description="Host address to bind the HTTP server to (serves both API and web interface).",
    )
    # Port to bind the HTTP server to.
    port: int = Field(
        default=11411,
        title="HTTP port",
        description="Port number to bind the HTTP server to (serves both API and web interface).",
    )


class PathsSettings(BaseModel):
    # Root directory where meeting recordings and artifacts are stored.
    base_dir: str = Field(
        default="~/.local/share/h3xassist",
        title="Base directory",
        description="Root directory used to store meeting recordings and derived artifacts.",
    )


class ExportSettings(BaseModel):
    # Directory where final human-readable summaries are stored.
    obsidian_enabled: bool = Field(
        default=True,
        title="Obsidian enabled",
        description="Whether to export summaries to Obsidian.",
    )
    obsidian_base_dir: str | None = Field(
        default=None,
        title="Obsidian base directory",
        description="Directory where finalized summary markdown and JSON artifacts are stored.",
    )


class PostprocessSettings(BaseModel):
    # Maximum number of post-processing jobs to run in parallel.
    concurrency: int = Field(
        default=1,
        title="Post-process concurrency",
        description="Maximum number of post-processing jobs that may run concurrently.",
    )


class RecordingSettings(BaseModel):
    # Toggle periodic recording/encoder metrics collection.
    metrics_enabled: bool = Field(
        default=False,
        title="Recording metrics enabled",
        description="Whether to collect and emit recording/encoder metrics periodically.",
    )
    # How often to collect and emit metrics when enabled (seconds).
    metrics_interval_sec: int = Field(
        default=5,
        title="Metrics interval (sec)",
        description="Interval in seconds for metrics collection when metrics are enabled.",
    )
    # Extra time to flush encoders/buffers after stream end (seconds).
    drain_sec: float = Field(
        default=5.0,
        title="Drain timeout (sec)",
        description="Additional time in seconds to flush encoders and buffers after stream end.",
    )


class OutlookSettings(BaseModel):
    # Directory (tenant) identifier for Microsoft Graph.
    tenant_id: str = Field(
        ...,
        title="Azure AD tenant ID",
        description="Azure Active Directory tenant (directory) identifier used for Microsoft Graph OAuth.",
    )
    # Application registration client ID for Microsoft Graph OAuth.
    client_id: str = Field(
        ...,
        title="Application (client) ID",
        description="Client ID of the Azure AD application registration for Microsoft Graph.",
    )
    # Primary mailbox email used to access Outlook/Calendar.
    user_email: str = Field(
        ...,
        title="User email",
        description="Primary mailbox email used to access Outlook and Calendar resources.",
    )
    # File path to persist interactive authentication tokens (MSAL cache).
    token_cache_path: str = Field(
        default=os.path.expanduser("~/.config/h3xassist/msal_cache.json"),
        title="MSAL token cache path",
        description="Filesystem path where MSAL stores OAuth tokens for reuse.",
    )


class IntegrationsSettings(BaseModel):
    # Optional Microsoft Graph/Outlook configuration.
    outlook: OutlookSettings | None = Field(
        default=None,
        title="Outlook integration",
        description="Optional configuration for Microsoft Graph/Outlook integration.",
    )
    # Calendar sync interval in minutes.
    calendar_sync_interval_minutes: int = Field(
        default=5,
        title="Calendar sync interval",
        description="How often to sync with calendar in minutes.",
        ge=1,
        le=1440,  # Max 24 hours
    )


class SpeakerAssignSettings(BaseModel):
    # Whether to refine diarization using anchor segments.
    enabled: bool = Field(
        default=False,
        title="Anchor mapping enabled",
        description="Enable refinement of diarization via anchor segments.",
    )
    # Discard anchors shorter than this duration (seconds).
    min_seg_sec: float = Field(
        default=2.5,
        title="Minimum anchor segment length (sec)",
        description="Anchors shorter than this many seconds are discarded.",
    )
    # Overlap threshold to consider anchors valid.
    min_overlap_ratio: float = Field(
        default=0.75,
        title="Minimum anchor overlap ratio",
        description="Minimum overlap ratio required for an anchor to be considered valid.",
    )
    # Prefer strict 1:1 anchor-to-speaker mapping.
    one_to_one: bool = Field(
        default=True,
        title="Enforce one-to-one mapping",
        description="If true, enforces a strict one-to-one anchor-to-speaker relation.",
    )
    min_ratio: float = Field(
        default=0.5,
        title="Minimum ratio",
        description="Minimum ratio required for an anchor to be considered valid.",
    )


class SummarizationSettings(BaseModel):
    # Toggle automatic summarization after processing completes.
    enabled: bool = Field(
        default=True,
        title="Summarization enabled",
        description="Whether to run summarization automatically after processing.",
    )
    # Google API key for the Generative AI client.
    provider_token: str | None = Field(
        default=None,
        title="Google API key",
        description="Google API key used by the Generative AI client.",
    )
    # Target model to use for summarization.
    model_name: str = Field(
        default="gemini-2.5-flash",
        title="LLM model name",
        description="Model name used by the Google Generative AI client.",
    )
    # Language for generated summary (e.g. 'uk', 'en', 'de').
    summary_language: str | None = Field(
        default=None,
        title="Summary language",
        description="Language code for generated summary (e.g. 'uk', 'en', 'de'). If None, summary will be in the same language as transcript.",
    )
    # Creativity/randomness of the generation.
    temperature: float = Field(
        default=0.2,
        title="Sampling temperature",
        description="Controls randomness of generation; higher values increase creativity.",
    )
    # Hard limit to truncate input fed into LLM.
    max_chars: int = Field(
        default=120_000,
        title="Max input characters",
        description="Maximum number of input characters to feed into the summarization model.",
    )

    # Retry behavior for provider calls.
    retry_max_attempts: int = Field(
        default=5,
        title="Retry max attempts",
        description="Maximum number of attempts (initial try + retries) for provider calls.",
    )
    retry_initial_delay_sec: float = Field(
        default=1.0,
        title="Retry initial delay (sec)",
        description="Initial delay before the first retry attempt (seconds).",
    )
    retry_backoff_multiplier: float = Field(
        default=2.0,
        title="Retry backoff multiplier",
        description="Exponential backoff multiplier applied to the retry delay.",
    )
    retry_max_delay_sec: float = Field(
        default=20.0,
        title="Retry max delay (sec)",
        description="Upper bound for the backoff delay between retries (seconds).",
    )
    retry_jitter_sec: float = Field(
        default=0.5,
        title="Retry jitter (sec)",
        description="Random jitter added to backoff delay to avoid thundering herd (seconds).",
    )
    retry_status_codes: list[int] = Field(
        default_factory=lambda: [408, 409, 425, 429, 500, 502, 503, 504],
        title="Retryable status codes",
        description="HTTP status codes considered retryable for provider calls.",
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="H3XASSIST_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    general: GeneralSettings = Field(
        default_factory=GeneralSettings,
        title="general",
        description="Basic application identity and display naming.",
    )
    models: ModelsSettings = Field(
        default_factory=ModelsSettings,
        title="models",
        description="Speech model selection and cache configuration.",
    )
    browser: BrowserSettings = Field(
        default_factory=BrowserSettings,
        title="browser",
        description="Browser profiles configuration (user-data directories, default profile).",
    )
    audio: AudioSettings = Field(
        default_factory=AudioSettings,
        title="audio",
        description="Audio pipeline parameters and Opus encoder settings.",
    )
    http: HttpSettings = Field(
        default_factory=HttpSettings,
        title="http",
        description="HTTP server configuration (host and port for API and web interface).",
    )
    paths: PathsSettings = Field(
        default_factory=PathsSettings,
        title="paths",
        description="Filesystem paths for meetings, schedule, and state files.",
    )
    postprocess: PostprocessSettings = Field(
        default_factory=PostprocessSettings,
        title="postprocess",
        description="Post-processing service options (concurrency).",
    )
    recording: RecordingSettings = Field(
        default_factory=RecordingSettings,
        title="recording",
        description="Recording metrics and drain behaviour.",
    )
    integrations: IntegrationsSettings = Field(
        default_factory=IntegrationsSettings,
        title="integrations",
        description="External integrations configuration (e.g., Outlook / Microsoft Graph).",
    )
    speaker: SpeakerAssignSettings = Field(
        default_factory=SpeakerAssignSettings,
        title="speaker",
        description="Speaker assignment algorithm parameters and debugging options.",
    )
    summarization: SummarizationSettings = Field(
        default_factory=SummarizationSettings,
        title="summarization",
        description="LLM-based summarization settings and limits.",
    )
    export: ExportSettings = Field(
        default_factory=ExportSettings,
        title="export",
        description="Export settings for summaries and Obsidian.",
    )

    @classmethod
    def settings_customise_sources(  # type: ignore[no-untyped-def]
        cls,
        settings_cls,  # noqa: ARG003
        init_settings,
        env_settings,
        dotenv_settings,  # noqa: ARG003
        file_secret_settings,
    ):
        def yaml_config_settings_source() -> dict[str, Any]:
            path = Path(SETTINGS_FILE).expanduser()
            if path.exists():
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                    return data or {}
                except Exception:
                    return {}
            return {}

        return (
            init_settings,
            env_settings,
            yaml_config_settings_source,
            file_secret_settings,
        )


def _ensure_config_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def save_settings(settings: AppSettings) -> None:
    _ensure_config_dir()
    data = settings.model_dump(mode="python")
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


# Module-level settings instance
settings = AppSettings()
