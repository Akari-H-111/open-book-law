"""Apply section 3.4 and Amendment 4 of the preregistration from validation records. Write us_selection.json.

`validation_view` is the only door to a run file here: it drops every record of any other split.
The earliest matching run decides. A choice whose inputs are incomplete shows `pending`.
"""

from open_book_law.paths import REPO_ROOT
from open_book_law.reader.prompts import PROMPT_VERSION
from open_book_law.runlog import first_match, load_runs, save_json

SUMMARY_PATH = REPO_ROOT / "results" / "summary" / "us_selection.json"
# Options come in the order that breaks ties. Amendment 2 runs e5-large after the confirmatory runs.
DENSE_CANDIDATES = ("e5-small", "e5-base")
KS = (1, 3, 5)
LIBRARIES = ("doctrine", "cases", "real")
OPEN_READERS = ("qwen3", "phi4")


def validation_view(run):
    """What selection may see of a run: its config and its validation numbers, and nothing else."""
    return {
        "run_id": run["run_id"],
        "config": run["config"],
        "metrics": run["metrics"].get("validation"),
        "records": [r for r in run["per_query"] if r.get("group") == "validation"],
    }


def views(suite, runs_dir):
    return [validation_view(run) for run in load_runs(suite, runs_dir)]


def accuracy(view):
    return 100 * sum(r["correct"] for r in view["records"]) / len(view["records"])


def choose(scores, runs, rule):
    """The first option with the highest score. Options come in the order that breaks ties."""
    if any(score is None for score in scores.values()):
        return {"status": "pending", "scores": scores, "runs": runs, "rule": rule}
    best = max(scores, key=lambda option: (scores[option], -list(scores).index(option)))
    return {"status": "selected", "value": best, "scores": scores, "runs": runs, "rule": rule}


def compare_readers(runs, options, field, rule, **settings):
    found = {o: first_match(runs, **{field: o}, **settings) for o in options}
    scores = {o: accuracy(run) if run and run["records"] else None for o, run in found.items()}
    return choose(scores, {o: run and run["run_id"] for o, run in found.items()}, rule)


def make_selection(runs_dir=None):
    retrieval = views("us_retrieval", runs_dir)
    found = {m: first_match(retrieval, dataset="mbe", retriever=m, library="full") for m in DENSE_CANDIDATES}
    scores = {m: run["metrics"]["hit@100"] if run and run["metrics"] else None for m, run in found.items()}
    dense = choose(scores, {m: run and run["run_id"] for m, run in found.items()}, "highest R@100 on full")

    readers = [
        run
        for run in views("us_reader", runs_dir)
        if run["config"].get("split") == "validation"
        and run["config"].get("prompt_version") == PROMPT_VERSION
        and not run["config"].get("rollout")
    ]
    settings = {"dataset": "mbe", "reader": "llama8", "condition": "retrieved"}
    k_rule = "highest accuracy, ties to the smaller k"
    library_rule = "highest accuracy among libraries"
    k = {"status": "pending", "scores": {}, "runs": {}, "rule": k_rule}
    library = {"status": "pending", "scores": {}, "runs": {}, "rule": library_rule}
    if dense["status"] == "selected":
        settings["retriever"] = dense["value"]
        k = compare_readers(readers, KS, "k", k_rule, library="real", **settings)
    if k["status"] == "selected":
        library = compare_readers(readers, LIBRARIES, "library", library_rule, k=k["value"], **settings)
    best_open = compare_readers(
        readers, OPEN_READERS, "reader", "highest closed-book accuracy", dataset="mbe", condition="closed"
    )
    return {"best_dense": dense, "k": k, "best_real_library": library, "best_open": best_open}


def main():
    selection = make_selection()
    save_json(SUMMARY_PATH, selection)
    for key, choice in selection.items():
        print(key, choice.get("value", "pending"))


if __name__ == "__main__":
    main()
