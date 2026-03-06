from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..models import HorseData
from .weights import ScoreWeights, default_score_weights


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    value: float
    source: str
    evidence: List[str]


def build_breakdown(
    horse: HorseData,
    course_key: Dict[str, float],
    weights: ScoreWeights | None = None,
) -> Dict[str, object]:
    score_weights = weights or default_score_weights()
    components: List[ScoreComponent] = []
    base = 1.0 + 0.2 * min(len(horse.past_runs), 5)
    components.append(_component("BaseClass", base, horse))

    form = 1.0 + (horse.rel_last3f or 0.0) * 0.2
    components.append(_component("Form", form, horse))

    pace_fit = 1.1 if horse.style in {"逃", "先"} else 0.95
    components.append(_component("PaceFit", pace_fit, horse, source="rule"))

    pace_rank_score = _pace_rank_score(horse.pace_rank)
    components.append(_component("PaceRankScore", pace_rank_score, horse))

    straight = course_key.get("StraightOpportunity", 0.5)
    lane_weight = 1.0 + (straight - 0.5) * 0.5
    lane_fit = (1.0 + (straight - 0.5) * 0.4) * lane_weight
    components.append(_component("LaneFit", lane_fit, horse, source="db"))

    lane_difficulty = course_key.get("LaneChangeDifficulty", 0.5)
    traffic_weight = 1.0 + (lane_difficulty - 0.5) * 0.5
    traffic = (1.0 - (lane_difficulty - 0.5) * 0.4) * traffic_weight
    components.append(_component("TrafficRisk", traffic, horse, source="db"))

    moveability = (horse.scores.moveability / 2) if horse.scores else 1.0
    components.append(_component("Moveability", moveability, horse))

    kick_stamina = (horse.scores.kick + horse.scores.stamina) / 4
    components.append(_component("KickStaminaBalance", kick_stamina, horse))

    if horse.time_index is not None:
        components.append(_component("TimeIndex", horse.time_index, horse))
    style_time_fit = _style_time_fit(horse.style, horse.time_z)
    components.append(_component("StyleTimeFit", style_time_fit, horse, source="rule"))

    total = _weighted_total(components, score_weights)
    return {"total": total, "components": components}


def _component(name: str, value: float, horse: HorseData, source: str = "derived") -> ScoreComponent:
    evidence = []
    if horse.past_runs:
        run = horse.past_runs[0]
        evidence = [run.raw_text[:80], f"tokens={run.tokens_after}", f"evidence_id={run.evidence_id}"]
    else:
        evidence = ["past_runs=0"]
    if horse.used_runs:
        evidence.append(f"used_runs={horse.used_runs}")
    return ScoreComponent(name=name, value=_clamp(value), source=source, evidence=evidence)


def _clamp(value: float, low: float = 0.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _pace_rank_score(pace_rank: float | None) -> float:
    if pace_rank is None:
        return 1.0
    if pace_rank <= 4:
        return 1.2
    if pace_rank <= 8:
        return 1.0
    return 0.8


def _style_time_fit(style: str, time_z: float | None) -> float:
    if time_z is None:
        return 1.0
    # Penalize clearly slow speed figures for forward styles, and reward
    # above-average figures for late runners that rely on sustained finish.
    if style in {"逃", "先"}:
        return _clamp(1.0 + time_z * 0.25)
    if style in {"差", "追"}:
        return _clamp(1.0 + time_z * 0.2)
    return _clamp(1.0 + time_z * 0.1)


def _weighted_total(components: List[ScoreComponent], weights: ScoreWeights) -> float:
    total = 0.0
    weight_sum = 0.0
    for component in components:
        weight = weights.component(component.name, 1.0)
        total += component.value * weight
        weight_sum += weight
    if weight_sum == 0.0:
        return 0.0
    return _clamp(total / weight_sum, high=2.0)
