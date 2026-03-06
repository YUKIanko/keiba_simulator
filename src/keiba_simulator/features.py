from __future__ import annotations

from typing import List

from .models import HorseData, HorseScores


def apply_basic_features(horses: List[HorseData]) -> None:
    for horse in horses:
        horse.style = _infer_style(horse)
        horse.scores = _score_components(horse, horses)


def _infer_style(horse: HorseData) -> str:
    if not horse.lap_ranks:
        return horse.style or "unknown"
    first_rank = horse.lap_ranks[0]
    if first_rank <= 2:
        return "逃"
    if first_rank <= 4:
        return "先"
    if first_rank <= 6:
        return "差"
    return "追"


def _rank_value(values: List[float | None], target: float | None) -> float | None:
    clean = [value for value in values if value is not None]
    if target is None or not clean:
        return None
    ordered = sorted(clean)
    return ordered.index(target) + 1


def _score_components(horse: HorseData, horses: List[HorseData]) -> HorseScores:
    field_size = max(1, len(horses))
    pace_rank_rank = _rank_value([h.pace_rank for h in horses], horse.pace_rank)
    last3f_rank = _rank_value([h.last3f_avg for h in horses], horse.last3f_avg)
    delta_rank = horse.delta_rank or 0.0

    cruise = _clamp_score(1 - abs(delta_rank) / max(1.0, field_size / 2))
    kick = _rank_score(last3f_rank, field_size)
    stamina = _clamp_score(0.6 + 0.2 * min(len(horse.past_runs), 5))
    turn = _rank_score(pace_rank_rank, field_size)
    start_skill = _start_skill_score(horse)
    moveability = _clamp_score(1 + (delta_rank / max(1.0, field_size)))
    traffic_resist = _clamp_score(1.5 * (1 - horse.uncertainty))

    return HorseScores(
        cruise=cruise,
        kick=kick,
        stamina=stamina,
        turn=turn,
        start_skill=start_skill,
        moveability=moveability,
        traffic_resist=traffic_resist,
    )


def _rank_score(rank: float | None, field_size: int) -> float:
    if rank is None:
        return 1.0
    return _clamp_score(2 - ((rank - 1) / max(1, field_size - 1)) * 2)


def _start_skill_score(horse: HorseData) -> float:
    if not horse.lap_ranks:
        return 1.0
    first_rank = horse.lap_ranks[0]
    if first_rank <= 2:
        return 2.0
    if first_rank <= 4:
        return 1.5
    if first_rank <= 6:
        return 1.0
    return 0.7


def _clamp_score(value: float) -> float:
    return max(0.0, min(2.0, value))
