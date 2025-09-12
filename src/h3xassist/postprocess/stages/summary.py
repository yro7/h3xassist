import logging
from typing import TYPE_CHECKING

from h3xassist.postprocess.pipeline import ProcessingStage
from h3xassist.postprocess.utils.speaker_utils import format_time

if TYPE_CHECKING:
    from h3xassist.models.recording import TranscriptSegment
    from h3xassist.postprocess.pipeline import ProcessingContext
    from h3xassist.postprocess.summarize import SummarizationService

logger = logging.getLogger(__name__)


class SummaryStage(ProcessingStage):
    """Stage that generates meeting summaries using LLM."""

    def __init__(self, summarization_service: "SummarizationService") -> None:
        self._summarizer = summarization_service

    @property
    def name(self) -> str:
        return "summary"

    async def process(self, context: "ProcessingContext") -> "ProcessingContext":
        """Generate meeting summary and export to various formats."""

        if not context.segments:
            logger.warning("No mapped segments for summarization")
            return context

        # Build plain text for LLM input
        transcript_text = self._build_transcript_text(context.segments)

        # Generate summary
        try:
            summary = await self._summarizer.summarize(
                transcript_text=transcript_text,
            )
            context.summary = summary
        except Exception:
            logger.exception("Summarization failed")
            return context

        logger.debug("Summary generated")
        return context

    def _build_transcript_text(self, segments: list["TranscriptSegment"]) -> str:
        """Build transcript text from mapped segments."""

        lines = []
        for seg in segments:
            lines.append(
                f"[{format_time(seg.start)} - {format_time(seg.end)}] {seg.speaker}: {seg.text}"
            )
        return "\n".join(lines)
