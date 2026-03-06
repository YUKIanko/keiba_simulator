from pathlib import Path

from keiba_simulator.parse import parse_races


def test_all_numbers_present_when_16_found(tmp_path: Path) -> None:
    text = """
    中山1R コース 1200m ダ 右
           アドミ        1200ダ
      2                                             牝
      2
           ビアーレ      1200ダ
      3                                             牡
      16
           エヒト        2000芝
      16                                            牡
    """
    result = parse_races(text, tmp_path / "dummy.pdf")
    race_info, horses = result.races[0]
    numbers = sorted(horse.number for horse in horses)
    assert numbers == list(range(1, 17))
    assert any(horse.name.startswith("Unknown-") for horse in horses)
    assert race_info.track == "中山"
