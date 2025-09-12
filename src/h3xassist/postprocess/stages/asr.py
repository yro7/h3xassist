import logging
from typing import TYPE_CHECKING

from h3xassist.postprocess.pipeline import ProcessingStage
from h3xassist.postprocess.utils.speaker_utils import infer_speaker_count

if TYPE_CHECKING:
    from h3xassist.postprocess.pipeline import ProcessingContext
    from h3xassist.postprocess.whisperx import WhisperXService

logger = logging.getLogger(__name__)


class ASRStage(ProcessingStage):
    """Stage that performs ASR (Automatic Speech Recognition) and diarization."""

    def __init__(self, whisperx_service: "WhisperXService") -> None:
        self._engine = whisperx_service

    @property
    def name(self) -> str:
        return "asr"

    async def process(self, context: "ProcessingContext") -> "ProcessingContext":
        """Run ASR and diarization on the audio file."""
        # Infer speaker count from captions to guide diarization
        min_speakers, max_speakers = infer_speaker_count(context.handle)

        meta = context.handle.read_meta()
        # Run full transcription to obtain words and diarization clusters
        segments = await self._engine.transcribe_full(
            context.handle.audio,
            language=meta.language if meta is not None else None,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        context.segments = segments

        logger.info("ASR completed: %d segments", len(segments))
        return context
