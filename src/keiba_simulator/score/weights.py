from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


DEFAULT_COMPONENT_WEIGHTS: Dict[str, float] = {
    "BaseClass": 1.0,
    "Form": 1.0,
    "PaceFit": 0.8,
    "PaceRankScore": 0.8,
    "LaneFit": 0.6,
    "TrafficRisk": 0.6,
    "Moveability": 0.6,
    "KickStaminaBalance": 0.6,
    "TimeIndex": 0.8,
    "StyleTimeFit": 0.9,
}


@dataclass(frozen=True)
class ScoreWeights:
    component_weights: Dict[str, float]

    def component(self, name: str, default: float = 1.0) -> float:
        return float(self.component_weights.get(name, default))


def default_score_weights() -> ScoreWeights:
    return ScoreWeights(component_weights=dict(DEFAULT_COMPONENT_WEIGHTS))


def load_score_weights(path: Path | None) -> ScoreWeights:
    if path is None or not path.exists():
        return default_score_weights()
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_weights = payload.get("component_weights", {})
    if not isinstance(raw_weights, dict):
        return default_score_weights()
    merged = dict(DEFAULT_COMPONENT_WEIGHTS)
    for key, value in raw_weights.items():
        try:
            merged[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return ScoreWeights(component_weights=merged)
