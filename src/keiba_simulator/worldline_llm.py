from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List
from urllib import request

from .course import TrackCourse
from .models import HorseData, RaceInfo


def infer_after_initial_worldlines_with_llm(
    race_info: RaceInfo,
    horses: List[HorseData],
    course: TrackCourse | None,
    config_path: Path,
) -> Dict[str, object] | None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_url = config["base_url"].rstrip("/") + "/v1/chat/completions"
    payload = _build_payload(race_info, horses, course, config)
    response = _post_json(base_url, payload)
    content = _extract_content(response)
    parsed = _parse_json_content(content)
    if parsed is None or not isinstance(parsed, dict):
        return None
    return parsed


def _build_payload(
    race_info: RaceInfo,
    horses: List[HorseData],
    course: TrackCourse | None,
    config: dict,
) -> dict:
    course_context = _course_context(race_info, course)
    running_style_heuristics = (
        "Running style heuristics for post-initial worldline generation:\n\n"
        "Front-runner / Nige:\n"
        "- If there are few other front-runners, reduce early pressure and reduce unnecessary acceleration cost.\n"
        "- In that case, increase late stamina retention and persistence.\n"
        "- If the course is one-turn or has a long final straight, reduce the advantage of front-running because late runners have more time to catch up.\n"
        "- If the course has many corners, increase front-runner persistence because repeated cornering reduces overall speed and helps conserve energy.\n\n"
        "Stalker / Senko:\n"
        "- Stalkers depend on the pace set by front-runners.\n"
        "- If the race shape forces repeated acceleration to secure position, lower late stamina expectation.\n"
        "- If pace is stable and running styles are naturally dispersed, increase stalker win probability.\n"
        "- If similar stalkers are adjacent and ability is similar, inner position is advantageous due to lower path loss, especially on courses with more corners.\n"
        "- On courses with few corners, inner-position advantage is weaker.\n\n"
        "Closer / Sashi:\n"
        "- Increase evaluation when front-runners and stalkers are likely to spend energy early.\n"
        "- Increase evaluation on one-turn or long-straight courses because they have more time and space to improve late.\n"
        "- Decrease evaluation on short-straight or many-corner courses because there is less time to close and more difficulty accelerating through turns.\n"
        "- If there are few front-runners and pace is calm, reduce closer evaluation because leaders retain more energy.\n"
        "- If many pace-pressuring horses exist, raise closer evaluation.\n"
        "- On courses with many corners, wider draws slightly hurt closers because of path loss and delayed launch timing.\n\n"
        "Deep closer / Oikomi:\n"
        "- Strongly pace-dependent.\n"
        "- Lower evaluation when early pace is calm or when there are few speed horses.\n"
        "- Raise evaluation when early competition is intense and late front fatigue is likely.\n"
        "- Raise evaluation on long-straight uphill finishes because leaders weaken more easily.\n"
        "- Lower evaluation on many-corner courses because rear runners suffer more path loss and unstable lane access.\n"
        "- On one-turn long-straight courses, allow stronger late improvement than standard closers."
    )
    initial_positions = []
    style_summary = {"Nige": 0, "Senko": 0, "Sashi": 0, "Oikomi": 0, "Unknown": 0}
    for horse in horses:
        style_bucket = _style_bucket(horse.style)
        style_summary[style_bucket] += 1
        initial_positions.append(
            {
                "horse_no": horse.number,
                "name": horse.name,
                "style_from_lap_rank": horse.style,
                "style_bucket": style_bucket,
                "initial_rank_hint": horse.lap_ranks[0] if horse.lap_ranks else None,
                "last3f_avg": horse.last3f_avg,
                "time_index": horse.time_index,
            }
        )
    schema = {
        "type": "object",
        "properties": {
            "worldlines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pace_scenario": {"type": "string"},
                        "shape": {"type": "string"},
                        "secondary_press": {"type": "boolean"},
                        "traffic_mode": {"type": "string"},
                        "outside_sweep": {"type": "boolean"},
                        "probability": {"type": "number"},
                        "reason": {"type": "array", "items": {"type": "string"}},
                        "horse_dynamics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "horse_no": {"type": "integer"},
                                    "mid_gain": {"type": "number"},
                                    "late_gain": {"type": "number"},
                                    "traffic_risk_adj": {"type": "number"},
                                    "wide_risk_adj": {"type": "number"},
                                },
                                "required": ["horse_no"],
                            },
                        },
                    },
                    "required": [
                        "pace_scenario",
                        "shape",
                        "secondary_press",
                        "traffic_mode",
                        "outside_sweep",
                        "probability",
                        "reason",
                        "horse_dynamics",
                    ],
                },
            }
        },
        "required": ["worldlines"],
    }
    system = (
        "You are a race scenario planner specialized in post-initial pack dynamics.\n\n"
        "The initial order and initial positioning are already fixed by `style_from_lap_rank` and must not be recomputed, re-ranked, or corrected.\n\n"
        "Your task is to infer only what happens after the initial phase:\n"
        "- pack compression or expansion\n"
        "- forward retention or loss of position\n"
        "- wide-lane loss on corners\n"
        "- gradual improvement from preserved runners\n"
        "- fatigue or weakening of early leaders\n"
        "- plausible branching race-flow scenarios\n\n"
        "Use course structure as the main causal driver of pack changes:\n"
        "- A short distance from start to first corner increases early position pressure and favors inside / forward retention.\n"
        "- Tight or frequent corners increase deceleration, compression, and lane-loss risk, especially for horses forced wide.\n"
        "- A long final straight increases the chance of late improvement by runners that preserved energy earlier.\n"
        "- An uphill finish reduces pure front-speed persistence and increases fatigue risk for horses that spent energy early.\n"
        "- A flat or easier finish allows earlier forward momentum to persist more often.\n"
        "- Course shape should affect pack transitions, but should not create extreme or unrealistic order changes without a clear reason.\n\n"
        "Important rules:\n"
        "- Do NOT predict final ranking.\n"
        "- Do NOT recompute the initial order.\n"
        "- Do NOT invent large movements for every horse.\n"
        "- Focus only on meaningful movers and local pack changes after the initial phase.\n"
        "- Keep dynamics small, plausible, and interpretable.\n"
        "- Treat the output as intermediate scenario generation for downstream numerical simulation, not as a final prediction.\n\n"
        "Output 3-4 branching worldlines.\n"
        "Each worldline should represent one plausible race-flow branch after the initial phase.\n\n"
        "Return JSON only."
    )
    user = (
        f"race_info={json.dumps({'race_name': race_info.race_name, 'track': race_info.track, 'surface': race_info.surface, 'distance_m': race_info.distance_m}, ensure_ascii=False)}\n\n"
        f"course_context={json.dumps(course_context, ensure_ascii=False)}\n\n"
        f"initial_positions={json.dumps(initial_positions, ensure_ascii=False)}\n\n"
        f"style_summary={json.dumps(style_summary, ensure_ascii=False)}\n\n"
        f"running_style_heuristics=\n{running_style_heuristics}\n\n"
        "Task:\n"
        "Infer only post-initial pack changes and branching race scenarios.\n"
        "The initial positions are fixed and must remain unchanged as the starting state.\n\n"
        "What to infer:\n"
        "- which horses are more likely to retain position after the initial phase\n"
        "- which horses are more likely to lose position due to corner pressure or wide travel\n"
        "- which horses may gradually improve later because of energy preservation\n"
        "- where pack compression or release is likely to happen\n"
        "- how course structure changes the race flow after the initial phase\n\n"
        "Constraints:\n"
        "- Do not output final ranking.\n"
        "- Do not recompute initial positions.\n"
        "- Produce 3-4 branching worldlines.\n"
        "- Each worldline should be driven by plausible course-related race flow.\n"
        "- horse_dynamics values should be small and bounded near [-0.5, 0.5].\n"
        "- Keep horse_dynamics concise: include only 4-8 horses per worldline with meaningful movement.\n"
        "- Avoid extreme reorderings unless clearly justified by course structure.\n"
        "- Keep probabilities normalized close to 1.0.\n\n"
        "Style integration rules:\n"
        "- Use each horse's style_bucket together with running_style_heuristics.\n"
        "- Apply style effects to each horse individually, not only at field level.\n"
        "- If style_from_lap_rank is unknown, keep adjustment conservative.\n\n"
        "Recommended branch types to cover:\n"
        "- early inside / forward retention branch\n"
        "- corner compression and wide-loss branch\n"
        "- late improvement branch enabled by preserved energy\n"
        "- uphill fatigue or front weakening branch (if slope is relevant)\n\n"
        "Return JSON only.\n\n"
        f"schema={json.dumps(schema, ensure_ascii=False)}"
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
                "name": "worldline_after_initial",
                "schema": schema,
            },
        },
    }


def _course_context(race_info: RaceInfo, course: TrackCourse | None) -> Dict[str, object]:
    lap_m = course.lap_m if course else 1800.0
    start_to_corner_m = max(50.0, race_info.distance_m % max(1.0, lap_m))
    start_position = "long_run_to_corner" if start_to_corner_m >= 280 else "short_run_to_corner"
    corner_profile = "tight" if race_info.course_key.get("CornerSeverity", 0.5) >= 0.6 else "gentle"
    homestretch_m = course.homestretch_m if course else 350.0
    uphill = bool(race_info.course_key.get("UphillTag", 0.0) >= 1.0)
    return {
        "start_position": start_position,
        "corner_profile": corner_profile,
        "homestretch_m": homestretch_m,
        "uphill_present": uphill,
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


def _style_bucket(style: str) -> str:
    if style == "逃":
        return "Nige"
    if style == "先":
        return "Senko"
    if style == "差":
        return "Sashi"
    if style == "追":
        return "Oikomi"
    return "Unknown"
