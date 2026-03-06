from __future__ import annotations

from pathlib import Path
from typing import List

from .course import TrackCourse
from .models import HorseData, Worldline
from .models import RaceInfo
from .worldline_llm import infer_after_initial_worldlines_with_llm


def generate_worldlines(
    horses: List[HorseData],
    race_info: RaceInfo,
    course: TrackCourse | None,
    llm_config: Path | None = None,
) -> List[Worldline]:
    # Initial positioning remains a deterministic estimate from lap-rank-derived style.
    initial_front_count = sum(1 for horse in horses if horse.style in {"逃", "先"})
    if llm_config and llm_config.exists():
        inferred = infer_after_initial_worldlines_with_llm(race_info, horses, course, llm_config)
        parsed = _parse_llm_worldlines(inferred, horses, initial_front_count)
        if parsed:
            return parsed
    return _fallback_worldlines(horses, race_info.course_key, initial_front_count)


def _fallback_worldlines(
    horses: List[HorseData], course_key: dict[str, float], initial_front_count: int
) -> List[Worldline]:
    front_count = sum(1 for horse in horses if horse.style in {"逃", "先"})
    uphill = course_key.get("UphillTag", 0.0)
    base = 0.3 + (front_count / max(len(horses), 1)) * 0.4
    weights = {
        "Fast": min(0.6, base + 0.1 * uphill),
        "Standard": 0.3,
        "Slow": max(0.1, 1 - base - 0.3),
        "Split": 0.2 if front_count >= 4 else 0.1,
    }
    total = sum(weights.values())
    worldlines: List[Worldline] = []
    for pace, weight in weights.items():
        probability = weight / total if total else 0.25
        shape = "String" if pace in {"Fast", "Split"} else "Compact"
        traffic_mode = "InsideHeavy" if course_key.get("LaneChangeDifficulty", 0.5) > 0.6 else "Neutral"
        reason = [
            f"front_count={front_count}",
            f"initial_front_count={initial_front_count}",
            f"uphill={uphill}",
            f"lane_change={course_key.get('LaneChangeDifficulty')}",
        ]
        worldlines.append(
            Worldline(
                pace_scenario=pace,
                shape=shape,
                secondary_press=pace in {"Fast", "Split"},
                traffic_mode=traffic_mode,
                outside_sweep=pace in {"Fast", "Split"},
                probability=round(probability, 4),
                reason=reason,
                horse_dynamics={},
            )
        )
    return worldlines


def _parse_llm_worldlines(
    payload: dict[str, object] | None,
    horses: List[HorseData],
    initial_front_count: int,
) -> List[Worldline]:
    if not payload:
        return []
    rows = payload.get("worldlines")
    if not isinstance(rows, list) or not rows:
        return []

    horse_numbers = {horse.number for horse in horses}
    worldlines: List[Worldline] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        probability = _to_float(row.get("probability"), 0.0)
        reason = row.get("reason", [])
        reasons = [str(item) for item in reason] if isinstance(reason, list) else []
        reasons.append(f"initial_front_count={initial_front_count}")
        worldlines.append(
            Worldline(
                pace_scenario=str(row.get("pace_scenario", "Standard")),
                shape=str(row.get("shape", "Compact")),
                secondary_press=bool(row.get("secondary_press", False)),
                traffic_mode=str(row.get("traffic_mode", "Neutral")),
                outside_sweep=bool(row.get("outside_sweep", False)),
                probability=probability,
                reason=reasons,
                horse_dynamics=_parse_horse_dynamics(row.get("horse_dynamics"), horse_numbers),
            )
        )
    return _normalize_worldline_probs(worldlines)


def _parse_horse_dynamics(raw: object, horse_numbers: set[int]) -> dict[int, dict[str, float]]:
    if not isinstance(raw, list):
        return {}
    parsed: dict[int, dict[str, float]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        horse_no = _to_int(row.get("horse_no"))
        if horse_no is None or horse_no not in horse_numbers:
            continue
        parsed[horse_no] = {
            "mid_gain": _clamp(_to_float(row.get("mid_gain"), 0.0), -0.5, 0.5),
            "late_gain": _clamp(_to_float(row.get("late_gain"), 0.0), -0.5, 0.5),
            "traffic_risk_adj": _clamp(_to_float(row.get("traffic_risk_adj"), 0.0), -0.2, 0.2),
            "wide_risk_adj": _clamp(_to_float(row.get("wide_risk_adj"), 0.0), -0.2, 0.2),
        }
    return parsed


def _normalize_worldline_probs(worldlines: List[Worldline]) -> List[Worldline]:
    if not worldlines:
        return []
    total = sum(max(0.0, worldline.probability) for worldline in worldlines)
    if total <= 0.0:
        uniform = round(1.0 / len(worldlines), 4)
        return [Worldline(**{**worldline.__dict__, "probability": uniform}) for worldline in worldlines]
    normalized = []
    for worldline in worldlines:
        prob = round(max(0.0, worldline.probability) / total, 4)
        normalized.append(Worldline(**{**worldline.__dict__, "probability": prob}))
    return normalized


def _to_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
