import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from h3xassist.models.recording import TranscriptSegment
    from h3xassist.postprocess.summarize import MeetingSummary
    from h3xassist.storage.recording_handle import RecordingHandle

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """Context object passed between pipeline stages."""

    handle: "RecordingHandle"

    # Intermediate results
    segments: list["TranscriptSegment"] | None = None
    summary: "MeetingSummary | None" = None

    # Performance metrics
    metrics: dict[str, float] = field(default_factory=dict)

    def record_metric(self, stage_name: str, duration_sec: float) -> None:
        """Record performance metric for a stage."""
        self.metrics[f"stage:{stage_name}"] = duration_sec
        logger.info("Completed %s stage in %.2fs", stage_name, duration_sec)


class ProcessingStage(ABC):
    """Base class for all pipeline stages."""

    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """Process the context and return updated context."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Stage name for logging and metrics."""
        pass


class Pipeline:
    """Orchestrates processing stages with metrics and error handling."""

    def __init__(self, stages: list[ProcessingStage]) -> None:
        self._stages = stages

    async def process(
        self,
        handle: "RecordingHandle",
    ) -> ProcessingContext:
        """Run all stages in sequence."""
        context = ProcessingContext(
            handle=handle,
        )

        # Update stage to preparing (best-effort)
        t0 = time.perf_counter()
        try:
            st = handle.read_meta()
            if st is not None:
                st.postprocess_stage = "preparing"
                handle.write_meta(st)
        except Exception as e:
            logger.warning("Failed to update postprocess_stage: %s", e)

        context.record_metric("stage_update", time.perf_counter() - t0)

        # Run stages sequentially
        total_t0 = time.perf_counter()
        for stage in self._stages:
            stage_t0 = time.perf_counter()
            try:
                st = handle.read_meta()
                if st is not None:
                    st.postprocess_stage = stage.name
                    handle.write_meta(st)
                else:
                    logger.warning("Failed to update meta to %s", stage.name)  # type: ignore[unreachable]
                context = await stage.process(context)
                context.record_metric(stage.name, time.perf_counter() - stage_t0)
            except Exception:
                logger.exception("Stage %s failed", stage.name)
                raise

        st = handle.read_meta()
        if st is not None:
            st.postprocess_stage = None
            handle.write_meta(st)

        total_duration = time.perf_counter() - total_t0
        logger.info(
            "Pipeline completed: dir=%s stages=%d total=%.2fs",
            handle.directory,
            len(self._stages),
            total_duration,
        )

        return context
