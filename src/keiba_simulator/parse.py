from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .models import HorseData, HorseScores, PastRun, RaceInfo


@dataclass
class ParseResult:
    races: List[Tuple[RaceInfo, List[HorseData]]]
    warnings: List[str]


RACE_HEADER_RE = re.compile(r"^(?:RACE|Race|第)\s*(\d+|[A-Za-z0-9]+)")
HORSE_NO_RE = re.compile(r"^\s*(\d{1,2})(?:\s+(\d{1,2}))?")
HORSE_NAME_RE = re.compile(r"^\s*([^\s]+)(?:\s{2,}.*)?$")
NAME_STOP_WORDS = {"⽗", "父", "⺟", "母", "コースレコード"}
COURSE_RE = re.compile(r"コース\s*(\d{3,4})m\s*([芝ダ])\S*([左右])\s*(内|外)?")
LAP_RANK_RE = re.compile(r"\b(\d{1,2})\s*[-\s]\s*(\d{1,2})\b")
PAST_RUN_RE = re.compile(
    r"\b(\d{1,2})-(\d{1,2})(?:-(\d{1,2}))?(?:-(\d{1,2}))?\b.*?3F\s*([0-9]+\.?[0-9]*)"
)
POSITION_SEGMENT_RE = re.compile(r"\d+(?:-\d+){1,3}")
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


def parse_races(text: str, pdf_path: Path) -> ParseResult:
    warnings: List[str] = []
    if not text.strip():
        warnings.append("No text extracted from PDF; using placeholder race.")
        race = _placeholder_race(pdf_path)
        return ParseResult(races=[(race, [])], warnings=warnings)

    race_blocks = _split_by_race(text)
    races: List[Tuple[RaceInfo, List[HorseData]]] = []
    for idx, block in enumerate(race_blocks, start=1):
        race_name = _extract_race_name(block, idx, pdf_path)
        header_info = _extract_course_info(block)
        horses, horse_warnings = _extract_horses(block)
        warnings.extend(horse_warnings)
        horses = _ensure_horse_numbers(horses)
        race_info = RaceInfo(
            race_name=race_name,
            track=header_info["track"],
            surface=header_info["surface"],
            distance_m=header_info["distance_m"],
            direction=header_info["direction"],
            layout=header_info["layout"],
            surface_distance_course=header_info["surface_distance_course"],
            field_size=len(horses),
            am_water_percent=None,
            init_bias=None,
            course_key={"CornerSeverity": 0.5, "LaneChangeDifficulty": 0.5, "StraightOpportunity": 0.5},
        )
        races.append((race_info, horses))

    if not races:
        race = _placeholder_race(pdf_path)
        races.append((race, []))
        warnings.append("Race parsing yielded no blocks; fallback race created.")

    return ParseResult(races=races, warnings=warnings)


def _split_by_race(text: str) -> List[str]:
    lines = text.splitlines()
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if RACE_HEADER_RE.match(line) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks if any(block)]


def _extract_race_name(block: str, index: int, pdf_path: Path) -> str:
    for line in block.splitlines():
        match = RACE_HEADER_RE.match(line)
        if match:
            return f"Race {match.group(1)}"
    return f"Race {index} ({pdf_path.stem})"


def _extract_horses(block: str) -> Tuple[List[HorseData], List[str]]:
    horses: List[HorseData] = []
    warnings: List[str] = []
    lines = block.splitlines()
    seen_numbers: set[int] = set()
    for index, line in enumerate(lines):
        name = _extract_horse_name(line)
        if name is None:
            continue
        number = _find_number_before(lines, index)
        if number is None:
            number = _find_horse_number(lines, index + 1)
        if number is None:
            warnings.append(f"Failed to locate horse number for name: {name}")
            continue
        lap_ranks = _find_lap_ranks(lines, index + 1)
        past_runs = _find_past_runs(lines, index + 1)
        if number in seen_numbers:
            warnings.append(f"Duplicate horse number skipped: {number} ({name})")
            continue
        seen_numbers.add(number)
        horses.append(
            HorseData(
                number=number,
                name=name,
                style="unknown",
                lap_type="C",
                scores=HorseScores(),
                uncertainty=0.7,
                lap_ranks=lap_ranks,
                past_runs=past_runs,
            )
        )
    return horses, warnings


def _find_number_before(lines: List[str], index: int) -> int | None:
    for back in range(1, 3):
        if index - back < 0:
            break
        line = lines[index - back]
        stripped = line.strip()
        if not stripped.isdigit():
            continue
        indent = len(line) - len(line.lstrip())
        number = int(stripped)
        if indent > 10 or number > 18:
            continue
        return number
    return None


def _find_lap_ranks(lines: List[str], start_index: int) -> List[int]:
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index != start_index and _extract_horse_name(line) is not None:
            break
        match = LAP_RANK_RE.search(line)
        if not match:
            continue
        first = int(match.group(1))
        second = int(match.group(2))
        if first == second == 0:
            continue
        return [first, second]
    return []


def _find_past_runs(lines: List[str], start_index: int) -> List[PastRun]:
    runs: List[PastRun] = []
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index != start_index and _extract_horse_name(line) is not None:
            break
        match = PAST_RUN_RE.search(line)
        if not match:
            continue
        positions, tokens_before, tokens_after, issues = _extract_position_tokens(line)
        pt1, pt2, pt3, pos_issues = _normalize_positions(positions)
        issues.extend(pos_issues)
        last3f = _safe_float(match.group(5))
        runs.append(
            PastRun(
                pt1=pt1,
                pt2=pt2,
                pt3=pt3,
                last3f=last3f,
                time_sec=None,
                surface=None,
                distance_m=None,
                track=None,
                raw_text=line.strip(),
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                issues=issues,
                evidence_id=f"legacy:{len(runs)+1}",
            )
        )
    return runs


def _normalize_positions(positions: List[int]) -> tuple[int | None, int | None, int | None, List[str]]:
    issues: List[str] = []
    if not positions:
        return None, None, None, ["MissingPositions"]
    pt1 = positions[0]
    pt2 = positions[1] if len(positions) > 1 else None
    if len(positions) > 2:
        pt3 = positions[2]
    elif pt2 is not None:
        pt3 = pt2
    else:
        pt3 = None
    validated = []
    for value in (pt1, pt2, pt3):
        if value is None:
            validated.append(None)
            continue
        if 1 <= value <= 18:
            validated.append(value)
        else:
            validated.append(None)
            issues.append("OutOfRangeRank")
    return validated[0], validated[1], validated[2], issues


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _extract_position_tokens(line: str) -> tuple[List[int], List[int], List[int], List[str]]:
    issues: List[str] = []
    before_segment = line.split("3F")[0]
    segments = POSITION_SEGMENT_RE.findall(before_segment)
    if not segments:
        return [], [], [], ["MissingPositionSegment"]
    segment = segments[-1]
    tokens_before = [int(token) for token in segment.split("-") if token.isdigit()]
    tokens_after, merge_issue = _repair_rank_tokens(tokens_before)
    if merge_issue:
        issues.append(merge_issue)
    return tokens_after, tokens_before, tokens_after, issues


def _repair_rank_tokens(tokens: List[int]) -> tuple[List[int], str | None]:
    if not tokens:
        return tokens, None
    needs_merge = 0 in tokens or len(tokens) > 4
    result: List[int] = []
    i = 0
    while i < len(tokens):
        cur = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if cur in range(1, 10) and nxt == 0:
            result.append(cur * 10)
            i += 2
            needs_merge = True
            continue
        if needs_merge and cur == 1 and nxt in range(1, 9):
            result.append(10 + nxt)
            i += 2
            continue
        result.append(cur)
        i += 1
    if result != tokens:
        return result, "MergedRankTokens"
    return result, None


def _ensure_horse_numbers(horses: List[HorseData]) -> List[HorseData]:
    if not horses:
        return horses
    numbers = {horse.number for horse in horses}
    max_number = max(numbers)
    if max_number < 16:
        return horses
    for number in range(1, 17):
        if number in numbers:
            continue
        horses.append(
            HorseData(
                number=number,
                name=f"Unknown-{number}",
                style="unknown",
                lap_type="C",
                scores=HorseScores(),
                uncertainty=0.95,
            )
        )
    return sorted(horses, key=lambda horse: horse.number)


def _extract_horse_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped[0].isdigit():
        return None
    match = HORSE_NAME_RE.match(line)
    if not match:
        return None
    name = match.group(1)
    if name in NAME_STOP_WORDS:
        return None
    if any(char.isdigit() for char in name):
        return None
    if len(name) < 2:
        return None
    if not any(ord(char) > 127 for char in name):
        return None
    return name


def _find_horse_number(lines: List[str], start_index: int) -> int | None:
    sex_priority: List[int] = []
    num_only_priority: List[int] = []
    kg_priority: List[int] = []
    fallback: List[int] = []
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index != start_index and _extract_horse_name(line) is not None:
            break
        stripped = line.strip()
        if stripped.isdigit():
            indent = len(line) - len(line.lstrip())
            number = int(stripped)
            if indent > 10 or number > 18:
                continue
            if _next_name_line(lines, index + 1) is not None:
                continue
            num_only_priority.append(number)
            continue
        indent = len(line) - len(line.lstrip())
        if indent > 10:
            continue
        match = HORSE_NO_RE.match(line)
        if not match:
            continue
        first = match.group(1)
        second = match.group(2)
        try:
            number = int(second or first)
        except ValueError:
            continue
        if any(tag in line for tag in ("牡", "牝", "せん", "セン")):
            sex_priority.append(number)
        elif "kg" in line:
            kg_priority.append(number)
        else:
            fallback.append(number)
    if sex_priority:
        return sex_priority[0]
    if num_only_priority:
        return num_only_priority[0]
    if kg_priority:
        return kg_priority[0]
    if fallback:
        return fallback[0]
    return None


def _next_name_line(lines: List[str], start_index: int) -> str | None:
    for index in range(start_index, len(lines)):
        candidate = lines[index]
        if not candidate.strip():
            continue
        return _extract_horse_name(candidate)
    return None


def _placeholder_race(pdf_path: Path) -> RaceInfo:
    return RaceInfo(
        race_name=f"Race 1 ({pdf_path.stem})",
        track="unknown",
        surface="unknown",
        distance_m=0,
        direction="unknown",
        layout="main",
        surface_distance_course="unknown",
        field_size=0,
        am_water_percent=None,
        init_bias=None,
        course_key={"CornerSeverity": 0.5, "LaneChangeDifficulty": 0.5, "StraightOpportunity": 0.5},
    )


def _extract_course_info(block: str) -> dict:
    lines = block.splitlines()
    track = _find_track_name(lines)
    distance_m = 0
    surface = "unknown"
    direction = "unknown"
    layout = "main"
    for line in lines:
        match = COURSE_RE.search(line)
        if not match:
            continue
        distance_m = int(match.group(1))
        surface = "turf" if match.group(2) == "芝" else "dirt"
        direction = "R" if match.group(3) == "右" else "L"
        layout = _layout_from_token(match.group(4))
        break
    surface_distance_course = _format_surface_distance(surface, distance_m, direction, layout)
    return {
        "track": track,
        "surface": surface,
        "distance_m": distance_m,
        "direction": direction,
        "layout": layout,
        "surface_distance_course": surface_distance_course,
    }


def _find_track_name(lines: List[str]) -> str:
    for line in lines[:3]:
        normalized = _normalize_text(line)
        for track in TRACK_NAMES:
            if track in normalized:
                return track
    return "unknown"


def _layout_from_token(token: str | None) -> str:
    if token == "内":
        return "inner"
    if token == "外":
        return "outer"
    return "main"


def _normalize_text(text: str) -> str:
    replacements = {
        "⼭": "山",
        "⼩": "小",
        "⽥": "田",
        "⽊": "木",
        "⽇": "日",
        "⽉": "月",
        "⽕": "火",
        "⽔": "水",
        "⾦": "金",
        "⼟": "土",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _format_surface_distance(surface: str, distance_m: int, direction: str, layout: str) -> str:
    if surface == "unknown" or distance_m == 0:
        return "unknown"
    surface_label = "芝" if surface == "turf" else "ダ"
    direction_label = "右" if direction == "R" else "左"
    layout_label = ""
    if layout == "inner":
        layout_label = "内"
    elif layout == "outer":
        layout_label = "外"
    return f"{surface_label}{distance_m}m {direction_label}{layout_label}".strip()
