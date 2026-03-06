import json
from pathlib import Path

from keiba_simulator.score.weights import default_score_weights, load_score_weights


def test_default_score_weights_has_known_component() -> None:
    weights = default_score_weights()
    assert weights.component("BaseClass") == 1.0
    assert weights.component("UnknownKey", 0.3) == 0.3


def test_load_score_weights_overrides_values(tmp_path: Path) -> None:
    config = {"component_weights": {"Form": 1.25, "TimeIndex": 1.4}}
    path = tmp_path / "weights.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    weights = load_score_weights(path)
    assert weights.component("Form") == 1.25
    assert weights.component("TimeIndex") == 1.4
    assert weights.component("BaseClass") == 1.0
