from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from urllib import request

from .horse_blocks import build_horse_blocks
from ..models import HorseData, PastRun


@dataclass(frozen=True)
class LLMRunIssue:
    run_index: int | None
    severity: str
    reason: str
    drop_run: bool


@dataclass(frozen=True)
class LLMCheckResult:
    horse_no: int
    expected_runs: int | None
    issues: List[LLMRunIssue]


def check_runs_with_llm(
    text: str,
    horses: List[HorseData],
    runs_by_horse: Dict[int, List[PastRun]],
    config_path: Path,
) -> Dict[int, LLMCheckResult]:
    config = _load_json(config_path)
    base_url = config["base_url"].rstrip("/") + "/v1/chat/completions"
    results: Dict[int, LLMCheckResult] = {}
    lines, blocks = build_horse_blocks(text, horses)

    for horse in horses:
        runs = runs_by_horse.get(horse.number, [])
        if not _needs_llm_check(runs):
            continue
        block = blocks.get(horse.number)
        if block is None:
            continue
        block_text = "\n".join(block.lines)
        text_limit = int(config.get("text_limit", 4000))
        if len(block_text) > text_limit:
            block_text = block_text[:text_limit]
        payload = _build_payload(horse, runs, block_text, config)
        response = _post_json(base_url, payload)
        content = _extract_content(response)
        parsed = _parse_json_content(content)
        if parsed is None:
            results[horse.number] = LLMCheckResult(
                horse_no=horse.number,
                expected_runs=None,
                issues=[LLMRunIssue(run_index=None, severity="error", reason="InvalidJSON", drop_run=False)],
            )
            continue
        results[horse.number] = _parse_result(horse.number, parsed)

    return results


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_llm_check(runs: List[PastRun]) -> bool:
    if not runs:
        return True
    for run in runs:
        if run.issues:
            return True
        if run.surface is None or run.distance_m is None or run.track is None:
            return True
        if run.time_sec is None:
            return True
    return False


def _build_payload(horse: HorseData, runs: List[PastRun], block_text: str, config: dict) -> dict:
    system = (
        "You are a data QA engine for race parsing. "
        "Return ONLY valid JSON. Do not include commentary or markdown."
    )
    run_rows = [
        {
            "run_index": idx + 1,
            "pt": [run.pt1, run.pt2, run.pt3],
            "last3f": run.last3f,
            "time_sec": run.time_sec,
            "surface": run.surface,
            "distance_m": run.distance_m,
            "track": run.track,
            "raw_text": run.raw_text,
            "issues": run.issues,
        }
        for idx, run in enumerate(runs)
    ]
    schema = {
        "type": "object",
        "properties": {
            "horse_no": {"type": "integer"},
            "expected_runs": {"type": ["integer", "null"]},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "run_index": {"type": ["integer", "null"]},
                        "severity": {"type": "string"},
                        "reason": {"type": "string"},
                        "drop_run": {"type": "boolean"},
                    },
                    "required": ["severity", "reason", "drop_run"],
                },
            },
        },
        "required": ["horse_no", "issues"],
    }
    user = (
        "Check the extracted runs and the raw block text. "
        "Identify contradictions, missing runs, or malformed fields. "
        "Only mark drop_run=true when the run should be excluded. "
        f"horse_no={horse.number}\n"
        f"extracted_runs={json.dumps(run_rows, ensure_ascii=False)}\n"
        f"block_text=\n{block_text}\n\n"
        f"Return JSON only. Schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": int(config.get("max_tokens", 2048)),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "run_quality_check",
                "schema": schema,
            },
        },
    }


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_content(response: dict) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return content.strip()


def _parse_json_content(content: str) -> dict | None:
    cleaned = _strip_code_fence(content)
    for candidate in (_extract_json_object(cleaned), cleaned):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return content[start : end + 1]


def _parse_result(horse_no: int, parsed: dict) -> LLMCheckResult:
    issues_data = parsed.get("issues", []) if isinstance(parsed, dict) else []
    issues: List[LLMRunIssue] = []
    for item in issues_data:
        if not isinstance(item, dict):
            continue
        issues.append(
            LLMRunIssue(
                run_index=_coerce_int(item.get("run_index")),
                severity=str(item.get("severity", "warn")),
                reason=str(item.get("reason", "")),
                drop_run=bool(item.get("drop_run", False)),
            )
        )
    expected_runs = _coerce_int(parsed.get("expected_runs")) if isinstance(parsed, dict) else None
    return LLMCheckResult(horse_no=horse_no, expected_runs=expected_runs, issues=issues)


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
