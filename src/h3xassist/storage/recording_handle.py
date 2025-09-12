from typing import TYPE_CHECKING

from h3xassist.models.recording import CaptionIntervals, RecordingMeta, Transcript
from h3xassist.postprocess.summarize import MeetingSummary

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class RecordingHandle:
    """Simple wrapper around a recording directory with meta.json."""

    def __init__(
        self, directory: "Path", *, on_update: "Callable[[RecordingMeta], None] | None" = None
    ) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

        self._on_update = on_update
        self._meta_path = directory / "meta.json"
        self._transcript_path = directory / "transcript.json"
        self._captions_path = directory / "captions.json"
        self._summary_path = directory / "summary.json"
        self._audio_path = directory / "audio.ogg"
        self._browser_log_path = directory / "browser.log"

    @property
    def directory(self) -> "Path":
        return self._directory

    @property
    def audio(self) -> "Path":
        return self._audio_path

    @property
    def browser_log(self) -> "Path":
        return self._browser_log_path

    def write_meta(self, meta: RecordingMeta) -> None:
        """Write metadata to meta.json."""
        self._meta_path.write_text(meta.model_dump_json())
        if self._on_update:
            self._on_update(meta)

    def read_meta(self) -> RecordingMeta:
        """Read metadata from meta.json."""
        if not self._meta_path.exists():
            raise FileNotFoundError(self._meta_path)
        return RecordingMeta.model_validate_json(self._meta_path.read_text())

    def write_transcript(self, data: Transcript) -> None:
        """Write transcript files and update metadata."""
        self._transcript_path.write_text(data.model_dump_json(indent=2))

    def write_caption_intervals(self, data: CaptionIntervals) -> None:
        """Write captions file and update metadata."""
        self._captions_path.write_text(data.model_dump_json(indent=2))

    def read_caption_intervals(self) -> CaptionIntervals | None:
        """Load captions if it exists, return None otherwise."""
        if self._captions_path.exists():
            return CaptionIntervals.model_validate_json(self._captions_path.read_text())
        return None

    def write_summary(self, data: MeetingSummary) -> None:
        """Write summary file and update metadata."""
        self._summary_path.write_text(data.model_dump_json(indent=2))

    def read_transcript(self) -> Transcript | None:
        """Load transcript if it exists, return None otherwise."""
        if self._transcript_path.exists():
            return Transcript.model_validate_json(self._transcript_path.read_text())
        return None

    def read_summary(self) -> MeetingSummary | None:
        """Load summary if it exists, return None otherwise."""
        if self._summary_path.exists():
            return MeetingSummary.model_validate_json(self._summary_path.read_text())
        return None

    def clear_results(self) -> None:
        """Clear all processing results before reprocessing.

        Removes transcript and summary files, but keeps audio, metadata, and captions.
        Captions are generated during recording and should be preserved.
        """
        # Remove transcript files
        self._transcript_path.unlink(missing_ok=True)
        transcript_txt = self._directory / "transcript.txt"
        transcript_txt.unlink(missing_ok=True)

        # Remove summary files
        self._summary_path.unlink(missing_ok=True)
        summary_md = self._directory / "summary.md"
        summary_md.unlink(missing_ok=True)
