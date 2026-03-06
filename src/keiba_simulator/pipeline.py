from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .course import derive_course_key, find_course, load_trackdata
from .models import HorseData, PastRun
from .features import apply_basic_features
from .canonical.build_table import build_invalid_table, build_table, save_invalid_table, save_table
from .debug.report import write_report
from .deep_parse.extract_runs import extract_runs
from .deep_parse.llm_check import check_runs_with_llm
from .deep_parse.validate_run import validate_run
from .lap_type.compute_proxies import compute_proxies
from .lap_type.judge import judge_lap_type
from .output import build_output
from .parse import parse_races
from .pdf_ingest import extract_text
from .score.build_breakdown import build_breakdown
from .score.weights import load_score_weights
from .sim import simulate_race
from .time_features import compute_time_features
from .worldline import generate_worldlines


def run_pipeline(
    pdf_path: Path,
    output_dir: Path,
    trackdata_path: Path | None = None,
    llm_check_config: Path | None = None,
    score_weights_path: Path | None = None,
) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    score_weights = load_score_weights(score_weights_path)

    courses = []
    if trackdata_path and trackdata_path.exists():
        courses = load_trackdata(trackdata_path)

    ingest_result = extract_text(pdf_path)
    parse_result = parse_races(ingest_result.text, pdf_path)

    race_outputs: List[Dict[str, object]] = []
    for race_info, horses in parse_result.races:
        course = find_course(courses, race_info.track, race_info.surface, race_info.layout)
        course_key = derive_course_key(course)
        race_info = race_info.__class__(
            race_name=race_info.race_name,
            track=race_info.track,
            surface=race_info.surface,
            distance_m=race_info.distance_m,
            direction=race_info.direction,
            layout=race_info.layout,
            surface_distance_course=race_info.surface_distance_course,
            field_size=race_info.field_size,
            am_water_percent=race_info.am_water_percent,
            init_bias=race_info.init_bias,
            course_key=course_key,
        )
        runs_by_horse = extract_runs(ingest_result.text, horses)
        if llm_check_config and llm_check_config.exists():
            llm_results = check_runs_with_llm(ingest_result.text, horses, runs_by_horse, llm_check_config)
            _apply_llm_check(horses, runs_by_horse, llm_results)
        _apply_runs(horses, runs_by_horse)
        _validate_runs(horses)
        _apply_proxies(horses)
        apply_basic_features(horses)
        lap_evidence = judge_lap_type(horses)
        _apply_time_features(horses, race_info)
        worldlines = generate_worldlines(horses, race_info, course, llm_check_config)
        win_scores = {
            horse.number: build_breakdown(horse, course_key, score_weights) for horse in horses
        }
        results, _ = simulate_race(horses, worldlines, win_scores)
        request_list = _build_request_list(horses)
        canonical_rows = build_table(race_info.race_name, horses)
        save_table(output_dir, race_info.race_name, canonical_rows)
        invalid_rows = build_invalid_table(race_info.race_name, horses)
        save_invalid_table(output_dir, race_info.race_name, invalid_rows)
        write_report(output_dir, race_info.race_name, horses)

        race_output = build_output(
            race_info=race_info,
            horses=horses,
            worldlines=worldlines,
            results=results,
            win_scores=win_scores,
            request_list=request_list,
            canonical_rows=canonical_rows,
            lap_evidence=lap_evidence,
        )
        race_outputs.append(race_output)

        race_file = output_dir / f"{race_info.race_name.replace(' ', '_')}.json"
        race_file.write_text(_to_json(race_output), encoding="utf-8")

    summary = {
        "Source": str(pdf_path),
        "Warnings": ingest_result.warnings + parse_result.warnings,
        "Races": race_outputs,
    }
    (output_dir / "summary.json").write_text(_to_json(summary), encoding="utf-8")
    return summary


def _to_json(data: Dict[str, object]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_request_list(horses: List[HorseData]) -> List[str]:
    requests: List[str] = []
    for horse in horses:
        if horse.name.startswith("Unknown-"):
            requests.append(f"MissingName(No.{horse.number})")
        if not horse.past_runs:
            requests.append(f"MissingPastRuns(No.{horse.number})")
            continue
        for run in horse.past_runs:
            if run.pt1 is None or run.pt2 is None or run.pt3 is None:
                requests.append(f"MissingLap(No.{horse.number})")
            if run.issues:
                requests.append(f"ParseIssue(No.{horse.number})")
            if run.last3f is None:
                requests.append(f"MissingLast3F(No.{horse.number})")
            if run.pt1 and (run.pt1 < 1 or run.pt1 > 18):
                requests.append(f"OutOfRangeLap(No.{horse.number})")
            if run.last3f and (run.last3f < 30 or run.last3f > 60):
                requests.append(f"OutOfRangeLast3F(No.{horse.number})")
        if not horse.used_runs:
            requests.append(f"MissingTimeFeature(No.{horse.number})")
        for run in horse.dropped_runs:
            requests.append(f"DroppedRun(No.{horse.number},evidence={run.evidence_id})")
        for issue in horse.notes_evidence:
            requests.append(f"ParseNote(No.{horse.number})")
    return sorted(set(requests))


def _apply_runs(horses: List[HorseData], runs_by_horse: Dict[int, List[PastRun]]) -> None:
    for horse in horses:
        runs = runs_by_horse.get(horse.number, [])
        horse.past_runs = runs


def _apply_llm_check(
    horses: List[HorseData],
    runs_by_horse: Dict[int, List[PastRun]],
    results: Dict[int, object],
) -> None:
    for horse in horses:
        result = results.get(horse.number)
        if result is None:
            continue
        expected_runs = getattr(result, "expected_runs", None)
        if expected_runs is not None and expected_runs > len(runs_by_horse.get(horse.number, [])):
            horse.notes_evidence.append(f"LLMExpectedRuns:{expected_runs}")
        for issue in getattr(result, "issues", []):
            reason = getattr(issue, "reason", "LLMCheck")
            horse.notes_evidence.append(f"LLMCheck:{reason}")
            if not getattr(issue, "drop_run", False):
                continue
            run_index = getattr(issue, "run_index", None)
            if run_index is None:
                continue
            runs = runs_by_horse.get(horse.number, [])
            idx = run_index - 1
            if idx < 0 or idx >= len(runs):
                continue
            runs[idx] = _merge_issues(runs[idx], [f"LLMInvalid:{reason}"])
            runs_by_horse[horse.number] = runs


def _validate_runs(horses: List[HorseData]) -> None:
    for horse in horses:
        validated = []
        issues = []
        dropped = []
        for run in horse.past_runs:
            valid, run_issues = validate_run(run)
            if valid:
                validated.append(valid)
            else:
                issues.extend(run_issues)
                dropped.append(_merge_issues(run, run_issues))
        horse.past_runs = validated
        horse.dropped_runs = dropped
        if issues:
            horse.notes_evidence.extend(issues)


def _apply_proxies(horses: List[HorseData]) -> None:
    proxies = compute_proxies(horses)
    for horse in horses:
        proxy = proxies.get(horse.number, {})
        horse.pace_rank = proxy.get("pace_rank")
        horse.last3f_avg = proxy.get("last3f_avg")
        horse.delta_rank = proxy.get("delta_rank")
        horse.rel_last3f = proxy.get("rel_last3f")


def _apply_time_features(horses: List[HorseData], race_info: RaceInfo) -> None:
    results = compute_time_features(
        horses,
        surface=race_info.surface,
        distance_m=race_info.distance_m,
        track_group=race_info.track,
    )
    for horse in horses:
        feature = results.get(horse.number)
        if feature is None:
            continue
        horse.raw_time = feature.raw_time
        horse.time_index = feature.time_index
        horse.time_z = feature.time_z
        horse.used_runs = feature.used_runs
        horse.time_features_debug = feature.debug


def _merge_issues(run: PastRun, new_issues: List[str]) -> PastRun:
    return PastRun(
        pt1=run.pt1,
        pt2=run.pt2,
        pt3=run.pt3,
        last3f=run.last3f,
        time_sec=run.time_sec,
        surface=run.surface,
        distance_m=run.distance_m,
        track=run.track,
        raw_text=run.raw_text,
        tokens_before=run.tokens_before,
        tokens_after=run.tokens_after,
        issues=run.issues + new_issues,
        evidence_id=run.evidence_id,
    )
