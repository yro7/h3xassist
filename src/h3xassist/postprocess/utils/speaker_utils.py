import logging
import unicodedata as _unicodedata
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from h3xassist.storage.recording_handle import RecordingHandle

logger = logging.getLogger(__name__)


def normalize_speaker_name(name: str) -> str:
    """Normalize speaker name by removing zero-width characters and normalizing Unicode."""
    s = (name or "").strip()
    # Remove common zero-width characters
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        s = s.replace(ch, "")
    with suppress(Exception):
        s = _unicodedata.normalize("NFC", s)
    return s


def infer_speaker_count(handle: "RecordingHandle") -> tuple[int | None, int | None]:
    """Infer min/max speaker count from caption intervals to guide diarization."""
    try:
        state = handle.read_caption_intervals()
        if state is None:
            return None, None

        captions_raw = list(state.intervals)
        unique_names = {
            normalize_speaker_name(str(interval.speaker))
            for interval in captions_raw
            if interval.speaker
        }
        unique_names.discard("")

        k = len(unique_names)
        if 1 <= k <= 12:
            min_speakers = k
            # Allow slight freedom upwards for robustness
            max_speakers = min(k + 1, 12)
            logger.info(
                "Inferred speaker count from captions: min=%d, max=%d", min_speakers, max_speakers
            )
            return min_speakers, max_speakers

    except Exception as e:
        logger.warning("Failed to infer speaker count: %s", e)

    return None, None


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
