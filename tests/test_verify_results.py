from keiba_simulator.verify_results import extract_race_number, parse_results_text


def test_parse_results_text_extracts_rows() -> None:
    text = """
 2026年1月24日（土曜） 1回 中山8日 1R
   1    8 16 ムーンブランシュ                                  牝3       55.0 木幡巧也                     1:13.2              2-2              37.3   484 +6 牧光二        1
   2    7 14 タヤスロレンヌ                                   牝3       55.0 江田照男                     1:14.1 ５            9-9              37.8   460 -2 岩戸孝樹       7
   3    1 2 アドミ                                        牝3       55.0 菅原明良                     1:14.1 クビ           5-5              38.1   448 -6 中川公成       2
    """
    rows = parse_results_text(text)
    assert [row.finish for row in rows] == [1, 2, 3]
    assert [row.horse_no for row in rows] == [16, 14, 2]
    assert rows[0].horse_name == "ムーンブランシュ"
    assert rows[2].popularity == 2


def test_extract_race_number_prefers_filename() -> None:
    text = "2026年1月24日（土曜） 1回 中山8日 11R\n"
    assert extract_race_number(text, "2026年1月24日 4レース.pdf") == 4


def test_extract_race_number_from_header_when_filename_missing() -> None:
    text = "2026年1月24日（土曜） 1回 中山8日 11R\n"
    assert extract_race_number(text, "race_result.pdf") == 11
