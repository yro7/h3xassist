"""Factory functions for creating different pipeline configurations."""

from pathlib import Path
from typing import TYPE_CHECKING

from h3xassist.postprocess.pipeline import Pipeline
from h3xassist.postprocess.service import PostprocessService
from h3xassist.postprocess.stages.asr import ASRStage
from h3xassist.postprocess.stages.export import ExportStage
from h3xassist.postprocess.stages.mapping import SpeakerMappingStage
from h3xassist.postprocess.stages.summary import SummaryStage
from h3xassist.postprocess.summarize import SummarizationService
from h3xassist.postprocess.whisperx import WhisperXService
from h3xassist.settings import settings

if TYPE_CHECKING:
    from h3xassist.storage.recording_store import RecordingStore


def create_full_pipeline() -> Pipeline:
    """Create full postprocessing pipeline with optional summarization and Obsidian export.

    All configuration is fully determined from settings.py
    """

    stages = [
        ASRStage(
            WhisperXService(
                model_name=settings.models.whisperx_model_name,
                model_dir=Path(settings.models.cache_dir).expanduser(),
                hf_token=settings.models.hf_token,
                compute_type=settings.models.compute_type,
                batch_size=settings.models.batch_size,
                device=settings.models.device,
            )
        ),
        SpeakerMappingStage(
            skip_mapping=not settings.speaker.enabled,
            min_seg_sec=settings.speaker.min_seg_sec,
            min_overlap_ratio=settings.speaker.min_overlap_ratio,
            one_to_one=settings.speaker.one_to_one,
            min_ratio=settings.speaker.min_ratio,
        ),
    ]

    if settings.summarization.enabled:
        token = settings.summarization.provider_token
        if token is None:
            raise ValueError("Summarization provider token is required")
        stages.append(
            SummaryStage(
                SummarizationService(
                    model_name=settings.summarization.model_name,
                    summary_language=settings.summarization.summary_language,
                    temperature=settings.summarization.temperature,
                    provider_token=token,
                )
            )
        )

    # Add export stage with appropriate configuration
    stages.append(
        ExportStage(
            export_obsidian=settings.export.obsidian_enabled,
            obsidian_base_dir=Path(settings.export.obsidian_base_dir).expanduser()
            if settings.export.obsidian_base_dir
            else None,
        )
    )

    return Pipeline(stages)


def create_postprocess_service(store: "RecordingStore") -> PostprocessService:
    """Create background postprocess service with full pipeline."""

    pipeline = create_full_pipeline()
    return PostprocessService(pipeline, store, max_concurrency=settings.postprocess.concurrency)
