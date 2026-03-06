from __future__ import annotations

from typing import List, Tuple

from ..models import PastRun


def validate_run(run: PastRun, head_cnt: int | None = None) -> Tuple[PastRun | None, List[str]]:
    issues = list(run.issues)
    limit = head_cnt or 18
    if run.pt1 is None or run.pt2 is None or run.pt3 is None:
        issues.append("MissingRank")
    for value in (run.pt1, run.pt2, run.pt3):
        if value is None:
            continue
        if value < 1 or value > limit:
            issues.append("RankOutOfRange")
    if run.last3f is None:
        issues.append("MissingLast3F")
    elif run.last3f < 30 or run.last3f > 60:
        issues.append("Last3FOutOfRange")

    if issues:
        return None, issues
    return run, []
