from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .normalize_text import normalize_text
from ..models import HorseData


@dataclass(frozen=True)
class HorseBlock:
    horse_no: int
    name: str
    start: int
    end: int
    lines: List[str]


def build_horse_blocks(text: str, horses: List[HorseData]) -> tuple[List[str], Dict[int, HorseBlock]]:
    normalized = normalize_text(text)
    lines = normalized.splitlines()
    name_index = _build_name_index(lines, horses)
    blocks: Dict[int, HorseBlock] = {}
    for horse in horses:
        indices = name_index.get(horse.name, [])
        if not indices:
            continue
        start = indices[0]
        end = _next_horse_index(start, name_index)
        if end is None:
            end = len(lines)
        block_lines = lines[start:end]
        blocks[horse.number] = HorseBlock(
            horse_no=horse.number,
            name=horse.name,
            start=start,
            end=end,
            lines=block_lines,
        )
    return lines, blocks


def _build_name_index(lines: List[str], horses: List[HorseData]) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {horse.name: [] for horse in horses}
    for line_no, line in enumerate(lines):
        for horse in horses:
            if _anchor_line(line, horse):
                index[horse.name].append(line_no)
    return index


def _next_horse_index(current: int, name_index: Dict[str, List[int]]) -> int | None:
    candidates = [idx for indices in name_index.values() for idx in indices if idx > current]
    return min(candidates) if candidates else None


def _anchor_line(line: str, horse: HorseData) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if horse.name not in stripped:
        return False
    # In JRA layouts, horse-name lines often have extra columns after the name.
    # Treat the first token as the anchor so we still isolate each horse block.
    first_token = stripped.split()[0]
    return first_token == horse.name
