import logging
import shutil
from typing import TYPE_CHECKING
from uuid import UUID

from h3xassist.storage.recording_handle import RecordingHandle

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from h3xassist.models.recording import RecordingMeta


logger = logging.getLogger(__name__)


class RecordingStore:
    """Minimal filesystem store: one directory per meeting.

    Layout:
      recordings/<uuid>/
        audio.ogg
        transcript.txt
        transcript.json
    """

    def __init__(
        self, base_dir: "Path", *, on_update: "Callable[[RecordingMeta | None], None] | None" = None
    ) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._on_update = on_update

    def create(self, recording_id: UUID) -> RecordingHandle:
        """Create recording handle.

        Args:
            recording_id: Recording ID.

        Returns:
            Recording handle.
        """
        return RecordingHandle(self._base_dir / str(recording_id), on_update=self._on_update)

    def get(self, recording_id: UUID) -> RecordingHandle:
        """Get recording handle.

        Args:
            recording_id: Recording ID.

        Returns:
            Recording handle.
        """
        directory = self._base_dir / str(recording_id)
        if not directory.exists():
            raise FileNotFoundError(directory)
        return RecordingHandle(directory, on_update=self._on_update)

    def list_recordings(self) -> list[UUID]:
        """List all recordings.

        Returns:
            List of recording IDs.
        """
        try:
            entries = sorted([UUID(d.name) for d in self._base_dir.iterdir() if d.is_dir()])
        except FileNotFoundError:
            return []
        return entries

    def delete(self, recording_id: UUID) -> None:
        """Delete recording."""
        directory = self._base_dir / str(recording_id)
        if not directory.exists():
            raise FileNotFoundError(directory)
        shutil.rmtree(directory)
        if self._on_update:
            self._on_update(None)
