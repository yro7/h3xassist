import logging
from typing import TYPE_CHECKING

from h3xassist.postprocess.pipeline import ProcessingStage
from h3xassist.speaker.mapping import (
    apply_mapping_to_segments,
    build_speaker_mapping_anchor,
)

if TYPE_CHECKING:
    from h3xassist.postprocess.pipeline import ProcessingContext

logger = logging.getLogger(__name__)


class SpeakerMappingStage(ProcessingStage):
    """Stage that maps diarization clusters to UI participant names."""

    def __init__(
        self,
        skip_mapping: bool,
        min_seg_sec: float,
        min_overlap_ratio: float,
        one_to_one: bool,
        min_ratio: float,
    ) -> None:
        self._skip_mapping = skip_mapping
        self._min_seg_sec = min_seg_sec
        self._min_overlap_ratio = min_overlap_ratio
        self._one_to_one = one_to_one
        self._min_ratio = min_ratio

    @property
    def name(self) -> str:
        return "speaker_mapping"

    async def process(self, context: "ProcessingContext") -> "ProcessingContext":
        """Map diarization clusters to UI names using caption intervals."""
        if self._skip_mapping or not context.segments:
            logger.info("Skipping speaker mapping")
            return context

        caption_intervals = context.handle.read_caption_intervals()
        if caption_intervals is None:
            logger.warning("No caption intervals found for mapping")
            return context

        # Use anchor-based speaker mapping for better accuracy
        logger.debug("Using anchor-based speaker mapping")
        mapping, confidences = build_speaker_mapping_anchor(
            context.segments,
            caption_intervals.intervals,
            min_seg_sec=self._min_seg_sec,
            min_overlap_ratio=self._min_overlap_ratio,
            one_to_one=self._one_to_one,
            min_ratio=self._min_ratio,
        )

        context.segments = apply_mapping_to_segments(
            context.segments, mapping, confidences=confidences
        )
        logger.debug("Speaker mapping completed: %d segments mapped", len(context.segments))
        return context
