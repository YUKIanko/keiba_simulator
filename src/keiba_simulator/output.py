from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from .models import HorseData, RaceInfo, SimHorseResult, Worldline
from .scoring import ScoreComponent


def build_output(
    race_info: RaceInfo,
    horses: List[HorseData],
    worldlines: List[Worldline],
    results: List[SimHorseResult],
    win_scores: Dict[int, Dict[str, object]],
    request_list: List[str],
    canonical_rows: List[Dict[str, object]],
    lap_evidence: Dict[int, Dict[str, object]],
) -> Dict[str, object]:
    win_gate = _select_win_gate(results)
    place_gate = _select_place_gate(results)
    final_marks = _build_final_marks(horses, results, win_gate, place_gate)

    scenario_comment = _scenario_comment(worldlines)
    short_memo = _short_memo(worldlines)
    devil_speak = _devil_speak(worldlines)

    return {
        "RaceName": _wrap(race_info.race_name, "pdf"),
        "SurfaceDistanceCourse": _wrap(race_info.surface_distance_course, "pdf"),
        "CourseMeta": _wrap(
            {
                "Track": _wrap(race_info.track, "pdf"),
                "Surface": _wrap(race_info.surface, "pdf"),
                "DistanceM": _wrap(race_info.distance_m, "pdf"),
                "Direction": _wrap(race_info.direction, "pdf"),
                "Layout": _wrap(race_info.layout, "pdf"),
                "CourseKey": _wrap(race_info.course_key, "db"),
            },
            "derived",
        ),
        "ScenarioComment": _wrap(scenario_comment, "derived"),
        "FinalMarks": final_marks,
        "BetTable": _wrap(_build_bet_table(win_gate, place_gate), "rule"),
        "DevilSpeak": _wrap(devil_speak, "derived"),
        "ShortMemo": _wrap(short_memo, "derived"),
        "Worldlines": [_wrap_worldline(worldline) for worldline in worldlines],
        "Probabilities": [_wrap_prob(result) for result in results],
        "WinScore": _wrap_win_scores(win_scores, horses),
        "TimeFeatures": _wrap_time_features(horses),
        "LapTypeEvidence": _wrap(lap_evidence, "derived"),
        "RequestList": [_wrap(value, "rule") for value in request_list],
        "CanonicalTable": _wrap(canonical_rows, "derived"),
    }


def _select_win_gate(results: List[SimHorseResult]) -> List[int]:
    ranked = sorted(results, key=lambda r: (-r.p_win, -r.p_in3))
    return [horse.number for horse in ranked[:2]]


def _select_place_gate(results: List[SimHorseResult]) -> List[int]:
    ranked = sorted(results, key=lambda r: (-r.p_in3, -r.p_win))
    return [horse.number for horse in ranked[:4]]


def _build_final_marks(
    horses: List[HorseData],
    results: List[SimHorseResult],
    win_gate: List[int],
    place_gate: List[int],
) -> List[Dict[str, object]]:
    result_map = {result.number: result for result in results}
    final_marks = []
    for horse in horses:
        result = result_map.get(horse.number)
        mark = ""
        if horse.number in win_gate:
            mark = "◎" if horse.number == win_gate[0] else "○"
        elif horse.number in place_gate:
            mark = "▲"
        final_marks.append(
            {
                "No": _wrap(horse.number, "pdf"),
                "Name": _wrap(horse.name, "pdf"),
                "Mark": _wrap(mark, "rule"),
                "LapType": _wrap(horse.lap_type, "derived"),
                "RawScore": _wrap(result.raw_score if result else 0.0, "derived"),
                "PWin": _wrap(result.p_win if result else 0.0, "derived"),
                "PIn3": _wrap(result.p_in3 if result else 0.0, "derived"),
                "TrafficFail": _wrap(result.traffic_fail if result else 0.0, "derived"),
                "WideCostFail": _wrap(result.wide_cost_fail if result else 0.0, "derived"),
            }
        )
    return final_marks


def _build_bet_table(win_gate: List[int], place_gate: List[int]) -> Dict[str, object]:
    return {
        "A": {"Focus": win_gate, "Amount": 100, "Tickets": len(win_gate)},
        "B": {"Focus": place_gate, "Amount": 100, "Tickets": len(place_gate)},
        "C": {"Focus": [], "Amount": 0, "Tickets": 0},
    }


def _scenario_comment(worldlines: List[Worldline]) -> str:
    if not worldlines:
        return "No scenario data."
    main = max(worldlines, key=lambda w: w.probability)
    return (
        f"Main scenario: {main.pace_scenario} pace, {main.shape} shape, "
        f"traffic {main.traffic_mode}."
    )


def _short_memo(worldlines: List[Worldline]) -> str:
    if not worldlines:
        return "No memo."
    main = max(worldlines, key=lambda w: w.probability)
    return f"Key: {main.pace_scenario} flow; adjust if pace shifts."


def _devil_speak(worldlines: List[Worldline]) -> str | None:
    if not worldlines:
        return None
    split = sum(1 for worldline in worldlines if worldline.probability < 0.25)
    if split >= 2:
        return "Worldlines are split; odds may swing on traffic and pace."
    return None


def _wrap(value: object, source: str) -> Dict[str, object]:
    return {"value": value, "source": source}


def _wrap_worldline(worldline: Worldline) -> Dict[str, object]:
    return {
        "pace_scenario": _wrap(worldline.pace_scenario, "rule"),
        "shape": _wrap(worldline.shape, "rule"),
        "secondary_press": _wrap(worldline.secondary_press, "rule"),
        "traffic_mode": _wrap(worldline.traffic_mode, "rule"),
        "outside_sweep": _wrap(worldline.outside_sweep, "rule"),
        "probability": _wrap(worldline.probability, "derived"),
        "horse_dynamics": _wrap(worldline.horse_dynamics, "llm"),
        "reason": _wrap(worldline.reason, "rule"),
    }


def _wrap_prob(result: SimHorseResult) -> Dict[str, object]:
    return {
        "number": _wrap(result.number, "pdf"),
        "name": _wrap(result.name, "pdf"),
        "raw_score": _wrap(result.raw_score, "derived"),
        "p_win": _wrap(result.p_win, "derived"),
        "p_in3": _wrap(result.p_in3, "derived"),
        "traffic_fail": _wrap(result.traffic_fail, "derived"),
        "wide_cost_fail": _wrap(result.wide_cost_fail, "derived"),
    }


def _wrap_win_scores(
    win_scores: Dict[int, Dict[str, object]], horses: List[HorseData]
) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    for horse in horses:
        data = win_scores[horse.number]
        components = []
        for component in data["components"]:
            components.append(
                {
                    "name": _wrap(component.name, component.source),
                    "value": _wrap(component.value, component.source),
                    "evidence": _wrap(component.evidence, "pdf"),
                }
            )
        items.append(
            {
                "No": _wrap(horse.number, "pdf"),
                "Name": _wrap(horse.name, "pdf"),
                "Total": _wrap(data["total"], "derived"),
                "Components": components,
            }
        )
    return items


def _wrap_time_features(horses: List[HorseData]) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    for horse in horses:
        items.append(
            {
                "No": _wrap(horse.number, "pdf"),
                "Name": _wrap(horse.name, "pdf"),
                "RawTime": _wrap(horse.raw_time, "derived"),
                "TimeIndex": _wrap(horse.time_index, "derived"),
                "TimeZ": _wrap(horse.time_z, "derived"),
                "UsedRuns": _wrap(horse.used_runs, "derived"),
                "TimeFeaturesDebug": _wrap(horse.time_features_debug, "derived"),
            }
        )
    return items
