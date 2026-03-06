from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import HorseData


@dataclass(frozen=True)
class TimeFeatureResult:
    raw_time: float | None
    time_index: float | None
    time_z: float | None
    used_runs: List[str]
    debug: List[str]


def compute_time_features(
    horses: List[HorseData],
    surface: str,
    distance_m: int,
    track_group: str,
) -> Dict[int, TimeFeatureResult]:
    bucket = _distance_bucket(distance_m)
    key_runs: List[Tuple[int, float, float]] = []
    used: Dict[int, List[str]] = {horse.number: [] for horse in horses}
    debug: Dict[int, List[str]] = {horse.number: [] for horse in horses}

    for horse in horses:
        times_sec: List[float] = []
        times_per_100m: List[float] = []
        for run in horse.past_runs:
            if run.time_sec is None:
                debug[horse.number].append(f"skip:{run.evidence_id}:missing_time")
                continue
            if run.surface != surface:
                debug[horse.number].append(f"skip:{run.evidence_id}:surface={run.surface}")
                continue
            if run.distance_m is None:
                debug[horse.number].append(f"skip:{run.evidence_id}:missing_distance")
                continue
            if _distance_bucket(run.distance_m) != bucket:
                debug[horse.number].append(
                    f"skip:{run.evidence_id}:distance={run.distance_m}"
                )
                continue
            if run.track is None:
                debug[horse.number].append(f"skip:{run.evidence_id}:missing_track")
                continue
            if run.track != track_group:
                debug[horse.number].append(f"skip:{run.evidence_id}:track={run.track}")
                continue
            times_sec.append(run.time_sec)
            per_100m = (run.time_sec / run.distance_m) * 100.0
            times_per_100m.append(per_100m)
            used[horse.number].append(
                f"{run.evidence_id}:{run.surface}:{run.distance_m}:{run.track}"
            )
        if times_sec:
            avg_time = sum(times_sec) / len(times_sec)
            avg_per_100m = sum(times_per_100m) / len(times_per_100m)
            key_runs.append((horse.number, avg_time, avg_per_100m))

    mean_per_100m, std_per_100m = _mean_std([per_100m for _, _, per_100m in key_runs])
    results: Dict[int, TimeFeatureResult] = {}
    for horse in horses:
        record = next((row for row in key_runs if row[0] == horse.number), None)
        if record is None:
            results[horse.number] = TimeFeatureResult(None, None, None, [], debug[horse.number])
            continue
        _, avg_time, avg_per_100m = record
        # Lower time-per-distance is better. Convert to a compact 0..2 score.
        time_z = None
        time_index = 1.0
        if std_per_100m:
            time_z = -(avg_per_100m - mean_per_100m) / std_per_100m
            time_index = _clamp(1.0 + time_z * 0.35, 0.0, 2.0)
        debug[horse.number].append(
            f"time_per_100m={avg_per_100m:.4f},mean={mean_per_100m:.4f},std={std_per_100m}"
        )
        results[horse.number] = TimeFeatureResult(
            raw_time=avg_time,
            time_index=time_index,
            time_z=time_z,
            used_runs=used[horse.number],
            debug=debug[horse.number],
        )
    return results


def _distance_bucket(distance_m: int) -> int:
    buckets = [1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600]
    return min(buckets, key=lambda value: abs(value - distance_m))


def _mean_std(values: List[float]) -> Tuple[float, float | None]:
    if not values:
        return 0.0, None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5 if variance > 0 else None
    return mean, std


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
