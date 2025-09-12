from __future__ import annotations


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Calculate overlap between two time intervals."""
    s = max(a[0], b[0])
    e = min(a[1], b[1])
    return max(0.0, e - s)


def union_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge overlapping time intervals."""
    if not intervals:
        return []
    intervals = sorted(
        ((max(0.0, s), max(0.0, e)) for s, e in intervals if e > s), key=lambda x: x[0]
    )
    merged: list[tuple[float, float]] = []
    cs, ce = intervals[0]
    for s, e in intervals[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            merged.append((cs, ce))
            cs, ce = s, e
    merged.append((cs, ce))
    return merged
