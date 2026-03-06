from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import HorseData


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    value: float
    source: str
    evidence: List[str]


def compute_win_score(
    horse: HorseData,
    course_key: Dict[str, float],
) -> Dict[str, object]:
    components = []
    raw_snippet = horse.past_runs[0].raw_text[:80] if horse.past_runs else "past_runs=0"

    base_class = _clamp(1.0 + 0.2 * min(len(horse.past_runs), 5))
    components.append(
        ScoreComponent(
            name="BaseClass",
            value=base_class,
            source="derived",
            evidence=[raw_snippet],
        )
    )

    form = _clamp(1.0 + (horse.rel_last3f or 0.0) * 0.2)
    components.append(
        ScoreComponent(
            name="Form",
            value=form,
            source="derived",
            evidence=[f"rel_last3f={horse.rel_last3f}"],
        )
    )

    pace_fit = 1.0
    if horse.style in {"逃", "先"}:
        pace_fit = 1.1
    elif horse.style == "追":
        pace_fit = 0.95
    components.append(
        ScoreComponent(
            name="PaceFit",
            value=_clamp(pace_fit),
            source="rule",
            evidence=[f"style={horse.style}"],
        )
    )

    lane_fit = _clamp(1.0 + (course_key.get("StraightOpportunity", 0.5) - 0.5) * 0.4)
    components.append(
        ScoreComponent(
            name="LaneFit",
            value=lane_fit,
            source="db",
            evidence=[f"StraightOpportunity={course_key.get('StraightOpportunity')}"]
        )
    )

    traffic_risk = _clamp(1.0 - (course_key.get("LaneChangeDifficulty", 0.5) - 0.5) * 0.4)
    components.append(
        ScoreComponent(
            name="TrafficRisk",
            value=traffic_risk,
            source="db",
            evidence=[f"LaneChangeDifficulty={course_key.get('LaneChangeDifficulty')}"]
        )
    )

    moveability = _clamp(horse.scores.moveability / 2 if horse.scores else 1.0)
    components.append(
        ScoreComponent(
            name="Moveability",
            value=moveability,
            source="derived",
            evidence=[f"moveability_score={horse.scores.moveability}"]
        )
    )

    kick_stamina = _clamp((horse.scores.kick + horse.scores.stamina) / 4)
    components.append(
        ScoreComponent(
            name="KickStaminaBalance",
            value=kick_stamina,
            source="derived",
            evidence=[f"kick={horse.scores.kick}", f"stamina={horse.scores.stamina}"]
        )
    )

    total = sum(component.value for component in components)

    return {
        "total": total,
        "components": components,
    }


def _clamp(value: float, low: float = 0.0, high: float = 2.0) -> float:
    return max(low, min(high, value))
