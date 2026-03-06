from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..models import HorseData


@dataclass(frozen=True)
class ProxyConfig:
    use_mean: bool = True


def compute_proxies(horses: List[HorseData], config: ProxyConfig | None = None) -> Dict[int, Dict[str, float | None]]:
    config = config or ProxyConfig()
    proxies: Dict[int, Dict[str, float | None]] = {}

    pace_values = []
    last3f_values = []
    for horse in horses:
        pace = _pace_rank(horse)
        last3f = _last3f_avg(horse)
        if pace is not None:
            pace_values.append(pace)
        if last3f is not None:
            last3f_values.append(last3f)
        proxies[horse.number] = {
            "pace_rank": pace,
            "last3f_avg": last3f,
            "delta_rank": None,
            "rel_last3f": None,
        }

    mean_last3f, std_last3f = _mean_std(last3f_values)
    for horse in horses:
        pace_rank = proxies[horse.number]["pace_rank"]
        last3f_avg = proxies[horse.number]["last3f_avg"]
        if pace_rank is not None and last3f_avg is not None:
            proxies[horse.number]["delta_rank"] = pace_rank - last3f_avg
        if last3f_avg is not None and std_last3f:
            proxies[horse.number]["rel_last3f"] = (last3f_avg - mean_last3f) / std_last3f

    return proxies


def _pace_rank(horse: HorseData) -> float | None:
    values = []
    for run in horse.past_runs:
        if run.pt1 is None or run.pt2 is None or run.pt3 is None:
            continue
        values.append((run.pt1 + run.pt2 + run.pt3) / 3)
    if not values:
        return None
    return sum(values) / len(values)


def _last3f_avg(horse: HorseData) -> float | None:
    values = [run.last3f for run in horse.past_runs if run.last3f is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _mean_std(values: List[float]) -> tuple[float, float | None]:
    if not values:
        return 0.0, None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5 if variance > 0 else None
    return mean, std
