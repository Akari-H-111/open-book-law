from open_book_law.prep.caselaw import (
    case_from_cornell,
    case_from_json,
    parse_long_date,
    split_passages,
    word_count,
)
from open_book_law.prep.citations import reference_cites


def test_paragraphs_merge_up_to_the_target_and_keep_their_place():
    short = "word " * 60
    long = "word " * 400
    case = {
        "id": "7",
        "opinions": [
            {"type": "majority", "text": "\n".join([short, short, short, "", long, short])},
            {"type": "dissent", "text": short},
        ],
    }
    passages = split_passages(case)
    assert [(p["opinion_type"], p["position"], len(p["text"].split())) for p in passages] == [
        ("majority", 0, 120),
        ("majority", 1, 60),
        ("majority", 2, 400),
        ("majority", 3, 60),
        ("dissent", 0, 60),
    ]
    assert passages[1]["id"] == "7:0:1"


def test_case_from_json_keeps_official_cite_and_handles_missing_fields():
    record = {
        "id": 5,
        "name_abbreviation": "Slocomb",
        "decision_date": "1840-01",
        "citations": [
            {"type": "nominative", "cite": "14 Pet. 60"},
            {"type": "official", "cite": "39 U.S. 60"},
        ],
        "casebody": {"opinions": [{"text": "Some words here.", "type": "majority"}]},
    }
    case = case_from_json(record)
    assert (case["id"], case["cite"], case["cites_to"], case["source"]) == ("5", "39 U.S. 60", [], "cap")
    assert word_count(case) == 3


PAGE = """<title>TRUMP v. SLAUGHTER | Supreme Court | US Law</title>
<div id="writing-25-332_SYLLABUS"><p class="notice jy-both">NOTE: skip</p>
<p class="normal">Syllabus text.</p></div>
<p class="opiniondates">Decided June 29, 2026</p>
<a id="writing-25-332_OPINION_4"></a><p class="scusnameplate">SUPREME COURT</p><p class="rule">___</p>
<p class="normal">The <em>first</em> para.</p><p class="normal">Second&nbsp;para.</p>
<a id="writing-25-332_DISSENT_5"></a><p class="normal">I dissent.</p>
<div id="tab_default_2"><p>Footer that is not an opinion.</p></div>"""


def test_cornell_page_gives_sections_date_and_source():
    case = case_from_cornell(PAGE, "25-332", None)
    assert case["id"] == "cornell:25-332"
    assert case["date"] == "2026-06-29"
    assert case["name"] == "Trump v. Slaughter"
    assert case["head_matter"].startswith("Syllabus text.")
    assert "skip" not in case["head_matter"]
    assert [(o["type"], o["text"]) for o in case["opinions"]] == [
        ("majority", "The first para.\nSecond para."),
        ("dissent", "I dissent."),
    ]
    assert case["source"].endswith("/25-332")


def test_cornell_page_with_another_layout_gives_none():
    assert case_from_cornell("<html><p>no anchors</p></html>", "25-332", None) is None


def test_long_dates():
    assert parse_long_date("Apr. 20, 2020") == "2020-04-20"
    assert parse_long_date("June 24, 2022") == "2022-06-24"


def test_reference_uses_printed_cites_and_ignores_head_matter_and_other_reporters():
    case = {
        "cites_to": [
            {"cite": "377 U. S. 271", "reporter": "U.S.", "opinion_index": 0, "paths": ["/us/377/0403-01"]},
            {"cite": "2 Wheaton 27", "reporter": "Wheat.", "opinion_index": 0, "paths": []},
            {"cite": "3 Wall, 9", "reporter": "Wall,", "opinion_index": 0, "paths": []},
            {"cite": "22 Howard, 127", "reporter": "Howard", "opinion_index": 0, "paths": []},
            {"cite": "1 U. S. 2", "reporter": "U.S.", "opinion_index": -1, "paths": []},
            {"cite": "7 How. 12", "reporter": "How. (Miss.)", "opinion_index": 0, "paths": []},
            {"cite": "garbled", "reporter": "U.S.", "opinion_index": 0, "paths": []},
        ]
    }
    cites, unreadable = reference_cites(case, 0)
    assert cites == {"377 U.S. 271", "15 U.S. 27", "70 U.S. 9", "63 U.S. 127"}
    assert unreadable == ["garbled"]
