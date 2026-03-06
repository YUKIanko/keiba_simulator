from __future__ import annotations

from typing import Dict, List, Tuple

from ..models import HorseData


def judge_lap_type(horses: List[HorseData]) -> Dict[int, Dict[str, object]]:
    evidence: Dict[int, Dict[str, object]] = {}
    pace_ranks = [horse.pace_rank for horse in horses if horse.pace_rank is not None]
    last3f_ranks = [horse.last3f_avg for horse in horses if horse.last3f_avg is not None]
    for horse in horses:
        lap_type, reason = _judge_one(horse, pace_ranks, last3f_ranks)
        horse.lap_type = lap_type
        evidence[horse.number] = {
            "lap_type": lap_type,
            "reason": reason,
        }
    return evidence


def _judge_one(
    horse: HorseData,
    pace_ranks: List[float],
    last3f_ranks: List[float],
) -> Tuple[str, List[str]]:
    reason = [
        f"pace_rank={horse.pace_rank}",
        f"last3f_avg={horse.last3f_avg}",
        f"style={horse.style}",
    ]
    if horse.pace_rank is None or horse.last3f_avg is None:
        return _fallback(horse), reason + ["fallback"]

    if horse.style in {"逃", "先"} and horse.pace_rank <= _percentile(pace_ranks, 0.4):
        return "A", reason
    if horse.style in {"差", "追"} and horse.last3f_avg <= _percentile(last3f_ranks, 0.4):
        return "B", reason
    return "C", reason


def _fallback(horse: HorseData) -> str:
    if horse.style in {"逃", "先"}:
        return "A"
    if horse.style == "差":
        return "B"
    return "C"


def _percentile(values: List[float], ratio: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int(max(0, min(len(values) - 1, len(values) * ratio)))
    return values[idx]
