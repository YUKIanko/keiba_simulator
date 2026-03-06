import json
from pathlib import Path

from keiba_simulator.models import HorseData, HorseScores, RaceInfo, Worldline
from keiba_simulator.sim import simulate_race
from keiba_simulator.worldline import generate_worldlines
from keiba_simulator.worldline_llm import _build_payload


def _horse(number: int, name: str, style: str) -> HorseData:
    return HorseData(
        number=number,
        name=name,
        style=style,
        lap_type="C",
        scores=HorseScores(cruise=1.0, kick=1.0, stamina=1.0, turn=1.0, start_skill=1.0, moveability=1.0, traffic_resist=1.0),
        uncertainty=0.5,
        lap_ranks=[1 if style in {"逃", "先"} else 8],
    )


def _race_info() -> RaceInfo:
    return RaceInfo(
        race_name="Race 1",
        track="中山",
        surface="dirt",
        distance_m=1200,
        direction="R",
        layout="main",
        surface_distance_course="ダ1200m 右",
        field_size=2,
        am_water_percent=None,
        init_bias=None,
        course_key={
            "CornerSeverity": 0.7,
            "LaneChangeDifficulty": 0.6,
            "StraightOpportunity": 0.3,
            "UphillTag": 1.0,
        },
    )


def test_worldline_llm_payload_contains_course_context_fields() -> None:
    race = _race_info()
    horses = [_horse(1, "A", "逃")]
    config = {"model": "dummy", "max_tokens": 256}
    payload = _build_payload(race, horses, None, config)
    content = payload["messages"][1]["content"]
    start = content.find("course_context=") + len("course_context=")
    end = content.find("\ninitial_positions=")
    course_context = json.loads(content[start:end])
    assert set(course_context.keys()) == {
        "start_position",
        "corner_profile",
        "homestretch_m",
        "uphill_present",
    }


def test_generate_worldlines_uses_llm_structured_output(tmp_path: Path, monkeypatch) -> None:
    race = _race_info()
    horses = [_horse(1, "A", "逃"), _horse(2, "B", "差")]

    def _fake_infer(*args, **kwargs):
        return {
            "worldlines": [
                {
                    "pace_scenario": "Standard",
                    "shape": "Compact",
                    "secondary_press": False,
                    "traffic_mode": "Neutral",
                    "outside_sweep": False,
                    "probability": 1.0,
                    "reason": ["llm-branch"],
                    "horse_dynamics": [
                        {"horse_no": 1, "mid_gain": 0.2, "late_gain": 0.1, "traffic_risk_adj": -0.02, "wide_risk_adj": 0.0}
                    ],
                }
            ]
        }

    monkeypatch.setattr("keiba_simulator.worldline.infer_after_initial_worldlines_with_llm", _fake_infer)
    config_path = tmp_path / "llm.json"
    config_path.write_text('{"base_url":"http://127.0.0.1:1234","model":"x"}', encoding="utf-8")
    worldlines = generate_worldlines(horses, race, None, config_path)
    assert len(worldlines) == 1
    assert 1 in worldlines[0].horse_dynamics
    assert "initial_front_count=1" in worldlines[0].reason


def test_simulation_consumes_worldline_horse_dynamics() -> None:
    horses = [_horse(1, "A", "差"), _horse(2, "B", "差")]
    worldlines = [
        Worldline(
            pace_scenario="Standard",
            shape="Compact",
            secondary_press=False,
            traffic_mode="Neutral",
            outside_sweep=False,
            probability=1.0,
            reason=["test"],
            horse_dynamics={
                1: {"mid_gain": 0.5, "late_gain": 0.5, "traffic_risk_adj": -0.1, "wide_risk_adj": -0.1},
                2: {"mid_gain": -0.5, "late_gain": -0.5, "traffic_risk_adj": 0.1, "wide_risk_adj": 0.1},
            },
        )
    ]
    win_scores = {1: {"total": 1.0}, 2: {"total": 1.0}}
    results, _ = simulate_race(horses, worldlines, win_scores, samples=50)
    by_no = {item.number: item for item in results}
    assert by_no[1].p_win > by_no[2].p_win
