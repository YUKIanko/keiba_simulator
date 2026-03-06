from keiba_simulator.deep_parse.extract_runs import extract_runs
from keiba_simulator.deep_parse.horse_blocks import build_horse_blocks
from keiba_simulator.models import HorseData, HorseScores


def _horse(number: int, name: str) -> HorseData:
    return HorseData(
        number=number,
        name=name,
        style="unknown",
        lap_type="C",
        scores=HorseScores(),
        uncertainty=0.5,
    )


def test_build_horse_blocks_accepts_lines_with_extra_columns() -> None:
    text = "\n".join(
        [
            "アドミ    中山 牝未勝利",
            "5-4 3F 38.1",
            "ビアーレ  東京 牝新馬",
            "4-4 3F 35.1",
        ]
    )
    horses = [_horse(2, "アドミ"), _horse(3, "ビアーレ")]
    _, blocks = build_horse_blocks(text, horses)
    assert 2 in blocks
    assert 3 in blocks
    assert blocks[2].lines[0].startswith("アドミ")
    assert blocks[3].lines[0].startswith("ビアーレ")


def test_extract_runs_reads_surface_distance_pair() -> None:
    text = "\n".join(
        [
            "アドミ",
            "2026.01.12 1200ダ 良 中山",
            "5-4 3F 38.1",
        ]
    )
    horses = [_horse(2, "アドミ")]
    runs = extract_runs(text, horses)[2]
    assert len(runs) == 1
    assert runs[0].surface == "dirt"
    assert runs[0].distance_m == 1200
