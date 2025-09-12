import logging
from typing import TYPE_CHECKING

from h3xassist.models.recording import TranscriptSegment
from h3xassist.speaker.utils import overlap, union_intervals

if TYPE_CHECKING:
    from collections.abc import Iterable

    from h3xassist.models.recording import CaptionInterval

logger = logging.getLogger(__name__)


def build_speaker_mapping_anchor(
    diar_segments: "Iterable[TranscriptSegment]",
    caption_intervals: "Iterable[CaptionInterval]",
    *,
    min_seg_sec: float,
    min_overlap_ratio: float,
    one_to_one: bool,
    min_ratio: float,
) -> tuple[dict[str, str], dict[str, float]]:
    """Anchor-based cluster→name mapping using longest high-confidence diar segments.

    Args:
        diar_segments: Iterable of TranscriptSegment objects to map.
        caption_intervals: Iterable of CaptionInterval objects to use for mapping.
        min_seg_sec: Minimum segment duration in seconds.
        min_overlap_ratio: Minimum overlap ratio for mapping.
        one_to_one: Whether to enforce one-to-one mapping.
        min_ratio: Minimum ratio for mapping.

    Returns:
        tuple[dict[str, str], dict[str, float]]: A tuple containing the mapping and confidence scores.
    """
    logger.info("Running anchor-based speaker mapping")

    # Build caption intervals by UI name (merged/normalized)
    by_name: dict[str, list[tuple[float, float]]] = {}
    for it in caption_intervals:
        if not it.speaker:
            continue
        by_name.setdefault(str(it.speaker), []).append((float(it.start), float(it.end)))
    for k in list(by_name.keys()):
        by_name[k] = union_intervals(by_name[k])

    # Collect diar segments per cluster
    by_cluster_segs: dict[str, list[TranscriptSegment]] = {}
    for seg in diar_segments:
        if not seg.speaker:
            continue
        by_cluster_segs.setdefault(str(seg.speaker), []).append(seg)

    # Precompute anchor candidates
    candidates: list[tuple[str, str, float]] = []  # (cluster, name, ratio)
    for cluster, segs in by_cluster_segs.items():
        for seg in segs:
            dur = max(0.0, float(seg.end) - float(seg.start))
            if dur < min_seg_sec:
                continue
            # Find best-overlap UI name for this segment
            best_name = None
            best_val = 0.0
            for name, ints in by_name.items():
                # Sum overlap with all intervals for the name
                total_ov = 0.0
                for s, e in ints:
                    total_ov += overlap((float(seg.start), float(seg.end)), (s, e))
                if total_ov > best_val:
                    best_val = total_ov
                    best_name = name
            if dur <= 0.0 or best_name is None:
                continue
            ratio = best_val / dur if dur > 0 else 0.0
            if ratio >= min_overlap_ratio:
                candidates.append((cluster, best_name, ratio))

    # Greedy assign anchors
    candidates.sort(reverse=True)
    mapping: dict[str, str] = {}
    confidence: dict[str, float] = {}
    used_names: set[str] = set()
    for cluster, name, ratio in candidates:
        if cluster in mapping:
            continue
        if one_to_one and name in used_names:
            continue
        mapping[cluster] = name
        confidence[cluster] = max(0.0, min(1.0, ratio))
        used_names.add(name)

    # Fallback for remaining clusters using overall overlap ratio
    cluster_total: dict[str, float] = {}
    for cluster, segs in by_cluster_segs.items():
        cluster_total[cluster] = sum(max(0.0, float(s.end) - float(s.start)) for s in segs)

    for cluster, segs in by_cluster_segs.items():
        if cluster in mapping:
            continue
        best_name = None
        best_val = 0.0
        for name, ints in by_name.items():
            if one_to_one and name in used_names:
                continue
            ov = 0.0
            for seg in segs:
                for s, e in ints:
                    ov += overlap((float(seg.start), float(seg.end)), (s, e))
            if ov > best_val:
                best_val = ov
                best_name = name
        total = cluster_total.get(cluster, 0.0)
        ratio = (best_val / total) if total > 0 else 0.0
        if best_name and ratio >= min_ratio:
            mapping[cluster] = best_name
            confidence[cluster] = max(0.0, min(1.0, ratio))
            used_names.add(best_name)
        else:
            mapping[cluster] = "SPEAKER_UNKNOWN"
            confidence[cluster] = 0.0

    return mapping, confidence


def apply_mapping_to_segments(
    segments: list[TranscriptSegment],
    mapping: dict[str, str],
    *,
    confidences: dict[str, float] | None = None,
) -> list[TranscriptSegment]:
    """Apply speaker mapping to segments and return TranscriptSegment objects."""

    logger.info("Applying mapping to segments")
    out: list[TranscriptSegment] = []
    for seg in segments:
        mapped_speaker = mapping.get(seg.speaker, seg.speaker or "SPEAKER_UNKNOWN")
        confidence = None
        if confidences is not None and seg.speaker in confidences:
            confidence = confidences[seg.speaker]

        mapped_seg = TranscriptSegment(
            start=seg.start,
            end=seg.end,
            speaker=mapped_speaker,
            text=seg.text or "",
            speaker_confidence=confidence,
        )
        out.append(mapped_seg)
    return out
