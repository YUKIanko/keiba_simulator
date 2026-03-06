from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import HorseData, SimHorseResult, Worldline


@dataclass(frozen=True)
class WorldlineOutcome:
    worldline: Worldline
    ranked: List[HorseData]


def simulate_worldlines(horses: List[HorseData], worldlines: List[Worldline]) -> List[WorldlineOutcome]:
    outcomes: List[WorldlineOutcome] = []
    for worldline in worldlines:
        ranked = sorted(horses, key=lambda horse: -_strength(horse, worldline))
        outcomes.append(WorldlineOutcome(worldline=worldline, ranked=ranked))
    return outcomes


def simulate_race(
    horses: List[HorseData],
    worldlines: List[Worldline],
    win_scores: Dict[int, Dict[str, object]],
    samples: int = 300,
) -> Tuple[List[SimHorseResult], Dict[int, Dict[str, float]]]:
    totals = {horse.number: {"wins": 0, "in3": 0, "traffic": 0, "wide": 0} for horse in horses}
    total_samples = 0
    for worldline in worldlines:
        count = max(1, int(samples * worldline.probability))
        total_samples += count
        for _ in range(count):
            performance = _simulate_step(horses, worldline, win_scores, totals)
            top3 = sorted(performance.items(), key=lambda item: -item[1])[:3]
            for idx, (horse_id, _) in enumerate(top3):
                if idx == 0:
                    totals[horse_id]["wins"] += 1
                totals[horse_id]["in3"] += 1

    results = []
    for horse in horses:
        stats = totals[horse.number]
        score_total = win_scores[horse.number]["total"]
        results.append(
            SimHorseResult(
                number=horse.number,
                name=horse.name,
                raw_score=round(score_total, 4),
                p_win=round(stats["wins"] / total_samples, 4) if total_samples else 0.0,
                p_in3=round(stats["in3"] / total_samples, 4) if total_samples else 0.0,
                traffic_fail=round(stats["traffic"] / total_samples, 4) if total_samples else 0.0,
                wide_cost_fail=round(stats["wide"] / total_samples, 4) if total_samples else 0.0,
            )
        )
    return results, totals


def _strength(horse: HorseData, worldline: Worldline) -> float:
    base = 1.0 + horse.scores.total()
    if worldline.pace_scenario == "Fast" and horse.style in {"追", "差"}:
        base += 0.2
    if worldline.pace_scenario == "Slow" and horse.style in {"逃", "先"}:
        base += 0.2
    return base + _stable_noise(horse.name)


def _stable_noise(name: str) -> float:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return int(digest[:4], 16) / 65535 * 0.05


def _simulate_step(
    horses: List[HorseData],
    worldline: Worldline,
    win_scores: Dict[int, Dict[str, object]],
    totals: Dict[int, Dict[str, int]],
) -> Dict[int, float]:
    performance: Dict[int, float] = {}
    for horse in horses:
        base = win_scores[horse.number]["total"]
        dynamics = worldline.horse_dynamics.get(horse.number, {})
        pace_bonus = 0.2 if (worldline.pace_scenario == "Fast" and horse.style in {"差", "追"}) else 0.0
        pace_bonus += 0.2 if (worldline.pace_scenario == "Slow" and horse.style in {"逃", "先"}) else 0.0
        pace_bonus += _clamp((dynamics.get("mid_gain", 0.0) + dynamics.get("late_gain", 0.0)) * 0.2)
        traffic_risk = _traffic_risk(horse, worldline)
        wide_risk = _wide_risk(horse, worldline)
        traffic_risk = _clamp(traffic_risk + dynamics.get("traffic_risk_adj", 0.0))
        wide_risk = _clamp(wide_risk + dynamics.get("wide_risk_adj", 0.0))
        noise = _stable_noise(horse.name)
        penalty = 0.0
        if _sample_event(horse, traffic_risk):
            totals[horse.number]["traffic"] += 1
            penalty += 0.3
        if _sample_event(horse, wide_risk):
            totals[horse.number]["wide"] += 1
            penalty += 0.2
        performance[horse.number] = base + pace_bonus + noise - penalty
    return performance


def _traffic_risk(horse: HorseData, worldline: Worldline) -> float:
    base = 0.1 if worldline.traffic_mode != "Neutral" else 0.06
    style_adj = 0.04 if horse.style in {"差", "追"} else 0.0
    return _clamp(base + style_adj + _stable_noise(horse.name))


def _wide_risk(horse: HorseData, worldline: Worldline) -> float:
    base = 0.08 if worldline.outside_sweep else 0.04
    style_adj = 0.03 if horse.style in {"差", "追"} else 0.0
    return _clamp(base + style_adj + _stable_noise(horse.name) / 2)


def _sample_event(horse: HorseData, probability: float) -> bool:
    seed = int(hashlib.sha256(f"{horse.name}{probability}".encode("utf-8")).hexdigest()[:6], 16)
    value = (seed % 1000) / 1000
    return value < probability


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
