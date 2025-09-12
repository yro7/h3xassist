import asyncio
import gc
import logging
import time
from collections import defaultdict
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from typing_extensions import TypedDict

from h3xassist.models.recording import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


logger = logging.getLogger(__name__)


class AlignedResult(TypedDict):
    """WhisperX alignment result structure."""

    segments: list[dict[str, Any]]


# Using TranscriptSegment from models.recording instead of local Segment


class WhisperXService:
    """Minimal wrapper to produce segment-level transcript without word timings.

    This module purposefully avoids complex configuration. It assumes models
    are cached/configured by the environment and focuses on returning
    a simple segment list suitable for transcript.json.
    """

    def __init__(
        self,
        *,
        model_name: str,
        model_dir: "Path",
        compute_type: str,
        batch_size: int,
        hf_token: str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_dir = str(model_dir) if model_dir else None
        self.batch_size = batch_size
        self.hf_token = hf_token

        # Determine device once at init, allow override via param
        if device is None:
            try:
                import torch

                chosen = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                chosen = "cpu"
        else:
            try:
                import torch

                torch_available = torch.cuda.is_available()
            except Exception:
                torch_available = False
            if device == "cuda" and not torch_available:
                logger.warning("CUDA requested but not available; using CPU instead")
                chosen = "cpu"
            else:
                chosen = device

        if chosen == "cpu" and compute_type == "float16":
            logger.warning("CPU requested but float16 is not supported; using int8 instead")
            compute_type = "int8"

        self.compute_type = compute_type
        self.device = chosen

        logger.info(
            "WhisperX initialized: model='%s', device=%s, compute=%s, batch_size=%s, cache_dir=%s, HF token=%s",
            self.model_name,
            self.device,
            self.compute_type,
            self.batch_size,
            self.model_dir or "<default>",
            "provided" if bool(self.hf_token) else "missing",
        )

    async def transcribe_full(
        self,
        audio_path: "Path",
        language: str | None = None,
        *,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[TranscriptSegment]:
        """Run ASR, alignment and diarization.

        Args:
            audio_path: Path to the audio file.
            language: Language code for ASR transcription.
            min_speakers: Minimum number of speakers to diarize.
            max_speakers: Maximum number of speakers to diarize.

        Returns:
            List of segments.
        """

        def _cleanup_gpu() -> None:
            try:
                if self.device == "cuda":
                    gc.collect()
                    import torch

                    torch.cuda.empty_cache()
            except Exception:
                pass

        def _work() -> list[TranscriptSegment]:
            import whisperx

            t_a0 = time.perf_counter()
            audio = whisperx.load_audio(audio_path.as_posix())
            t_a1 = time.perf_counter()
            logger.debug("load_audio: %.2fs", t_a1 - t_a0)

            logger.debug(
                "Loading WhisperX model '%s' (compute=%s, cache_dir=%s)",
                self.model_name,
                self.compute_type,
                self.model_dir or "<default>",
            )
            t_m0 = time.perf_counter()
            model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type=self.compute_type,
                download_root=self.model_dir,
                local_files_only=True,
                language=language,
                asr_options={
                    # Determinism and search depth
                    "beam_size": 7,  # could be 8, but minimal gain
                    "patience": 1.2,  # wider exploration without beam growth
                    # "temperatures": [0.0],          # no sampling
                    "best_of": 1,  # doesn't affect beam-search; keep 1
                },
            )

            try:
                logger.debug(
                    "Running ASR (batch_size=%s, language=%s)", self.batch_size, language or "auto"
                )
                t_asr0 = time.perf_counter()
                asr = model.transcribe(
                    audio,
                    language=language,
                    batch_size=self.batch_size,
                )
            finally:
                del model
                _cleanup_gpu()

            t_asr1 = time.perf_counter()
            logger.debug("ASR: %.2fs (model_load: %.2fs)", t_asr1 - t_asr0, t_asr0 - t_m0)

            segments = asr.get("segments") or []
            lang = language or asr.get("language") or "en"

            # Alignment
            try:
                align_model, metadata = whisperx.load_align_model(
                    language_code=lang, device=self.device
                )
                try:
                    t_al0 = time.perf_counter()
                    aligned = whisperx.align(
                        segments,
                        align_model,
                        metadata,
                        audio,
                        self.device,
                        return_char_alignments=False,
                    )
                    t_al1 = time.perf_counter()
                    logger.debug("Alignment: %.2fs", t_al1 - t_al0)
                finally:
                    del align_model
                    _cleanup_gpu()
            except Exception as e:
                logger.warning(
                    "Alignment failed; continuing with raw ASR segments: %s", e, exc_info=True
                )
                aligned = AlignedResult(segments=segments)

            # Diarization
            diarize_segments = None
            try:
                from whisperx.diarize import DiarizationPipeline

                t_d0 = time.perf_counter()
                diarize_pipeline = DiarizationPipeline(
                    device=self.device, use_auth_token=self.hf_token
                )
                diarize_segments = diarize_pipeline(
                    audio,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                )
                t_d1 = time.perf_counter()
                assigned = whisperx.assign_word_speakers(diarize_segments, aligned)
                t_aw1 = time.perf_counter()
                logger.debug(
                    "Diarization: %.2fs, assign_word_speakers: %.2fs", t_d1 - t_d0, t_aw1 - t_d1
                )
            except Exception as e:
                logger.warning(
                    "Diarization failed; returning unassigned segments: %s", e, exc_info=True
                )
                assigned = aligned
            finally:
                with suppress(Exception):
                    del diarize_pipeline
                _cleanup_gpu()

            simple = _to_segments(assigned.get("segments") or [])

            logger.debug(
                "Full transcription finished: segments=%s",
                len(simple),
            )

            return simple

        return await asyncio.to_thread(_work)


def _to_segments(raw_segments: "Iterable[dict[str, Any]]") -> list[TranscriptSegment]:
    result: list[TranscriptSegment] = []
    for seg in raw_segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip()
        sp = seg.get("speaker")
        if not sp:
            # Majority vote over words.speaker if present
            words = seg.get("words") or []
            counts: defaultdict[str, int] = defaultdict(int)
            for w in words:
                s = w.get("speaker")
                if not s:
                    continue
                counts[str(s)] += 1
            sp = max(counts, key=lambda k: counts[k]) if counts else "SPEAKER_UNKNOWN"
        result.append(TranscriptSegment(start=start, end=end, speaker=str(sp), text=text))
    return result
