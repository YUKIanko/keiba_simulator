from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RaceInfo:
    race_name: str
    track: str
    surface: str
    distance_m: int
    direction: str
    layout: str
    surface_distance_course: str
    field_size: int
    am_water_percent: Optional[float]
    init_bias: Optional[str]
    course_key: Dict[str, float]


@dataclass
class HorseScores:
    cruise: float = 0.0
    kick: float = 0.0
    stamina: float = 0.0
    turn: float = 0.0
    start_skill: float = 0.0
    moveability: float = 0.0
    traffic_resist: float = 0.0

    def total(self) -> float:
        return (
            self.cruise
            + self.kick
            + self.stamina
            + self.turn
            + self.start_skill
            + self.moveability
            + self.traffic_resist
        )


@dataclass(frozen=True)
class PastRun:
    pt1: Optional[int]
    pt2: Optional[int]
    pt3: Optional[int]
    last3f: Optional[float]
    time_sec: Optional[float]
    surface: Optional[str]
    distance_m: Optional[int]
    track: Optional[str]
    raw_text: str
    tokens_before: List[int]
    tokens_after: List[int]
    issues: List[str]
    evidence_id: str


@dataclass
class HorseData:
    number: int
    name: str
    style: str
    lap_type: str
    scores: HorseScores
    uncertainty: float
    lap_ranks: List[int] = field(default_factory=list)
    past_runs: List[PastRun] = field(default_factory=list)
    dropped_runs: List[PastRun] = field(default_factory=list)
    pace_rank: Optional[float] = None
    last3f_avg: Optional[float] = None
    delta_rank: Optional[float] = None
    rel_last3f: Optional[float] = None
    raw_time: Optional[float] = None
    time_index: Optional[float] = None
    time_z: Optional[float] = None
    used_runs: List[str] = field(default_factory=list)
    time_features_debug: List[str] = field(default_factory=list)
    notes_evidence: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Worldline:
    pace_scenario: str
    shape: str
    secondary_press: bool
    traffic_mode: str
    outside_sweep: bool
    probability: float
    reason: List[str]
    horse_dynamics: Dict[int, Dict[str, float]] = field(default_factory=dict)


@dataclass
class SimHorseResult:
    number: int
    name: str
    raw_score: float
    p_win: float
    p_in3: float
    traffic_fail: float
    wide_cost_fail: float


@dataclass
class SimRaceResult:
    race_name: str
    worldlines: List[Worldline]
    horses: List[SimHorseResult]
    scenario_comment: str
    devil_speak: Optional[str]
    short_memo: str
