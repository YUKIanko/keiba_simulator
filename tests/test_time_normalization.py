from keiba_simulator.models import HorseData, HorseScores, PastRun
from keiba_simulator.time_features import compute_time_features


def test_time_features_surface_isolated() -> None:
    horse = HorseData(
        number=1,
        name="Test",
        style="",
        lap_type="C",
        scores=HorseScores(),
        uncertainty=0.5,
        past_runs=[
            PastRun(
                pt1=1,
                pt2=1,
                pt3=1,
                last3f=35.0,
                time_sec=70.0,
                surface="turf",
                distance_m=1200,
                track="中山",
                raw_text="芝1200 1:10.0",
                tokens_before=[1, 1],
                tokens_after=[1, 1],
                issues=[],
                evidence_id="1:1",
            ),
            PastRun(
                pt1=2,
                pt2=2,
                pt3=2,
                last3f=36.0,
                time_sec=72.0,
                surface="dirt",
                distance_m=1200,
                track="中山",
                raw_text="ダ1200 1:12.0",
                tokens_before=[2, 2],
                tokens_after=[2, 2],
                issues=[],
                evidence_id="1:2",
            ),
        ],
    )

    results = compute_time_features([horse], surface="dirt", distance_m=1200, track_group="中山")
    feature = results[1]
    assert feature.raw_time == 72.0
    assert feature.used_runs == ["1:2:dirt:1200:中山"]
    assert all("surface=turf" in entry for entry in feature.debug if "skip" in entry)


def test_time_index_uses_time_per_distance() -> None:
    fast = HorseData(
        number=1,
        name="Fast",
        style="逃",
        lap_type="C",
        scores=HorseScores(),
        uncertainty=0.5,
        past_runs=[
            PastRun(
                pt1=1,
                pt2=1,
                pt3=1,
                last3f=35.0,
                time_sec=70.0,
                surface="dirt",
                distance_m=1200,
                track="中山",
                raw_text="ダ1200 1:10.0",
                tokens_before=[1, 1],
                tokens_after=[1, 1],
                issues=[],
                evidence_id="1:1",
            )
        ],
    )
    slow = HorseData(
        number=2,
        name="Slow",
        style="逃",
        lap_type="C",
        scores=HorseScores(),
        uncertainty=0.5,
        past_runs=[
            PastRun(
                pt1=1,
                pt2=1,
                pt3=1,
                last3f=36.0,
                time_sec=74.0,
                surface="dirt",
                distance_m=1200,
                track="中山",
                raw_text="ダ1200 1:14.0",
                tokens_before=[1, 1],
                tokens_after=[1, 1],
                issues=[],
                evidence_id="2:1",
            )
        ],
    )

    results = compute_time_features([fast, slow], surface="dirt", distance_m=1200, track_group="中山")
    assert results[1].time_index is not None
    assert results[2].time_index is not None
    assert results[1].time_index > results[2].time_index
    assert results[1].time_z is not None and results[1].time_z > 0
    assert results[2].time_z is not None and results[2].time_z < 0
