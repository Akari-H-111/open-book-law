"""The error sample (section 11) and the label audit (section 9), with a fake Claude CLI."""

import json
import stat
import sys

import pytest

from open_book_law import runlog
from open_book_law.prep import us_error_sample, us_label_audit

FAKE_CLI = """#!{python}
import json, sys
argv = sys.argv[1:]
model = argv[argv.index("--model") + 1]
prompt = sys.stdin.read()
with open({log!r}, "a") as f:
    f.write(json.dumps({{"model": model, "prompt": prompt}}) + "\\n")
answers = json.load(open({answers!r}))
print(json.dumps({{"structured_output": answers[model], "usage": {{}}, "total_cost_usd": 0}}))
"""


def fake_cli(tmp_path, answers):
    """A script that answers each model with a fixed dict, and logs every call. Returns (path, log path)."""
    (tmp_path / "answers.json").write_text(json.dumps(answers))
    log = tmp_path / "calls.log"
    path = tmp_path / "fake_claude"
    path.write_text(
        FAKE_CLI.format(python=sys.executable, log=str(log), answers=str(tmp_path / "answers.json"))
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path), log


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def question(qid, gold=("g1",)):
    q = {"qid": qid, "query": f"Facts of {qid}?", "answer": "B", "gold": set(gold), "split": "test"}
    return q | {f"choice_{letter}": f"option {letter}" for letter in "abcd"}


def reader_record(qid, correct, docids=("d1", "d2")):
    return {
        "qid": qid,
        "correct": correct,
        "gold": "B",
        "predicted": "B" if correct else "C",
        "docids": list(docids),
    }


LABEL = {"label": "reading", "quote": " ".join(f"w{i}" for i in range(40)), "reason": "It | was there.\nYes."}


def test_the_sample_holds_only_wrong_answers_and_is_the_same_on_every_draw():
    records = [reader_record(f"q{i}", correct=i % 3 == 0) for i in range(60)]
    first = us_error_sample.draw_sample(records, 10)
    assert first == us_error_sample.draw_sample(list(reversed(records)), 10)
    assert len(first) == 10 and not any(r["correct"] for r in first)
    assert len(us_error_sample.draw_sample(records, 1000)) == 40


def test_labels_are_asked_once_per_answer_and_a_stopped_run_continues(tmp_path):
    binary, log = fake_cli(tmp_path, {us_error_sample.MODEL: LABEL})
    picked = [reader_record("a", False), reader_record("b", False)]
    questions = {q: question(q) for q in "ab"}
    texts = {"d1": ("first passage", "wex"), "d2": ("second passage", "caselaw")}
    path = tmp_path / "labels.jsonl"
    answers = runlog.read_partial(path)
    with open(path, "a", encoding="utf-8") as file:
        rows = us_error_sample.label_sample(picked[:1], questions, texts, answers, file, binary)
    assert [r["qid"] for r in rows] == ["a"] and len(calls(log)) == 1
    prompt = calls(log)[0]["prompt"]
    assert "[d1] first passage" in prompt and "B. option b" in prompt and "The model chose: C" in prompt
    answers = runlog.read_partial(path)
    with open(path, "a", encoding="utf-8") as file:
        rows = us_error_sample.label_sample(picked, questions, texts, answers, file, binary)
    assert [r["qid"] for r in rows] == ["a", "b"] and len(calls(log)) == 2
    assert rows[0]["docids"] == ["d1", "d2"]


def test_a_cli_failure_leaves_the_answer_out_and_goes_on(tmp_path):
    picked = [reader_record("a", False)]
    texts = {"d1": ("t", "wex"), "d2": ("t", "wex")}
    with open(tmp_path / "labels.jsonl", "a", encoding="utf-8") as file:
        rows = us_error_sample.label_sample(
            picked, {"a": question("a")}, texts, {}, file, str(tmp_path / "missing")
        )
    assert rows == []


def test_the_review_table_has_blank_columns_and_short_quotations():
    row = LABEL | {"qid": "a", "docids": ["d1", "d2"]}
    lines = us_error_sample.review_table([row, row | {"qid": "0"}]).splitlines()
    assert "not reviewed" in lines[0]
    assert lines[5].startswith("| 0 |") and lines[6].startswith("| a |")
    cells = lines[6].split(" | ")
    assert cells[1] == "d1, d2" and cells[2] == "reading"
    assert cells[3] == "It / was there. Yes." and cells[4] == " ".join(f"w{i}" for i in range(25))
    assert lines[6].endswith("|  |  |")
    assert len(lines[6].split("|")) == len(lines[3].split("|"))


def test_error_sample_main_writes_the_review_file_and_a_summary(tmp_path, monkeypatch):
    binary, _ = fake_cli(tmp_path, {us_error_sample.MODEL: LABEL})
    records = [reader_record(f"q{i}", correct=False) for i in range(5)]
    run = {"run_id": "r1", "per_query": records}
    monkeypatch.setattr(us_error_sample, "find_reader_run", lambda: run)
    monkeypatch.setattr(
        us_error_sample.samples, "load_questions", lambda *a: [question(r["qid"]) for r in records]
    )
    monkeypatch.setattr(
        us_error_sample, "read_passages", lambda dataset, wanted: {d: ("text", "wex") for d in wanted}
    )
    monkeypatch.setattr(us_error_sample, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(us_error_sample, "REVIEW", tmp_path / "docs" / "review" / "error_sample.md")
    monkeypatch.setattr(us_error_sample, "SUMMARY", tmp_path / "summary.json")
    us_error_sample.main(["--claude-bin", binary, "--size", "3"])
    assert not (tmp_path / "summary.json").exists() and not (tmp_path / "docs").exists()
    assert (tmp_path / "work" / "smoke_review.md").exists()
    monkeypatch.setattr(us_error_sample, "SIZE", 5)
    us_error_sample.main(["--claude-bin", binary, "--size", "5"])
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["labelled"] == 5 and summary["counts"] == {"reading": 5} and summary["run"] == "r1"
    assert len((tmp_path / "docs" / "review" / "error_sample.md").read_text().splitlines()) == 10


def test_judges_see_numbered_passages_and_out_of_range_numbers_are_dropped(tmp_path):
    first, second = us_label_audit.JUDGES
    binary, log = fake_cli(tmp_path, {first: {"relevant": [1, 7, -1]}, second: {"relevant": []}})
    texts = {"d1": ("one", "wex"), "d2": ("two", "wex")}
    q = question("a")
    with open(tmp_path / "j.jsonl", "a", encoding="utf-8") as file:
        found = us_label_audit.judge_question(q, ["d1", "d2"], texts, {}, file, binary)
    assert found == {first: ["d2"], second: []}
    assert "[0] one" in calls(log)[0]["prompt"] and "Official answer: B" in calls(log)[0]["prompt"]
    broken = str(tmp_path / "missing")
    with open(tmp_path / "j.jsonl", "a", encoding="utf-8") as file:
        assert us_label_audit.judge_question(q, ["d1"], texts, {}, file, broken) is None


def test_the_audit_summary_compares_judges_and_gold_recall():
    first, second = us_label_audit.JUDGES
    records = [
        {
            "qid": "a",
            "pool": ["x", "y"],
            "relevant": {first: ["x"], second: ["x"]},
            "gold_hit": {"bm25": True},
        },
        {"qid": "b", "pool": ["x", "y"], "relevant": {first: ["y"], second: []}, "gold_hit": {"bm25": False}},
    ]
    summary = us_label_audit.summarize_audit(records, ["bm25"])
    assert summary["label"] == "silver" and summary["questions"] == 2
    assert summary["passage_agreement"] == 75.0 and summary["both_judges_found_one"] == 50.0
    assert summary[f"judged_relevant_{first}"] == 100.0 and summary[f"judged_relevant_{second}"] == 50.0
    assert summary["gold_hit_top10_bm25"] == 50.0


def test_label_audit_main_writes_a_smoke_run(tmp_path, monkeypatch):
    first, second = us_label_audit.JUDGES
    binary, _ = fake_cli(tmp_path, {first: {"relevant": [0]}, second: {"relevant": [0, 1]}})
    questions = [question(f"q{i}", gold=[f"g{i}"]) for i in range(4)]
    ranked = {q["qid"]: [f"g{q['qid'][1:]}", "other"] for q in questions}
    runs = [
        {"run_id": name, "config": {"dataset": "mbe", "retriever": name, "library": "full"}}
        for name in ("bm25", "e5")
    ]
    monkeypatch.setattr(us_label_audit, "make_selection", lambda: {"best_dense": {"value": "e5"}})
    monkeypatch.setattr(us_label_audit.runlog, "load_runs", lambda suite: runs)
    monkeypatch.setattr(us_label_audit.runlog, "read_rankings", lambda rid: (ranked, 2))
    monkeypatch.setattr(
        us_label_audit.samples,
        "load_questions",
        lambda dataset, split: questions[:2] if split == "test" else questions[2:],
    )
    monkeypatch.setattr(us_label_audit.samples, "data_files", lambda dataset: [])
    monkeypatch.setattr(
        us_label_audit, "read_passages", lambda dataset, wanted: {d: ("text", "wex") for d in wanted}
    )
    monkeypatch.setattr(us_label_audit, "WORK_DIR", tmp_path / "work")
    written = {}
    monkeypatch.setattr(us_label_audit.runlog, "write_run", lambda *args: written.update(args=args) or "path")
    us_label_audit.main(["--claude-bin", binary, "--size", "3"])
    suite, config, _, _, metrics, records = written["args"][:6]
    assert (
        suite == "us_smoke"
        and config["size"] == 3
        and config["retrieval_runs"] == {"bm25": "bm25", "e5": "e5"}
    )
    assert len(records) == 3 and metrics["questions_missing"] == 0
    assert metrics["all"]["gold_hit_top10_bm25"] == 100.0
    with pytest.raises(SystemExit):
        monkeypatch.setattr(us_label_audit.runlog, "load_runs", lambda suite: runs[:1])
        us_label_audit.main(["--claude-bin", binary, "--size", "3"])
