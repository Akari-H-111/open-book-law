import json

from open_book_law import runlog


def test_read_partial_cuts_a_broken_last_line_so_that_later_lines_stay_valid(tmp_path):
    path = tmp_path / "partial.jsonl"
    path.write_text('{"qid": "a"}\n{"qid": "b', encoding="utf-8")
    assert list(runlog.read_partial(path)) == ["a"]
    with open(path, "a", encoding="utf-8") as f:
        runlog.append_record(f, {"qid": "c"})
    assert [json.loads(line)["qid"] for line in path.read_text(encoding="utf-8").splitlines()] == ["a", "c"]
    assert list(runlog.read_partial(path)) == ["a", "c"]
