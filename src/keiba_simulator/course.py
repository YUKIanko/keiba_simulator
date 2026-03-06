from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TrackCourse:
    track: str
    direction: str
    surface: str
    layout: str
    lap_m: float
    homestretch_m: float
    width_m_min: float | None
    width_m_max: float | None
    elevation_m: float | None
    notes: str


def load_trackdata(path: Path) -> list[TrackCourse]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    courses: list[TrackCourse] = []
    for entry in payload.get("courses", []):
        courses.append(
            TrackCourse(
                track=entry.get("track", "unknown"),
                direction=entry.get("direction", ""),
                surface=entry.get("surface", ""),
                layout=entry.get("layout", ""),
                lap_m=float(entry.get("lap_m", 0.0)),
                homestretch_m=float(entry.get("homestretch_m", 0.0)),
                width_m_min=_to_float(entry.get("width_m_min")),
                width_m_max=_to_float(entry.get("width_m_max")),
                elevation_m=_to_float(entry.get("elevation_m")),
                notes=entry.get("notes", ""),
            )
        )
    return courses


def find_course(
    courses: Iterable[TrackCourse],
    track: str,
    surface: str,
    layout: str,
) -> Optional[TrackCourse]:
    for course in courses:
        if course.track != track:
            continue
        if course.surface != surface:
            continue
        if layout != "main" and course.layout != layout:
            continue
        return course
    return None


def derive_course_key(course: TrackCourse | None) -> dict[str, float]:
    if course is None:
        return {"CornerSeverity": 0.5, "LaneChangeDifficulty": 0.5, "StraightOpportunity": 0.5}

    lap_m = course.lap_m or 1800.0
    homestretch_m = course.homestretch_m or 350.0
    width_avg = _width_avg(course.width_m_min, course.width_m_max)

    corner_severity = clamp(1 - ((lap_m - 1400.0) / (2200.0 - 1400.0)))
    lane_change = 0.5
    if width_avg is not None:
        lane_change = clamp(1 - ((width_avg - 20.0) / (40.0 - 20.0)))
    straight_opportunity = clamp((homestretch_m - 250.0) / (700.0 - 250.0))
    uphill_tag = 1.0 if (course.elevation_m or 0.0) >= 3.0 else 0.0

    return {
        "CornerSeverity": round(corner_severity, 3),
        "LaneChangeDifficulty": round(lane_change, 3),
        "StraightOpportunity": round(straight_opportunity, 3),
        "UphillTag": uphill_tag,
    }


def _width_avg(width_min: float | None, width_max: float | None) -> float | None:
    if width_min is None and width_max is None:
        return None
    if width_min is None:
        return width_max
    if width_max is None:
        return width_min
    return (width_min + width_max) / 2


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
