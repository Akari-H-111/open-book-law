"""Selection, hypothesis verdicts and reader targets, on synthetic run files."""

import json

from open_book_law.experiments import us_finetune, us_hypotheses, us_select, us_verdicts


def write_run(runs_dir, suite, run_id, config, records=(), metrics=None, when="2026-11-03T00:00:00+00:00"):
    (runs_dir / suite).mkdir(parents=True, exist_ok=True)
    run = {
        "run_id": run_id,
        "utc_time": when,
        "git": {"commit": "c"},
        "config": config,
        "metrics": metrics or {},
        "per_query": list(records),
    }
    (runs_dir / suite / f"{run_id}.json").write_text(json.dumps(run))


def answers(group, n, right):
    return [{"qid": f"{group}{i}", "group": group, "correct": float(i < right)} for i in range(n)]


def dense_runs(tmp_path, small=3.0, base=4.0):
    for model, value in (("e5-small", small), ("e5-base", base)):
        config = {"dataset": "mbe", "retriever": model, "library": "full"}
        metrics = {"validation": {"hit@100": value}, "all": {"hit@100": 99.0 if model == "e5-small" else 0.0}}
        write_run(tmp_path, "us_retrieval", model, config, metrics=metrics)


def reader_config(split="validation", **settings):
    version = us_select.PROMPT_VERSION
    return {"dataset": "mbe", "reader": "llama8", "split": split, "prompt_version": version, **settings}


def selection_runs(tmp_path):
    dense_runs(tmp_path)
    retrieved = {"condition": "retrieved", "retriever": "e5-base"}
    for k, right in ((1, 40), (3, 50), (5, 50)):
        config = reader_config(k=k, library="real", **retrieved)
        write_run(tmp_path, "us_reader", f"k{k}", config, answers("validation", 100, right))
    write_run(
        tmp_path,
        "us_reader",
        "doc",
        reader_config(k=3, library="doctrine", **retrieved),
        answers("validation", 100, 60),
    )
    write_run(
        tmp_path,
        "us_reader",
        "cases",
        reader_config(k=3, library="cases", **retrieved),
        answers("validation", 100, 30),
    )
    for reader, right in (("qwen3", 45), ("phi4", 55)):
        config = {**reader_config(condition="closed"), "reader": reader}
        write_run(tmp_path, "us_reader", reader, config, answers("validation", 100, right))


def test_selection_is_pending_without_runs(tmp_path):
    selection = us_select.make_selection(tmp_path)
    assert {selection[key]["status"] for key in ("best_dense", "k", "best_real_library", "best_open")} == {
        "pending"
    }


def test_selection_follows_validation_and_ties_go_to_the_smaller_k(tmp_path):
    selection_runs(tmp_path)
    selection = us_select.make_selection(tmp_path)
    assert selection["best_dense"]["value"] == "e5-base"
    assert selection["k"]["value"] == 3
    assert selection["best_real_library"]["value"] == "doctrine"
    assert selection["best_open"]["value"] == "phi4"


def test_selection_ignores_train_and_test_records(tmp_path):
    dense_runs(tmp_path, small=5.0, base=4.0)
    assert us_select.make_selection(tmp_path)["best_dense"]["value"] == "e5-small"
    for reader, right_train, right_validation in (("qwen3", 100, 40), ("phi4", 0, 41)):
        records = answers("train", 100, right_train) + answers("test", 100, right_train)
        records += answers("validation", 100, right_validation)
        config = {**reader_config(condition="closed"), "reader": reader}
        write_run(tmp_path, "us_reader", reader, config, records)
    assert us_select.make_selection(tmp_path)["best_open"]["value"] == "phi4"
    view = us_select.validation_view(json.loads((tmp_path / "us_reader" / "phi4.json").read_text()))
    assert {r["group"] for r in view["records"]} == {"validation"}


def test_a_reader_run_on_a_rollout_ranking_cannot_decide_selection(tmp_path):
    selection_runs(tmp_path)
    early = "2026-11-02T00:00:00+00:00"
    retrieved = {"condition": "retrieved", "retriever": "e5-base", "rollout": True}
    for name, k, library in (("roll_k1", 1, "real"), ("roll_cases", 3, "cases")):
        config = reader_config(k=k, library=library, **retrieved)
        write_run(tmp_path, "us_reader", name, config, answers("validation", 100, 99), when=early)
    selection = us_select.make_selection(tmp_path)
    assert selection["k"]["value"] == 3 and selection["k"]["runs"][1] == "k1"
    assert selection["best_real_library"]["value"] == "doctrine"


def test_a_reader_run_on_a_rollout_ranking_cannot_serve_h1_to_h3(tmp_path):
    selection_runs(tmp_path)
    early = "2026-11-02T00:00:00+00:00"
    shared = {"split": "confirmatory", "condition": "retrieved", "retriever": "e5-base", "k": 3}
    closed = reader_config(split="confirmatory", condition="closed")
    write_run(tmp_path, "us_reader", "cclosed", closed, answers("test", 400, 100))
    config = reader_config(library="doctrine", **shared)
    write_run(tmp_path, "us_reader", "cdoc", config, answers("test", 400, 200))
    config = reader_config(library="doctrine", rollout=True, **shared)
    write_run(tmp_path, "us_reader", "roll", config, answers("test", 400, 399), when=early)
    test = us_hypotheses.make_summary(tmp_path)["tests"]["H1"]
    assert test["runs"] == ["cdoc", "cclosed"] and test["difference"] == 25.0


def test_a_smoke_or_unfrozen_run_cannot_decide_selection(tmp_path):
    config = {**reader_config(condition="closed"), "prompt_version": "old"}
    write_run(tmp_path, "us_reader", "qwen3", {**config, "reader": "qwen3"}, answers("validation", 10, 9))
    write_run(
        tmp_path,
        "us_smoke",
        "phi4",
        {**reader_config(condition="closed"), "reader": "phi4"},
        answers("validation", 10, 9),
    )
    assert us_select.make_selection(tmp_path)["best_open"]["status"] == "pending"


def done(difference, low, p):
    return {"status": "done", "difference": difference, "low": low, "high": difference + 1, "p": p}


def rules(**tests):
    filled = {key: {"status": "pending"} for key in us_hypotheses.THRESHOLDS}
    filled.update(tests)
    return us_hypotheses.apply_rules(filled)


def test_a_verdict_needs_size_interval_and_corrected_test():
    assert rules(H1=done(3.0, 0.5, 0.001))["H1"]["verdict"] == "supported"
    assert rules(H1=done(2.9, 0.5, 0.001))["H1"]["verdict"] == "not supported"
    assert rules(H1=done(4.0, -0.1, 0.001))["H1"]["verdict"] == "not supported"
    uncorrected_only = rules(H1=done(4.0, 0.5, 0.01))["H1"]
    assert uncorrected_only["p_holm"] == 0.11
    assert uncorrected_only["verdict"] == "not supported"


def test_missing_tests_stay_pending_and_the_family_is_marked_incomplete():
    tests = rules(H1=done(4.0, 0.5, 0.001))
    assert tests["H2"]["verdict"] == "pending"
    assert tests["H1"]["family_complete"] is False
    assert tests["H1"]["p_holm"] == 0.011


def test_holm_changes_with_other_results_in_the_family():
    tests = rules(H1=done(4.0, 0.5, 0.004), H2=done(4.0, 0.5, 0.005))
    assert tests["H1"]["p_holm"] == 0.044
    assert tests["H2"]["p_holm"] == 0.05
    assert tests["H1"]["verdict"] == "supported"
    assert tests["H2"]["verdict"] == "not supported"


def test_compare_is_paired_by_question_and_refuses_different_sets():
    a = {"q1": 1.0, "q2": 1.0, "q3": 0.0, "q4": 0.0}
    b = {"q4": 0.0, "q3": 0.0, "q2": 0.0, "q1": 1.0}
    result = us_hypotheses.compare(a, b, "x", "y")
    assert result["difference"] == 25.0
    assert (result["a_only"], result["b_only"], result["p"]) == (1, 0, 1.0)
    assert us_hypotheses.compare(a, {"q1": 1.0}, "x", "y")["status"] == "pending"


def test_hypotheses_are_pending_with_no_runs(tmp_path):
    summary = us_hypotheses.make_summary(tmp_path)
    assert {test["verdict"] for test in summary["tests"].values()} == {"pending"}
    assert "pending" in us_hypotheses.markdown_table(summary)


def test_hypotheses_from_synthetic_runs_include_a_failure(tmp_path):
    selection_runs(tmp_path)
    retrieved = {"condition": "retrieved", "retriever": "e5-base", "k": 3}
    many = 400
    confirmatory = {"split": "confirmatory"}
    for name, config, right in (
        ("closed", {"condition": "closed"}, 100),
        ("gold", {"condition": "gold"}, 300),
        ("cdoc", {"library": "doctrine", **retrieved}, 200),
        ("ccases", {"library": "cases", **retrieved}, 198),
    ):
        write_run(
            tmp_path,
            "us_reader",
            name,
            reader_config(**{**config, **confirmatory}),
            answers("test", many, right),
        )
    tests = us_hypotheses.make_summary(tmp_path)["tests"]
    assert tests["H1"]["verdict"] == "supported"
    assert tests["H1"]["difference"] == 25.0
    assert tests["H2"]["verdict"] == "not supported"
    assert tests["H3"]["verdict"] == "supported"
    assert tests["H5"]["verdict"] == "pending"


def test_rollout_and_finetune_tests_read_their_own_columns(tmp_path):
    settings = {"dataset": "mbe", "retriever": "bm25", "library": "full"}
    hits = [{"qid": f"q{i}", "group": "test", "hit@100": float(i < 100)} for i in range(400)]
    before = [{"qid": f"q{i}", "group": "test", "hit@100": float(i < 10)} for i in range(400)]
    before.append({"qid": "v", "group": "validation", "hit@100": 1.0})
    write_run(tmp_path, "us_retrieval", "base", settings, before)
    write_run(tmp_path, "us_downstream", "roll", {**settings, "rollout": "p", "split": "confirmatory"}, hits)
    records = [
        {
            "qid": f"q{i}",
            "group": "ohio",
            "unseen_group": i < 3,
            "hit@10": float(i < 90),
            "zero_hit@10": float(i < 89),
        }
        for i in range(400)
    ]
    metrics = {"unseen_groups": {"hit@10": 1.0, "zero_hit@10": 2.0}}
    write_run(
        tmp_path,
        "us_finetune",
        "ft",
        {"mode": "eval", "split": "test", "limit": None, "limit_docs": None},
        records,
        metrics,
    )
    summary = us_hypotheses.make_summary(tmp_path)
    assert summary["tests"]["H4a"]["difference"] == 22.5
    assert summary["tests"]["H4a"]["verdict"] == "supported"
    assert summary["tests"]["H6"]["verdict"] == "not supported"
    assert summary["exploratory"]["H6_unseen_groups"]["questions"] == 3
    assert summary["exploratory"]["H6_unseen_groups"]["hit@10"] == 1.0


def test_an_empty_unseen_group_subset_has_no_rate(tmp_path):
    records = [{"qid": "q0", "group": "ohio", "unseen_group": False, "hit@10": 1.0, "zero_hit@10": 0.0}]
    metrics = {"unseen_groups": {"hit@10": 0.0, "zero_hit@10": 0.0}}
    config = {"mode": "eval", "split": "test", "limit": None, "limit_docs": None}
    write_run(tmp_path, "us_finetune", "ft", config, records, metrics)
    unseen = us_hypotheses.make_summary(tmp_path)["exploratory"]["H6_unseen_groups"]
    assert unseen == {"questions": 0, "hit@10": None, "zero_hit@10": None}
    assert us_finetune.summarize([])["hit@10"] is None


def test_reader_targets_apply_the_limits_and_r4_has_no_verdict(tmp_path):
    assert us_verdicts.reader_verdict(3.0) == "reproduced"
    assert us_verdicts.reader_verdict(-5.0) == "partly reproduced"
    assert us_verdicts.reader_verdict(5.1) == "diverged"
    housing = {"dataset": "housing", "reader": "llama8", "split": "all", "sample": "s", "condition": "gold"}
    write_run(tmp_path, "us_reader", "r3b", housing, metrics={"all": {"accuracy": 70.0, "questions": 2000}})
    mbe = {"dataset": "mbe", "reader": "llama8", "split": "confirmatory", "condition": "closed"}
    write_run(tmp_path, "us_reader", "r4", mbe, metrics={"all": {"accuracy": 40.0, "questions": 1071}})
    entries = {e["id"]: e for e in us_verdicts.reader_targets(tmp_path)}
    assert entries["R3a"]["verdict"] == "pending"
    assert entries["R3b"]["verdict"] == "diverged"
    assert entries["R4 closed"]["verdict"] == "comparison only"
    assert "private questions" in entries["R4 closed"]["note"]
    summary = us_verdicts.make_summary(tmp_path)
    assert "R4 closed" in us_verdicts.markdown_table(summary)
