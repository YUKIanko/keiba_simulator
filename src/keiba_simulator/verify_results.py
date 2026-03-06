from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .pdf_ingest import extract_text

FILE_RACE_NO_RE = re.compile(r"(\d{1,2})\s*レース")
HEADER_RACE_NO_RE = re.compile(r"(?:^|\s)(\d{1,2})R(?:\s|$)")
RESULT_ROW_RE = re.compile(r"^\s*(\d{1,2})\s+\d+\s+(\d{1,2})\s+([^\s]+).*\s(\d{1,2})\s*$")


@dataclass(frozen=True)
class ActualHorseResult:
    finish: int
    horse_no: int
    horse_name: str
    popularity: int


def parse_results_text(text: str) -> List[ActualHorseResult]:
    rows: List[ActualHorseResult] = []
    for line in text.splitlines():
        match = RESULT_ROW_RE.match(line)
        if not match:
            continue
        rows.append(
            ActualHorseResult(
                finish=int(match.group(1)),
                horse_no=int(match.group(2)),
                horse_name=match.group(3),
                popularity=int(match.group(4)),
            )
        )
    rows.sort(key=lambda row: row.finish)
    return rows


def extract_race_number(text: str, fallback_name: str) -> int | None:
    from_name = FILE_RACE_NO_RE.search(fallback_name)
    if from_name:
        return int(from_name.group(1))

    header_lines = "\n".join(text.splitlines()[:20])
    match = HEADER_RACE_NO_RE.search(header_lines)
    if match:
        return int(match.group(1))
    return None


def load_actual_results(results_dir: Path) -> Dict[int, Dict[str, object]]:
    actual_by_race: Dict[int, Dict[str, object]] = {}
    for file_path in sorted(results_dir.iterdir()):
        if not file_path.is_file():
            continue
        if "レース" not in file_path.name:
            continue
        ingest = extract_text(file_path)
        race_no = extract_race_number(ingest.text, file_path.stem)
        if race_no is None:
            continue
        rows = parse_results_text(ingest.text)
        actual_by_race[race_no] = {
            "source": str(file_path),
            "warnings": ingest.warnings,
            "results": [
                {
                    "finish": row.finish,
                    "horse_no": row.horse_no,
                    "horse_name": row.horse_name,
                    "popularity": row.popularity,
                }
                for row in rows
            ],
        }
    return actual_by_race


def _unwrap(value: object) -> object:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _extract_race_no_from_sim_json(data: Dict[str, object], file_name: str) -> int | None:
    race_name = _unwrap(data.get("RaceName", {}))
    if isinstance(race_name, str):
        match = re.search(r"(\d{1,2})レース", race_name)
        if match:
            return int(match.group(1))
    match = re.search(r"(\d{1,2})レース", file_name)
    if match:
        return int(match.group(1))
    return None


def load_sim_results(sim_dir: Path) -> Dict[int, Dict[str, object]]:
    sim_by_race: Dict[int, Dict[str, object]] = {}
    for file_path in sorted(sim_dir.glob("*.json")):
        if file_path.name == "summary.json":
            continue
        if "_canonical" in file_path.name:
            continue
        data = json.loads(file_path.read_text(encoding="utf-8"))
        race_no = _extract_race_no_from_sim_json(data, file_path.name)
        if race_no is None:
            continue
        sim_by_race[race_no] = {"source": str(file_path), "data": data}
    return sim_by_race


def compare_results(
    actual_by_race: Dict[int, Dict[str, object]],
    sim_by_race: Dict[int, Dict[str, object]],
) -> Dict[str, object]:
    races: List[Dict[str, object]] = []
    for race_no in sorted(actual_by_race):
        actual_results = actual_by_race[race_no]["results"]
        if not actual_results:
            races.append({"race_no": race_no, "status": "no_actual_rows"})
            continue

        sim_entry = sim_by_race.get(race_no)
        if sim_entry is None:
            races.append({"race_no": race_no, "status": "sim_not_found"})
            continue

        sim_data = sim_entry["data"]
        probabilities = [_convert_prob_item(item) for item in sim_data.get("Probabilities", [])]
        probabilities.sort(key=lambda item: item["p_win"], reverse=True)
        rank_map = {item["horse_no"]: index + 1 for index, item in enumerate(probabilities)}
        marks = _extract_marks(sim_data)

        winner = min(actual_results, key=lambda row: row["finish"])
        actual_top3 = [row["horse_no"] for row in sorted(actual_results, key=lambda row: row["finish"])[:3]]
        pred_top3 = [item["horse_no"] for item in probabilities[:3]]
        top3_overlap = sorted(set(actual_top3) & set(pred_top3))

        races.append(
            {
                "race_no": race_no,
                "status": "ok",
                "actual_source": actual_by_race[race_no]["source"],
                "sim_source": sim_entry["source"],
                "winner_no": winner["horse_no"],
                "winner_name": winner["horse_name"],
                "winner_pred_rank": rank_map.get(winner["horse_no"]),
                "winner_mark": marks.get(winner["horse_no"], ""),
                "pred_top1_no": probabilities[0]["horse_no"] if probabilities else None,
                "hit_top1": bool(probabilities and probabilities[0]["horse_no"] == winner["horse_no"]),
                "winner_in_pred_top3": winner["horse_no"] in pred_top3,
                "actual_top3": actual_top3,
                "pred_top3": pred_top3,
                "top3_overlap": top3_overlap,
                "top3_overlap_count": len(top3_overlap),
            }
        )

    ok_races = [race for race in races if race["status"] == "ok"]
    summary = {
        "total_races": len(races),
        "ok_races": len(ok_races),
        "top1_hits": sum(1 for race in ok_races if race["hit_top1"]),
        "winner_in_top3_hits": sum(1 for race in ok_races if race["winner_in_pred_top3"]),
        "avg_top3_overlap": (
            round(sum(race["top3_overlap_count"] for race in ok_races) / len(ok_races), 3)
            if ok_races
            else 0.0
        ),
    }
    return {"summary": summary, "races": races}


def _convert_prob_item(item: Dict[str, object]) -> Dict[str, object]:
    return {
        "horse_no": int(_unwrap(item.get("number", 0)) or 0),
        "horse_name": str(_unwrap(item.get("name", "")) or ""),
        "p_win": float(_unwrap(item.get("p_win", 0.0)) or 0.0),
    }


def _extract_marks(sim_data: Dict[str, object]) -> Dict[int, str]:
    marks: Dict[int, str] = {}
    for item in sim_data.get("FinalMarks", []):
        horse_no = int(_unwrap(item.get("No", 0)) or 0)
        mark = str(_unwrap(item.get("Mark", "")) or "")
        marks[horse_no] = mark
    return marks


def _write_json(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract race result PDFs and compare to simulation outputs.")
    parser.add_argument("--results-dir", type=Path, default=Path("race_results"))
    parser.add_argument("--sim-dir", type=Path, default=Path("output/latest_run"))
    parser.add_argument("--actual-output", type=Path, default=Path("output/latest_run/actual_results.json"))
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("output/latest_run/verification_report.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    actual_by_race = load_actual_results(args.results_dir)
    sim_by_race = load_sim_results(args.sim_dir)
    report = compare_results(actual_by_race, sim_by_race)

    _write_json(args.actual_output, {"races": actual_by_race})
    _write_json(args.report_output, report)

    summary = report["summary"]
    print(
        "verification:",
        f"total={summary['total_races']}",
        f"ok={summary['ok_races']}",
        f"top1_hits={summary['top1_hits']}",
        f"winner_in_top3_hits={summary['winner_in_top3_hits']}",
        f"avg_top3_overlap={summary['avg_top3_overlap']}",
    )
    print(f"actual_output={args.actual_output}")
    print(f"report_output={args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
