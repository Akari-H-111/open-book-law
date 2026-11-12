"""Apply sections 4 and 6 of the preregistration to the run files. Write us_hypotheses.json and a table.

Holm runs over the whole family of H1 to H10, in which H4 has two tests. A missing p-value counts as 1, so
corrected values stay conservative until the family is complete, and each row says when that is the case.
"""

import math

from open_book_law import evalx
from open_book_law.experiments import us_select
from open_book_law.experiments.us_verdicts import update_document
from open_book_law.paths import REPO_ROOT
from open_book_law.runlog import first_match, load_runs, save_json
from open_book_law.us import goodlaw

SUMMARY_PATH = REPO_ROOT / "results" / "summary" / "us_hypotheses.json"
DOC_PATH = REPO_ROOT / "docs" / "RESULTS.md"
ALPHA = 0.05
THRESHOLDS = {
    "H1": 3, "H2": 2, "H3": 5, "H4a": 3, "H4b": 3, "H5": 3, "H6": 2, "H7": 10, "H8": 5,
    "H9": "Wilson low > 30%", "H10": 5,
}  # fmt: skip
CONFIRMATORY_GROUPS = ("train", "test")
NOT_TESTABLE = "not testable with this model"


def values(run, key, groups=None):
    """Dict from qid to a 0 or 1 outcome, optionally within some groups."""
    return {r["qid"]: r[key] for r in run["per_query"] if groups is None or r["group"] in groups}


def compare(a, b, a_run, b_run):
    """Paired comparison of two dicts from qid to 0 or 1. Different question sets show `pending`."""
    if set(a) != set(b) or not a:
        return {"status": "pending", "note": f"question sets differ: {len(a)} and {len(b)}"}
    qids = sorted(a)
    x = [a[q] for q in qids]
    y = [b[q] for q in qids]
    difference, low, high = evalx.paired_bootstrap([100 * v for v in x], [100 * v for v in y])
    a_only, b_only, p = evalx.mcnemar_exact(x, y)
    return {
        "status": "done",
        "questions": len(qids),
        "difference": difference,
        "low": low,
        "high": high,
        "a_only": a_only,
        "b_only": b_only,
        "p": p,
        "runs": [a_run, b_run],
    }


def ordinary(runs):
    """Drop reader runs that read a rollout ranking. Only H4 may use rollouts, and it reads retrieval runs."""
    return [run for run in runs if not run["config"].get("rollout")]


def pair(a_run, b_run, a_key="correct", b_key=None, b_groups=None):
    if a_run is None or b_run is None:
        return {"status": "pending", "note": "a run is missing"}
    a = values(a_run, a_key)
    b = values(b_run, b_key or a_key, b_groups)
    return compare(a, b, a_run["run_id"], b_run["run_id"])


def share_test(run):
    """H9. Holm needs a p-value and section 6 names no test, so this is an exact one-sided binomial at 30%."""
    if run is None:
        return {"status": "pending", "note": "a run is missing"}
    n, k = len(run["per_query"]), int(sum(r["old_outranks_new"] for r in run["per_query"]))
    low, high = evalx.wilson(k, n)
    p = min(1.0, sum(math.comb(n, i) * 0.3**i * 0.7 ** (n - i) for i in range(k, n + 1)))
    test = {"difference": 100 * k / n, "low": 100 * low, "high": 100 * high, "p": p, "runs": [run["run_id"]]}
    return test | {"status": "done", "questions": n}


def agent_test(good, agents, reader, search):
    """H10: `retrieved` minus the agent. Amendment 1 part D: too few valid turns on validation rule it out."""
    own = {"reader": reader, "retriever": search["retriever"]}
    validation = first_match(agents, dataset="mbe", split="validation", **own)
    if validation and validation["metrics"]["all"]["valid_turn_share"] < 80:
        return {"status": NOT_TESTABLE, "note": "under 80% of turns were valid on validation"}
    agent = first_match(agents, dataset="scotus", **own) if validation else None
    return pair(first_match(good, condition="retrieved", k=search["k"], **own), agent, "superseded")


def apply_rules(tests):
    """Add the corrected p-value and the verdict to each test. `tests` maps id to a compare() result.

    A test that cannot run keeps its place in the family with p = 1, so the family stays at 11 tests.
    """
    ids = list(tests)
    corrected = evalx.holm([tests[i].get("p", 1.0) for i in ids])
    complete = all(tests[i]["status"] in ("done", NOT_TESTABLE) for i in ids)
    for test_id, p_holm in zip(ids, corrected, strict=True):
        test = tests[test_id]
        test["threshold"] = THRESHOLDS[test_id]
        test["family_complete"] = complete
        test["verdict"] = NOT_TESTABLE if test["status"] == NOT_TESTABLE else "pending"
        if test["status"] == "done":
            test["p_holm"] = p_holm
            floor = test["low"] > (30 if test_id == "H9" else 0)
            large = test_id == "H9" or round(test["difference"], 10) >= test["threshold"]
            meets = floor and large and p_holm < ALPHA
            test["verdict"] = "supported" if meets else "not supported"
    return tests


def make_summary(runs_dir=None):
    selection = us_select.make_selection(runs_dir)
    readers = ordinary(load_runs("us_reader", runs_dir))
    downstream = [r for r in load_runs("us_downstream", runs_dir) if r["config"].get("rollout")]
    baseline = load_runs("us_retrieval", runs_dir)
    llama = {"dataset": "mbe", "reader": "llama8", "split": "confirmatory"}
    closed = first_match(readers, condition="closed", **llama)
    tests = {key: {"status": "pending", "note": "a selection is pending"} for key in THRESHOLDS}

    if {selection[key]["status"] for key in ("best_dense", "k", "best_real_library")} == {"selected"}:
        search = {"retriever": selection["best_dense"]["value"], "k": selection["k"]["value"]}
        retrieved = {**llama, "condition": "retrieved", **search}
        best = first_match(readers, library=selection["best_real_library"]["value"], **retrieved)
        tests["H1"] = pair(best, closed)
        tests["H2"] = pair(
            first_match(readers, library="doctrine", **retrieved),
            first_match(readers, library="cases", **retrieved),
        )
        tests["H3"] = pair(first_match(readers, condition="gold", **llama), best)

    def rollout_test(retriever):
        settings = {"dataset": "mbe", "retriever": retriever, "library": "full"}
        expanded = first_match(downstream, split="confirmatory", **settings)
        return pair(expanded, first_match(baseline, **settings), "hit@100", b_groups=CONFIRMATORY_GROUPS)

    tests["H4a"] = rollout_test("bm25")
    if selection["best_dense"]["status"] == "selected":
        tests["H4b"] = rollout_test(selection["best_dense"]["value"])

    housing = {"dataset": "housing", "reader": "llama8", "condition": "retrieved"}
    housing |= {"retriever": "e5-small", "k": 1}
    sampled = [r for r in readers if r["config"].get("sample") and r["config"].get("split") == "all"]
    tests["H5"] = pair(
        first_match(sampled, library="within-state", **housing),
        first_match(sampled, library="all-states", **housing),
    )
    evaluated = first_match(load_runs("us_finetune", runs_dir), mode="eval", split="test")
    tests["H6"] = pair(evaluated, evaluated, "hit@10", "zero_hit@10")
    good = ordinary(load_runs("us_goodlaw", runs_dir))
    tests["H7"] = pair(
        first_match(good, condition="old-only", reader="llama8"),
        first_match(good, condition="closed", reader="llama8"),
        "superseded",
    )
    if {selection[key]["status"] for key in ("best_dense", "k")} == {"selected"}:
        search = {"retriever": selection["best_dense"]["value"], "k": selection["k"]["value"]}
        retrieved = first_match(good, condition="retrieved", reader="llama8", **search)
        citator = first_match(good, condition="citator", reader="llama8", **search)
        tests["H8"] = pair(retrieved, citator, "superseded")
        scotus = load_runs("us_downstream", runs_dir)
        tests["H9"] = share_test(first_match(scotus, dataset="scotus", retriever=search["retriever"]))
        best_open = selection["best_open"].get("value")
        tests["H10"] = agent_test(good, load_runs("us_agent", runs_dir), best_open, search)
    extras = {}
    dates = [first_match(good, condition=c, reader="llama8") for c in ("date-before", "date-today")]
    if all(dates):
        extras["date_test_both_forms_correct"] = goodlaw.both_forms_correct(*dates)
    if evaluated:
        unseen = [r for r in evaluated["per_query"] if r["unseen_group"]]
        # Runs before this fix stored 0 for an empty subset; an empty subset has no rate.
        metrics = evaluated["metrics"]["unseen_groups"] if unseen else {}
        extras["H6_unseen_groups"] = {
            "questions": len(unseen),
            "hit@10": metrics.get("hit@10"),
            "zero_hit@10": metrics.get("zero_hit@10"),
        }
    return {"units": "percentage points", "alpha": ALPHA, "tests": apply_rules(tests), "exploratory": extras}


def markdown_table(summary):
    lines = [
        "| Test | Difference | 95% interval | p | Holm p | Needs | Verdict |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for test_id, test in summary["tests"].items():
        if test["status"] == "done":
            interval = f"{test['low']:+.2f} to {test['high']:+.2f}"
            numbers = f"{test['difference']:+.2f} | {interval} | {test['p']:.4f} | {test['p_holm']:.4f}"
        else:
            numbers = "pending | pending | pending | pending"
        lines.append(f"| {test_id} | {numbers} | {test['threshold']} | {test['verdict']} |")
    complete = next(iter(summary["tests"].values()))["family_complete"]
    lines += ["", f"Every Holm test in the family has run: {'yes' if complete else 'no'}."]
    return "\n".join(lines) + "\n"


def main():
    summary = make_summary()
    save_json(SUMMARY_PATH, summary)
    update_document(markdown_table(summary), DOC_PATH)
    for test_id, test in summary["tests"].items():
        print(test_id, test["verdict"])


if __name__ == "__main__":
    main()
