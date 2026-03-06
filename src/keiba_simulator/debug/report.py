from __future__ import annotations

from pathlib import Path
from typing import List

from ..models import HorseData


def write_report(output_dir: Path, race_name: str, horses: List[HorseData]) -> None:
    safe_name = race_name.replace(" ", "_")
    report_path = output_dir / f"{safe_name}_debug_report.txt"
    lines: List[str] = []
    for horse in horses:
        lines.append(f"No.{horse.number} {horse.name}")
        if not horse.past_runs:
            lines.append("  past_runs: none")
        for run in horse.past_runs:
            lines.append(f"  raw: {run.raw_text}")
            lines.append(f"  tokens(before): {run.tokens_before}")
            lines.append(f"  tokens(after): {run.tokens_after}")
            lines.append(f"  pt1/pt2/pt3: {run.pt1}/{run.pt2}/{run.pt3}")
            lines.append(f"  last3F: {run.last3f}")
            lines.append(f"  issues: {','.join(run.issues) if run.issues else 'none'}")
        if horse.dropped_runs:
            lines.append("  dropped_runs:")
            for run in horse.dropped_runs:
                lines.append(f"    raw: {run.raw_text}")
                lines.append(f"    tokens(before): {run.tokens_before}")
                lines.append(f"    tokens(after): {run.tokens_after}")
                lines.append(f"    pt1/pt2/pt3: {run.pt1}/{run.pt2}/{run.pt3}")
                lines.append(f"    last3F: {run.last3f}")
                lines.append(f"    issues: {','.join(run.issues) if run.issues else 'none'}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
