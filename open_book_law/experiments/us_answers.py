"""Post hoc: how the housing reader runs split their answers between Yes and No.

Writes us_housing_answers.json.

No hypothesis depends on this file. It shows how far each accuracy is above always answering "No".
"""

from collections import Counter

from open_book_law.paths import REPO_ROOT
from open_book_law.runlog import load_runs, save_json

SUMMARY_PATH = REPO_ROOT / "results" / "summary" / "us_housing_answers.json"


def answer_split(run):
    """Gold and predicted label counts, and accuracy within each gold label, in percent."""
    rows = run["per_query"]
    gold = Counter(r["gold"] for r in rows)
    predicted = Counter(r["predicted"] for r in rows)
    accuracy = {
        label: round(100 * sum(r["correct"] for r in rows if r["gold"] == label) / gold[label], 2)
        for label in gold
    }
    return {
        "accuracy": run["metrics"]["all"]["accuracy"],
        "accuracy_by_gold": accuracy,
        "always_no": round(100 * gold["No"] / len(rows), 2),
        "config": {key: run["config"][key] for key in ("condition", "retriever", "library", "k")},
        "gold": dict(gold),
        "predicted": dict(predicted),
        "questions": len(rows),
        "run_id": run["run_id"],
    }


def main():
    runs = [
        r
        for r in load_runs("us_reader")
        if r["config"]["dataset"] == "housing" and r["config"]["split"] == "all"
    ]
    summary = {"post_hoc": True, "runs": [answer_split(r) for r in runs]}
    save_json(SUMMARY_PATH, summary)
    for row in summary["runs"]:
        config = row["config"]
        by_gold = row["accuracy_by_gold"]
        print(row["run_id"], config["condition"], config["retriever"], row["accuracy"], by_gold)


if __name__ == "__main__":
    main()
