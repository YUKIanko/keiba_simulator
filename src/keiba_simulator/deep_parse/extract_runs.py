from __future__ import annotations

import re
from typing import Dict, List

from .horse_blocks import build_horse_blocks
from ..models import HorseData, PastRun

TRACK_NAMES = [
    "東京",
    "中山",
    "阪神",
    "京都",
    "新潟",
    "中京",
    "札幌",
    "函館",
    "福島",
    "小倉",
]

_RUN_ENTRY_RE = re.compile(
    r"(?<![0-9:.])(\d(?:\s*\d)*\s*-\s*\d(?:\s*\d)*(?:\s*-\s*\d(?:\s*\d)*){0,2})\s*3F\s*([0-9]+\.?[0-9]*)"
)


def extract_runs(text: str, horses: List[HorseData]) -> Dict[int, List[PastRun]]:
    lines, blocks = build_horse_blocks(text, horses)
    runs_by_horse: Dict[int, List[PastRun]] = {horse.number: [] for horse in horses}

    for horse in horses:
        block = blocks.get(horse.number)
        if block is None:
            continue
        runs_by_horse[horse.number] = _parse_runs_from_block(block.lines, horse, lines, block.start)

    return runs_by_horse


def _parse_runs_from_block(
    block: List[str], horse: HorseData, lines: List[str], anchor_index: int
) -> List[PastRun]:
    runs: List[PastRun] = []
    context = {"surface": None, "distance_m": None, "track": None}
    context_tracks: List[str] = []
    context_pairs: List[tuple[int, str]] = []
    header_context = _scan_header_context(lines, anchor_index)
    for line in block:
        context = _merge_context(context, _extract_run_context(line))
        context_tracks = _update_track_list(context_tracks, line)
        context_pairs = _update_surface_list(context_pairs, line)
        entries = list(_RUN_ENTRY_RE.finditer(line))
        if not entries:
            continue
        for index, match in enumerate(entries):
            fragment = _run_fragment(line, entries, index)
            segment = match.group(1)
            tokens_before = [
                int(token.replace(" ", ""))
                for token in segment.split("-")
                if token.strip().replace(" ", "").isdigit()
            ]
            tokens_after, issues = _repair_rank_tokens(tokens_before)
            if 0 in tokens_after:
                issues.append("ZeroToken")
            if len(tokens_after) < 2 or len(tokens_after) > 4:
                issues.append("ColumnMismatch")
            if _count_time_tokens(fragment) >= 2:
                issues.append("MultiTimeInFragment")
            pt1, pt2, pt3 = _normalize_positions(tokens_after)
            last3f = _safe_float(match.group(2))
            time_sec = _extract_time_sec(line, match.start())
            surface, distance_m = _select_surface(context_pairs, index, context)
            track = _select_track(context_tracks, index, context)
            if surface is None:
                surface = header_context.get("surface")
            if distance_m is None:
                distance_m = header_context.get("distance_m")
            if track is None:
                track = header_context.get("track")
            evidence_id = f"{horse.number}:{len(runs) + 1}"
            runs.append(
                PastRun(
                    pt1=pt1,
                    pt2=pt2,
                    pt3=pt3,
                    last3f=last3f,
                    time_sec=time_sec,
                    surface=surface,
                    distance_m=distance_m,
                    track=track,
                    raw_text=fragment.strip(),
                    tokens_before=tokens_before,
                    tokens_after=tokens_after,
                    issues=issues,
                    evidence_id=evidence_id,
                )
            )
    return runs


def _repair_rank_tokens(tokens: List[int]) -> tuple[List[int], List[str]]:
    if not tokens:
        return tokens, ["MissingTokens"]
    result: List[int] = []
    issues: List[str] = []
    i = 0
    while i < len(tokens):
        cur = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if cur in range(1, 10) and nxt == 0:
            result.append(cur * 10)
            i += 2
            issues.append("Merged10")
            continue
        if cur == 1 and nxt in range(1, 9):
            result.append(10 + nxt)
            i += 2
            issues.append("Merged1x")
            continue
        result.append(cur)
        i += 1
    return result, issues


def _normalize_positions(tokens: List[int]) -> tuple[int | None, int | None, int | None]:
    if not tokens:
        return None, None, None
    pt1 = tokens[0]
    pt2 = tokens[1] if len(tokens) > 1 else None
    pt3 = tokens[2] if len(tokens) > 2 else pt2
    return pt1, pt2, pt3


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _extract_time_sec(line: str, before_index: int) -> float | None:
    candidates = list(re.finditer(r"\d+:\d{2}\.\d", line))
    if not candidates:
        return None
    match = max((m for m in candidates if m.start() < before_index), key=lambda m: m.start(), default=None)
    if match is None:
        return None
    time_text = match.group(0)
    minutes, seconds = time_text.split(":")
    try:
        return int(minutes) * 60 + float(seconds)
    except ValueError:
        return None


def _extract_run_context(line: str) -> dict:
    surface = None
    distance_m = None
    track = None
    for name in TRACK_NAMES:
        if name in line:
            track = name
            break
    match = re.search(r"(\d{3,4})\s*(芝|ダ)", line)
    if match:
        distance_m = int(match.group(1))
        surface = "turf" if match.group(2) == "芝" else "dirt"
    return {"surface": surface, "distance_m": distance_m, "track": track}


def _merge_context(current: dict, update: dict) -> dict:
    merged = dict(current)
    for key, value in update.items():
        if value is not None:
            merged[key] = value
    return merged


def _update_track_list(current: List[str], line: str) -> List[str]:
    tracks = [name for name in TRACK_NAMES if name in line]
    return tracks if tracks else current


def _update_surface_list(current: List[tuple[int, str]], line: str) -> List[tuple[int, str]]:
    pairs = [(int(match.group(1)), match.group(2)) for match in re.finditer(r"(\d{3,4})\s*(芝|ダ)", line)]
    return pairs if pairs else current


def _select_surface(pairs: List[tuple[int, str]], index: int, context: dict) -> tuple[str | None, int | None]:
    if pairs:
        bucket = pairs[index] if index < len(pairs) else pairs[-1]
        distance_m = bucket[0]
        surface = "turf" if bucket[1] == "芝" else "dirt"
        return surface, distance_m
    return context.get("surface"), context.get("distance_m")


def _select_track(tracks: List[str], index: int, context: dict) -> str | None:
    if tracks:
        return tracks[index] if index < len(tracks) else tracks[-1]
    return context.get("track")


def _run_fragment(line: str, entries: List[re.Match], index: int) -> str:
    start = entries[index].start()
    end = entries[index + 1].start() if index + 1 < len(entries) else len(line)
    return line[start:end]


def _count_time_tokens(fragment: str) -> int:
    return len(re.findall(r"\d+:\d{2}\.\d", fragment))


def _scan_header_context(lines: List[str], anchor_index: int) -> dict:
    context = {"surface": None, "distance_m": None, "track": None}
    start = max(0, anchor_index - 6)
    for line in lines[start:anchor_index + 1]:
        update = _extract_run_context(line)
        context = _merge_context(context, update)
    return context
