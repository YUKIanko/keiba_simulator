from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import json

from ..models import HorseData, PastRun

SCHEMA_VERSION = "canonical_v0.1"


def build_table(race_name: str, horses: List[HorseData]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for horse in horses:
        if not horse.past_runs:
            rows.append(_base_row(race_name, horse, None))
            continue
        for run in horse.past_runs:
            rows.append(_base_row(race_name, horse, run))
    return rows


def build_invalid_table(race_name: str, horses: List[HorseData]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for horse in horses:
        for run in horse.dropped_runs:
            rows.append(_base_row(race_name, horse, run))
    return rows


def save_table(output_dir: Path, race_name: str, rows: List[Dict[str, object]]) -> None:
    safe_name = race_name.replace(" ", "_")
    jsonl_path = output_dir / f"{safe_name}_canonical.jsonl"
    csv_path = output_dir / f"{safe_name}_canonical.csv"

    jsonl_lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    jsonl_path.write_text("\n".join(jsonl_lines), encoding="utf-8")

    if not rows:
        return
    header = list(rows[0].keys())
    csv_lines = [",".join(header)]
    for row in rows:
        csv_lines.append(",".join(_escape_csv(row.get(key)) for key in header))
    csv_path.write_text("\n".join(csv_lines), encoding="utf-8")


def save_invalid_table(output_dir: Path, race_name: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    safe_name = race_name.replace(" ", "_")
    jsonl_path = output_dir / f"{safe_name}_canonical_invalid.jsonl"
    jsonl_lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    jsonl_path.write_text("\n".join(jsonl_lines), encoding="utf-8")


def _base_row(race_name: str, horse: HorseData, run: PastRun | None) -> Dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "race_name": race_name,
        "horse_no": horse.number,
        "horse_name": horse.name,
        "pt1": run.pt1 if run else None,
        "pt2": run.pt2 if run else None,
        "pt3": run.pt3 if run else None,
        "last3F": run.last3f if run else None,
        "time_sec": run.time_sec if run else None,
        "surface": run.surface if run else None,
        "distance_m": run.distance_m if run else None,
        "track": run.track if run else None,
        "raw_text": run.raw_text if run else None,
        "tokens_before": run.tokens_before if run else None,
        "tokens_after": run.tokens_after if run else None,
        "issues": run.issues if run else None,
        "evidence_id": run.evidence_id if run else None,
    }


def _escape_csv(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if "," in text or "\"" in text:
        text = text.replace("\"", "\"\"")
        return f"\"{text}\""
    return text
