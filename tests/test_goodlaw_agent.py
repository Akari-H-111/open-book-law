"""The agent loop with a fake model, the good-law conditions, and H7 to H10 on synthetic run files."""

import json
import sqlite3

import numpy as np
import pytest

from open_book_law.agent import loop, tools
from open_book_law.experiments import us_agent, us_goodlaw, us_hypotheses, us_retrieval
from open_book_law.us import authority, goodlaw

QUESTION = {"qid": "q", "query": "Is it so?", "split": "overruled", "answer": "A", "superseded_rule": "B"}
QUESTION |= {f"choice_{letter}": f"option {letter}" for letter in "abcd"}
SEARCH = '{"tool": "search", "args": {"query": "rule", "library": "scotus"}}'
CHECK = '{"tool": "check_status", "args": {"citation": "100 U.S. 1", "as_of_date": "2026-11-03"}}'


def run_fake(replies, statuses="good"):
    calls, seen = [], []

    def generate(messages):
        seen.append(list(messages))
        return replies[len(seen) - 1]

    def fake_tool(name):
        def tool(**args):
            calls.append((name, args))
            return {"status": statuses} if name == "check_status" else {"results": []}

        return tool

    tool_set = {name: fake_tool(name) for name in loop.ARGS}
    forced = []

    def force_answer(messages):
        forced.append(messages)
        return "C"

    result = loop.run_question(QUESTION, "scotus", "2026-11-03", tool_set, generate, force_answer)
    return result, calls, seen, forced


def test_correct_calls_then_an_answer():
    result, calls, seen, forced = run_fake([SEARCH, CHECK, '{"answer": "A"}'])
    assert result["predicted"] == "A"
    assert [name for name, _ in calls] == ["search", "check_status"]
    assert (result["tool_calls"], result["malformed"], result["turns"]) == (2, 0, 3)
    assert not result["exhausted"] and not forced
    assert seen[1][-1]["content"].startswith("Result: ")


def test_a_malformed_call_gets_a_correction_and_counts():
    wrong_args = '{"tool": "read", "args": {"wrong": "x"}}'
    result, calls, seen, _ = run_fake(["not json", wrong_args, '{"answer": "B"}'])
    assert result["predicted"] == "B"
    assert result["malformed"] == 2 and not calls
    assert seen[1][-1]["content"] == loop.CORRECTION


def test_the_budget_counts_tool_calls_refuses_the_sixth_and_forces_an_answer():
    result, calls, _, forced = run_fake([SEARCH] * 20)
    assert len(calls) == loop.BUDGET == 5
    assert result["exhausted"] and result["predicted"] == "C" and result["stop"] == "tool_budget"
    assert (result["tool_calls"], result["turns"], result["malformed"]) == (5, 6, 0)
    assert result["trace"][-1]["kind"] == "refused" and "result" not in result["trace"][-1]
    assert forced[0][-1]["content"] == loop.FORCE


def test_the_model_may_answer_after_its_fifth_tool_call():
    result, calls, _, forced = run_fake([SEARCH] * 5 + ['{"answer": "D"}'])
    assert len(calls) == 5 and result["predicted"] == "D" and not result["exhausted"] and not forced


def test_malformed_replies_do_not_use_the_tool_budget():
    result, calls, _, _ = run_fake(["bad", "bad", *[SEARCH] * 5, '{"answer": "A"}'])
    assert len(calls) == 5 and result["malformed"] == 2 and result["predicted"] == "A"


def test_the_third_malformed_reply_ends_the_question():
    result, calls, _, forced = run_fake(["{bad"] * 20)
    assert (result["turns"], result["malformed"], result["stop"]) == (3, 3, "malformed_limit")
    assert result["exhausted"] and not calls and forced


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ('{"answer": "D"}', "answer"),
        ('Sure: {"answer": "D"}', "answer"),
        ('{"answer": "E"}', "malformed"),
        ('{"answer": "A", "extra": 1}', "malformed"),
        ('{"tool": "delete", "args": {}}', "malformed"),
        ('{"tool": "read", "args": {"passage_id": 7}}', "malformed"),
        ('{"tool": [], "args": {}}', "malformed"),
        ('{"tool": {"a": 1}, "args": {}}', "malformed"),
        ('{"tool": null, "args": {}}', "malformed"),
        ('{"tool": "read", "args": {"passage_id": "7"}}', "tool"),
        ('{"answer": "A"} {"answer": "B"}', "malformed"),
        ("", "malformed"),
    ],
)
def test_parse_reply(text, kind):
    assert loop.parse_reply(text)[0] == kind


def test_ignored_status_needs_an_overruled_result_and_the_old_rule():
    result = run_fake([CHECK, '{"answer": "B"}'], statuses="overruled")[0]
    assert result["saw_overruled"]
    record = us_agent.score(QUESTION, result)
    assert record["superseded"] == 1.0 and record["ignored_status"] and record["correct"] == 0.0
    followed = run_fake([CHECK, '{"answer": "A"}'], statuses="overruled")[0]
    assert not us_agent.score(QUESTION, followed)["ignored_status"]
    still_good = run_fake([CHECK, '{"answer": "B"}'], statuses="good")[0]
    assert not us_agent.score(QUESTION, still_good)["ignored_status"]


def test_summary_counts_turns():
    results = [run_fake(["bad", SEARCH, '{"answer": "A"}'])[0], run_fake([SEARCH] * 6)[0]]
    summary = us_agent.summarize_agent([us_agent.score(QUESTION, r) for r in results])
    assert summary["malformed_share"] == pytest.approx(100 / 9)
    assert summary["valid_turn_share"] == pytest.approx(800 / 9)
    assert summary["budget_exhausted"] == 1 and summary["tool_calls_per_question"] == 3
    assert (summary["tool_call_budget"], summary["malformed_limit"]) == (5, 3)
    assert summary["malformed_limit_hit"] == 0


def make_graph():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cases = [
        {"id": "1", "cite": "100 U.S. 1", "name": "Old v. A", "date": "1900-01-01"},
        {"id": "2", "cite": "400 U.S. 1", "name": "New v. B", "date": "1970-06-01"},
        {"id": "cornell:9-9", "cite": None, "name": "Other v. C", "date": "2000-01-01"},
    ]
    pair = {
        "old_id": "1", "new_id": "2", "new_year": 1970, "in_part": False,
        "old_name": "Old v. A", "old_cite": None, "old_year": 1900,
        "new_name": "New v. B", "new_cite": None,
    }  # fmt: skip
    authority.build(conn, cases, [pair])
    return conn


def test_citator_drops_an_overruled_decision_but_not_before_its_overruling():
    conn = make_graph()
    ranked = ["1:0:0", "2:0:0", "1:0:1", "cornell:9-9:0:0"]
    assert us_goodlaw.citator_top_k(conn, ranked, 2) == ["2:0:0", "cornell:9-9:0:0"]
    assert us_goodlaw.citator_top_k(conn, ranked, 2, as_of="1969-12-31") == ["1:0:0", "2:0:0"]
    assert us_goodlaw.citator_top_k(conn, ranked, 2, as_of="1970-06-01") == ["2:0:0", "cornell:9-9:0:0"]


def test_the_citator_reads_deep_and_the_summary_counts_questions_with_fewer_than_k_passages(monkeypatch):
    monkeypatch.setattr(goodlaw, "read_questions", lambda conn=None: ([], []))
    conn = make_graph()
    deep = ["1:0:0"] * 50 + ["cornell:9-9:0:0", "2:0:0"]
    assert us_goodlaw.citator_top_k(conn, deep, 2) == ["cornell:9-9:0:0", "2:0:0"]
    assert us_goodlaw.citator_top_k(conn, deep[:50], 2) == []
    q = {"qid": "q", "current_rule": "A", "superseded_rule": "B"}
    records = []
    for docids in (["x", "y"], ["x"], []):
        record = {"predicted": "A", "docids": docids, "correct": 1.0, "truncated": False, "label_mass": 1.0}
        records.append(record | us_goodlaw.outcome_fields(record, q))
    assert [r["n_passages"] for r in records] == [2, 1, 0]
    assert us_goodlaw.summarize_goodlaw(records, k=2)["questions_with_fewer_than_k"] == 2
    assert "questions_with_fewer_than_k" not in us_goodlaw.summarize_goodlaw(records)


def test_the_date_test_has_two_forms_with_different_correct_options():
    q = {"qid": "q", "query": "What is the rule?", "answer": "A", "superseded_rule": "B", "new_year": 1970}
    before, today = (us_goodlaw.date_form(q, c) for c in us_goodlaw.DATE_TEST)
    assert before["query"] == "As of 1969: What is the rule?" and before["answer"] == "B"
    assert today["query"] == f"As of {goodlaw.TODAY}: What is the rule?" and today["answer"] == "A"
    shared = {"qid": "1-1", "old_id": "o", "new_id": "n", "old_passage": "OLD", "new_passage": "NEW"}
    shared |= {"old_name": "Old", "old_year": 1900, "new_name": "New", "new_year": 1970}
    for condition in us_goodlaw.DATE_TEST:
        assert us_goodlaw.fixed_context(shared, condition) == us_goodlaw.fixed_context(shared, "both-dated")


def test_both_forms_correct_counts_questions_right_in_both_runs():
    def run(*correct):
        return {"per_query": [{"qid": f"q{i}", "correct": float(c)} for i, c in enumerate(correct)]}

    assert goodlaw.both_forms_correct(run(1, 1, 0, 1), run(1, 0, 0, 1)) == 50.0
    with pytest.raises(ValueError, match="different questions"):
        goodlaw.both_forms_correct(run(1), run(1, 1))


def test_dense_scotus_may_create_its_store_but_a_smoke_run_may_not():
    def may(*extra, dataset="scotus"):
        args = us_retrieval.parse_args(["--dataset", dataset, "--retriever", "e5-small", *extra])
        return us_retrieval.may_encode_store(args)

    assert may()
    assert not may("--limit", "5")
    assert not may("--split", "validation", dataset="mbe")
    assert not may("--library", "doctrine", dataset="mbe")
    assert may(dataset="mbe")


def test_case_of_keeps_the_colon_of_a_cornell_id():
    assert goodlaw.case_of("cornell:19-1392:0:5") == "cornell:19-1392"
    assert goodlaw.case_of("123:1:2") == "123"


def test_note_names_the_overruling_decision_only_on_an_overruled_decision():
    conn = make_graph()
    assert us_goodlaw.with_note(conn, "1:0:0", "text") == "[Overruled by New v. B (1970).]\ntext"
    assert us_goodlaw.with_note(conn, "2:0:0", "text") == "text"


def test_outcome_classes():
    q = {"qid": "q", "current_rule": "A", "superseded_rule": "B"}
    assert us_goodlaw.outcome_fields({"predicted": "A", "docids": []}, q)["outcome"] == "current"
    assert us_goodlaw.outcome_fields({"predicted": "B", "docids": []}, q)["outcome"] == "superseded"
    assert us_goodlaw.outcome_fields({"predicted": "B", "docids": []}, q)["superseded"] == 1.0
    assert us_goodlaw.outcome_fields({"predicted": "C", "docids": []}, q)["outcome"] == "other_wrong"


def test_passage_order_is_balanced_seeded_and_shared_by_both_conditions():
    firsts = [us_goodlaw.old_goes_first(f"{i}-1") for i in range(400)]
    assert 160 < sum(firsts) < 240
    assert firsts == [us_goodlaw.old_goes_first(f"{i}-1") for i in range(400)]
    q = {"qid": "1-1", "old_id": "o", "new_id": "n", "old_passage": "OLD", "new_passage": "NEW"}
    q |= {"old_name": "Old", "old_year": 1900, "new_name": "New", "new_year": 1970}
    assert us_goodlaw.fixed_context(q, "both")[0] == us_goodlaw.fixed_context(q, "both-dated")[0]


def test_only_the_dated_condition_shows_names_and_years():
    q = {"qid": "1-1", "old_id": "o", "new_id": "n", "old_passage": "OLD", "new_passage": "NEW"}
    q |= {"old_name": "Old", "old_year": 1900, "new_name": "New", "new_year": 1970}
    order, texts = us_goodlaw.fixed_context(q, "both")
    assert set(order) == {"o", "n"} and texts["o"][0] == "OLD"
    assert us_goodlaw.fixed_context(q, "both-dated")[1]["o"][0] == "Old (1900):\nOLD"
    assert us_goodlaw.fixed_context(q, "closed")[0] == []
    assert us_goodlaw.fixed_context(q, "old-only")[0] == ["o"]
    assert us_goodlaw.fixed_context(q, "new-only")[0] == ["n"]


def test_a_question_leaves_if_its_overruling_decision_was_overruled_later(tmp_path, monkeypatch):
    conn = make_graph()
    base = {"options": dict(zip("ABCD", "wxyz", strict=True)), "question": "Q", "current_rule": "A"}
    rows = [base | {"pair_id": "a", "new_id": "1"}, base | {"pair_id": "b", "new_id": "2"}]
    path = tmp_path / "questions.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(goodlaw, "QUESTIONS", path)
    kept, left_out = goodlaw.read_questions(conn)
    assert [q["qid"] for q in kept] == ["b"] and [q["qid"] for q in left_out] == ["a"]
    assert kept[0]["choice_a"] == "w" and kept[0]["answer"] == "A" and kept[0]["query"] == "Q"


def test_ranks_use_all_scores_and_a_tie_does_not_outrank():
    rows = [
        {"id": "o:0:0", "case_id": "o", "opinion_type": "dissent"},
        {"id": "n:0:0", "case_id": "n", "opinion_type": "majority"},
        {"id": "x:0:0", "case_id": "x", "opinion_type": "majority"},
        {"id": "n:0:1", "case_id": "n", "opinion_type": "majority"},
    ]
    q = {"qid": "q", "old_id": "o", "new_id": "n"}
    scores = [[0.9, 0.1, 0.5, 0.2], [0.1, 0.1, 0.5, 0.9], [0.5, 0.5, 0.1, 0.1]]
    scores = [np.array(row) for row in scores]
    _, records = us_retrieval.rank_scotus([q, q, q], rows, lambda i: scores[i])
    assert (records[0]["rank_old"], records[0]["rank_new"], records[0]["old_outranks_new"]) == (1, 3, 1.0)
    assert (records[1]["rank_old"], records[1]["rank_new"], records[1]["old_outranks_new"]) == (3, 1, 0.0)
    assert records[2]["old_outranks_new"] == 0.0
    assert records[0]["types_top10"] == {"dissent": 1, "majority": 3}


def test_scotus_runs_go_to_the_downstream_suite_and_keep_their_own_library():
    args = us_retrieval.parse_args(["--dataset", "scotus", "--retriever", "bm25"])
    assert us_retrieval.suite_for(args) == "us_downstream"
    assert us_retrieval.make_config(args, [])["library"] == "scotus"
    smoke = us_retrieval.parse_args(["--dataset", "scotus", "--retriever", "bm25", "--limit", "5"])
    assert us_retrieval.suite_for(smoke) == "us_smoke"


def test_tools_return_case_details_and_errors():
    conn = make_graph()
    made = tools.make_tools(["1:0:0", "2:0:0"], ["old words " * 50, "new words"], lambda query: [1, 0], conn)
    found = made["search"]("words", "scotus")["results"]
    assert found[0] == {
        "passage_id": "2:0:0",
        "case": "New v. B",
        "year": "1970",
        "citation": "400 U.S. 1",
        "snippet": "new words",
    }
    assert len(found[1]["snippet"].split()) == 40
    assert "error" in made["read"]("nope")
    assert made["read"]("2:0:0") == {"text": "new words"}
    assert "error" in made["check_status"]("100 U.S. 1", "soon")
    assert made["check_status"]("100 U.S. 1", "1950-01-01")["status"] == "good"
    assert made["check_status"]("100 U.S. 1", "1980-01-01")["status"] == "overruled"
    assert made["check_status"]("100 U.S. 1", "1800-01-01")["status"] == "not_decided"


def good_run(run_id, condition, superseded, reader="llama8", retriever=None, k=None, dataset="scotus"):
    config = {"condition": condition, "reader": reader, "retriever": retriever, "k": k, "dataset": dataset}
    per_query = [{"qid": f"q{i}", "group": "g", "superseded": float(v)} for i, v in enumerate(superseded)]
    return {"run_id": run_id, "utc_time": run_id, "config": config, "per_query": per_query, "metrics": {}}


def write_runs(root, suite, runs):
    (root / suite).mkdir(parents=True, exist_ok=True)
    for run in runs:
        (root / suite / f"{run['run_id']}.json").write_text(json.dumps(run))


def fake_selection(monkeypatch, dense="e5-small", k=3, best_open="qwen3"):
    chosen = {
        "best_dense": {"status": "selected", "value": dense},
        "k": {"status": "selected", "value": k},
        "best_real_library": {"status": "pending"},
        "best_open": {"status": "selected", "value": best_open},
    }
    monkeypatch.setattr(us_hypotheses.us_select, "make_selection", lambda runs_dir=None: chosen)


def test_h7_compares_the_superseded_rate_with_closed_book(tmp_path):
    many = [good_run("a", "old-only", [1] * 60 + [0] * 40), good_run("b", "closed", [0] * 100)]
    write_runs(tmp_path, "us_goodlaw", many)
    test = us_hypotheses.make_summary(tmp_path)["tests"]["H7"]
    assert test["status"] == "done" and test["difference"] == 60 and test["a_only"] == 60


def test_h7_fails_when_the_difference_is_small(tmp_path):
    runs = [good_run("a", "old-only", [1] * 15 + [0] * 85), good_run("b", "closed", [1] * 10 + [0] * 90)]
    write_runs(tmp_path, "us_goodlaw", runs)
    assert us_hypotheses.make_summary(tmp_path)["tests"]["H7"]["verdict"] == "not supported"


def test_h8_compares_retrieved_and_citator_at_the_selected_settings(tmp_path, monkeypatch):
    fake_selection(monkeypatch)
    settings = {"retriever": "e5-small", "k": 3}
    runs = [
        good_run("a", "retrieved", [1] * 30 + [0] * 70, **settings),
        good_run("b", "citator", [0] * 100, **settings),
        good_run("c", "citator", [1] * 30 + [0] * 70, retriever="bm25", k=3),
    ]
    write_runs(tmp_path, "us_goodlaw", runs)
    test = us_hypotheses.make_summary(tmp_path)["tests"]["H8"]
    assert test["difference"] == 30 and test["runs"] == ["a", "b"]


def scotus_run(wins, total, retriever="e5-small"):
    per_query = [{"qid": f"q{i}", "old_outranks_new": float(i < wins)} for i in range(total)]
    config = {"dataset": "scotus", "retriever": retriever}
    return {"run_id": f"s{wins}", "utc_time": "t", "config": config, "per_query": per_query, "metrics": {}}


def test_h9_needs_the_wilson_bound_above_30_percent():
    strong = us_hypotheses.apply_rules({"H9": us_hypotheses.share_test(scotus_run(60, 100))})["H9"]
    assert strong["verdict"] == "supported" and strong["low"] > 30 and strong["p"] < 0.05
    near = us_hypotheses.apply_rules({"H9": us_hypotheses.share_test(scotus_run(36, 100))})["H9"]
    assert near["difference"] == 36 and near["low"] < 30 and near["verdict"] == "not supported"


def test_h9_binomial_p_is_exact():
    assert us_hypotheses.share_test(scotus_run(2, 2))["p"] == pytest.approx(0.09)
    assert us_hypotheses.share_test(scotus_run(0, 2))["p"] == pytest.approx(1.0)


def agent_run(run_id, dataset, superseded, valid=100.0, split="all", reader="qwen3"):
    run = good_run(run_id, None, superseded, reader=reader, retriever="e5-small", dataset=dataset)
    run["config"] |= {"split": split}
    run["metrics"] = {"all": {"valid_turn_share": valid}}
    return run


def test_h10_compares_retrieved_with_the_agent(tmp_path, monkeypatch):
    fake_selection(monkeypatch)
    retrieved = good_run("r", "retrieved", [1] * 40 + [0] * 60, reader="qwen3", retriever="e5-small", k=3)
    write_runs(tmp_path, "us_goodlaw", [retrieved])
    agents = [agent_run("v", "mbe", [0], split="validation"), agent_run("g", "scotus", [1] * 10 + [0] * 90)]
    write_runs(tmp_path, "us_agent", agents)
    test = us_hypotheses.make_summary(tmp_path)["tests"]["H10"]
    assert test["difference"] == 30 and test["runs"] == ["r", "g"]


def test_h10_is_not_testable_under_80_percent_of_valid_turns_and_stays_in_the_family(tmp_path, monkeypatch):
    fake_selection(monkeypatch)
    write_runs(tmp_path, "us_agent", [agent_run("v", "mbe", [0], valid=79.9, split="validation")])
    tests = us_hypotheses.make_summary(tmp_path)["tests"]
    assert tests["H10"]["verdict"] == us_hypotheses.NOT_TESTABLE
    assert len(tests) == 11


def test_h10_at_exactly_80_percent_is_testable_and_pending_without_runs(tmp_path, monkeypatch):
    fake_selection(monkeypatch)
    write_runs(tmp_path, "us_agent", [agent_run("v", "mbe", [0], valid=80.0, split="validation")])
    assert us_hypotheses.make_summary(tmp_path)["tests"]["H10"]["verdict"] == "pending"


def test_h10_is_pending_without_a_validation_run(tmp_path, monkeypatch):
    fake_selection(monkeypatch)
    write_runs(tmp_path, "us_agent", [agent_run("g", "scotus", [0])])
    assert us_hypotheses.make_summary(tmp_path)["tests"]["H10"]["verdict"] == "pending"


def test_a_not_testable_test_counts_in_holm_and_completes_the_family():
    done = {"status": "done", "difference": 50, "low": 40, "high": 60, "p": 0.01}
    tests = {key: dict(done) for key in us_hypotheses.THRESHOLDS}
    tests["H10"] = {"status": us_hypotheses.NOT_TESTABLE}
    ruled = us_hypotheses.apply_rules(tests)
    assert ruled["H1"]["p_holm"] == pytest.approx(0.11)
    assert ruled["H1"]["verdict"] == "not supported"
    assert ruled["H10"]["verdict"] == us_hypotheses.NOT_TESTABLE
    assert ruled["H1"]["family_complete"]


def test_h9_and_h10_pending_keep_the_family_incomplete(tmp_path):
    summary = us_hypotheses.make_summary(tmp_path)
    assert summary["tests"]["H9"]["verdict"] == summary["tests"]["H10"]["verdict"] == "pending"
    assert not summary["tests"]["H1"]["family_complete"]
