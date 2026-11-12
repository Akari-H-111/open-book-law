"""Apply section 5 of the preregistration to the run files. Write us_repro.json and the REPRODUCTION.md table.

A target with no run shows `pending`. If a target has several runs, the earliest one decides, so that a rerun
cannot replace a result that someone dislikes. The others are listed next to it.
"""

import re

from open_book_law.paths import REPO_ROOT
from open_book_law.runlog import load_runs, save_json

SUMMARY_PATH = REPO_ROOT / "results" / "summary" / "us_repro.json"
DOC_PATH = REPO_ROOT / "docs" / "REPRODUCTION.md"
AUTO = re.compile(r"(<!-- AUTO:BEGIN -->\n).*?(<!-- AUTO:END -->)", re.DOTALL)
TIERS = ("reproduced", "partly reproduced", "diverged")

# Published values: Zheng et al. 2025. Table 22 is mbe. Tables 24 and 25 are housing's upper and lower bound.
TARGETS = [
    ("R1a", "mbe", "bm25", {10: 0.75, 100: 2.26, 1000: 8.79}),
    ("R1b", "mbe", "e5-small", {10: 0.59, 100: 2.68, 1000: 9.29}),
    ("R1c", "mbe", "e5-base", {10: 0.84, 100: 3.51, 1000: 11.21}),
    ("R1d", "mbe", "e5-large", {10: 0.92, 100: 4.27, 1000: 12.30}),
    ("R2a", "housing", "bm25", {10: 40.81, 100: 62.41, 1000: 76.19}),
    ("R2b", "housing", "e5-small", {10: 34.35, 100: 64.42, 1000: 81.63}),
    ("R2c", "housing", "e5-base", {10: 45.75, 100: 74.61, 1000: 86.65}),
    ("R2d", "housing", "e5-large", {10: 50.58, 100: 78.83, 1000: 87.73}),
]
COMPARISON = {
    "R1a": {"hit@1": 0.25, "mrr@10": 0.37},
    "R1b": {"hit@1": 0.08, "mrr@10": 0.18},
    "R1c": {"hit@1": 0.25, "mrr@10": 0.39},
    "R1d": {"hit@1": 0.17, "mrr@10": 0.34},
    "R2a": {"hit@1": 14.72, "mrr@10": 21.99, "all@10": 18.31, "all@100": 39.89, "all@1000": 59.68},
    "R2b": {"hit@1": 8.97, "mrr@10": 15.95, "all@10": 13.32, "all@100": 37.57, "all@1000": 66.32},
    "R2c": {"hit@1": 13.56, "mrr@10": 22.38, "all@10": 20.30, "all@100": 51.61, "all@1000": 75.53},
    "R2d": {"hit@1": 16.08, "mrr@10": 26.02, "all@10": 24.40, "all@100": 57.20, "all@1000": 78.36},
}
LIMITS = {"mbe": {10: 1, 100: 2, 1000: 3}, "housing": {10: 2, 100: 3, 1000: 3}}
LIBRARY = {"mbe": "full", "housing": "within-state"}
# Published values: Zheng et al. 2025, Tables 30 and 33. R3 runs on the housing sample of Amendment 2.
TOP_1_BM25 = {"condition": "retrieved", "retriever": "bm25", "library": "within-state", "k": 1}
READER_TARGETS = [
    ("R3a", "housing", {"condition": "closed"}, 58.81),
    ("R3b", "housing", {"condition": "gold"}, 75.27),
    ("R3c", "housing", TOP_1_BM25, 68.22),
    ("R4 closed", "mbe", {"condition": "closed"}, 37.84),
    ("R4 gold", "mbe", {"condition": "gold"}, 57.38),
]
READER_NOTES = {
    "housing": "On the sample of 2,000 questions from Amendment 2. Weights are 4-bit. The prompt is ours.",
    "mbe": "Comparison only, with no verdict. The published set includes private questions.",
}


def judge(dataset, published, ours):
    """Return per-k rows and the overall verdict. Every k must meet a tier for the target to reach it."""
    rows, tiers = {}, []
    for k, value in published.items():
        difference = ours[f"hit@{k}"] - value
        limit = LIMITS[dataset][k]
        distance = abs(round(difference, 10))
        tier = 0 if distance <= limit else 1 if distance <= 2 * limit else 2
        tiers.append(tier)
        rows[f"R@{k}"] = {
            "published": value,
            "ours": ours[f"hit@{k}"],
            "difference": difference,
            "limit": limit,
            "verdict": TIERS[tier],
        }
    return rows, TIERS[max(tiers)]


def recalls(run):
    return {f"R@{k}": run["metrics"]["all"][f"hit@{k}"] for k in (10, 100, 1000)}


def target_entry(target, runs, diagnostics):
    target_id, dataset, retriever, published = target
    comparison = COMPARISON[target_id]

    def is_target(run):
        config = run["config"]
        return (
            config["dataset"] == dataset
            and config["retriever"] == retriever
            and config["library"] == LIBRARY[dataset]
        )

    matching = [r for r in runs if is_target(r)]
    entry = {
        "id": target_id,
        "dataset": dataset,
        "retriever": retriever,
        "verdict": "pending",
        "published": {f"R@{k}": v for k, v in published.items()},
        "comparison_only": {},
        "diagnostics": [
            {
                "run_id": r["run_id"],
                "tokenizer": r["config"].get("tokenizer"),
                **recalls(r),
                "comparison_only": {key: r["metrics"]["all"][key] for key in comparison},
            }
            for r in diagnostics
            if is_target(r)
        ],
    }
    if matching:
        first = matching[0]
        ours = first["metrics"]["all"]
        entry["metrics"], entry["verdict"] = judge(dataset, published, ours)
        entry.update(
            run_id=first["run_id"],
            commit=first["git"]["commit"],
            questions=ours["questions"],
            later_runs=[r["run_id"] for r in matching[1:]],
            comparison_only={
                key: {"published": value, "ours": ours[key], "difference": ours[key] - value}
                for key, value in comparison.items()
            },
        )
        if first["config"].get("states"):
            entry["on_sampled_states"] = first["config"]["states"]
    return entry


def make_summary(runs_dir=None):
    full = load_runs("us_retrieval", runs_dir)
    sampled = load_runs("us_states", runs_dir)
    diagnostics = load_runs("us_diagnostics", runs_dir)
    return {
        "source": "Zheng et al. 2025, Tables 22, 24, 25, 30 and 33. Rules: preregistration section 5",
        "units": "percentage points",
        # Amendment 2: R2c runs on sampled states only, and bm25 and e5-small report those states next to it.
        "targets": [target_entry(t, sampled if t[0] == "R2c" else full, diagnostics) for t in TARGETS],
        "same_states": [
            {
                "run_id": r["run_id"],
                "retriever": r["config"]["retriever"],
                "states": r["config"]["states"],
                **recalls(r),
            }
            for r in sampled
        ],
        "reader_targets": reader_targets(runs_dir),
    }


def reader_verdict(difference):
    distance = abs(round(difference, 10))
    return "reproduced" if distance <= 3 else "partly reproduced" if distance <= 5 else "diverged"


def reader_targets(runs_dir):
    """R3 and R4 from the suite `us_reader`. The earliest matching run decides. R4 gets no verdict."""
    runs = load_runs("us_reader", runs_dir)
    entries = []
    for target_id, dataset, settings, published in READER_TARGETS:
        wanted = {"dataset": dataset, "reader": "llama8", **settings}
        wanted["split"] = "all" if dataset == "housing" else "confirmatory"
        matching = [
            r
            for r in runs
            if all(r["config"].get(key) == value for key, value in wanted.items())
            and (dataset == "mbe" or r["config"].get("sample"))
        ]
        entry = {
            "id": target_id,
            "dataset": dataset,
            "published": published,
            "verdict": "pending" if dataset == "housing" else "comparison only",
            "note": READER_NOTES[dataset],
        }
        if matching:
            ours = matching[0]["metrics"]["all"]
            entry.update(
                ours=ours["accuracy"],
                difference=ours["accuracy"] - published,
                questions=ours["questions"],
                run_id=matching[0]["run_id"],
                later_runs=[r["run_id"] for r in matching[1:]],
            )
            if dataset == "housing":
                entry["verdict"] = reader_verdict(entry["difference"])
        entries.append(entry)
    return entries


def retrieval_rows(entry):
    """One table row per recall depth of a target. A target with no run shows `pending`."""
    rows = []
    # Amendment 2: a verdict on sampled states says so.
    verdict = entry["verdict"] + (" (on sampled states)" if entry.get("on_sampled_states") else "")
    for k in (10, 100, 1000):
        key = f"R@{k}"
        metric = entry.get("metrics", {}).get(key)
        ours = f"{metric['ours']:.2f} | {metric['difference']:+.2f}" if metric else "pending | pending"
        rows.append(
            f"| {entry['id']} | {entry['dataset']} | {entry['retriever']} | {key} "
            f"| {entry['published'][key]:.2f} | {ours} | {LIMITS[entry['dataset']][k]} "
            f"| {metric['verdict'] if metric else 'pending'} | {verdict} |"
        )
    return rows


def markdown_table(summary):
    lines = [
        "| Target | Dataset | Retriever | Metric | Published | Ours | Difference | Limit "
        "| Metric verdict | Target verdict |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for entry in summary["targets"]:
        lines += retrieval_rows(entry)
    lines += [
        "",
        "Values for comparison only. No verdict depends on them. `hit@1` and `mrr@10` count the first gold",
        "passage. `all@k` means that every gold statute was found, the paper's lower bound on housing.",
        "",
        "| Target | Metric | Published | Ours | Difference |",
        "|---|---|---:|---:|---:|",
    ]
    for entry in summary["targets"]:
        for key, value in entry["comparison_only"].items():
            lines.append(
                f"| {entry['id']} | {key} | {value['published']:.2f} | {value['ours']:.2f} "
                f"| {value['difference']:+.2f} |"
            )
    lines += [
        "",
        "Diagnostics. These runs use settings that the preregistration did not fix. They change no verdict.",
        "",
        "| Target | Run | Tokenizer | R@10 | R@100 | R@1000 | Comparison-only metrics |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for entry in summary["targets"]:
        for run in entry["diagnostics"]:
            others = ", ".join(f"{key} {value:.2f}" for key, value in run["comparison_only"].items())
            lines.append(
                f"| {entry['id']} | `{run['run_id']}` | {run['tokenizer']} | {run['R@10']:.2f} "
                f"| {run['R@100']:.2f} | {run['R@1000']:.2f} | {others} |"
            )
    if summary["same_states"]:
        lines += ["", "Runs on the sampled states of Amendment 2.", ""]
        lines += ["| Run | Retriever | States | R@10 | R@100 | R@1000 |", "|---|---|---|---:|---:|---:|"]
        for run in summary["same_states"]:
            lines.append(
                f"| `{run['run_id']}` | {run['retriever']} | {', '.join(run['states'])} "
                f"| {run['R@10']:.2f} | {run['R@100']:.2f} | {run['R@1000']:.2f} |"
            )
    lines += [
        "",
        "Reader targets. Accuracy in percent, with limits of 3 and 5 points.",
        "",
        "| Target | Dataset | Published | Ours | Difference | Questions | Verdict | Note |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for entry in summary["reader_targets"]:
        ours = f"{entry['ours']:.2f}" if "ours" in entry else "pending"
        difference = f"{entry['difference']:+.2f}" if "ours" in entry else "pending"
        lines.append(
            f"| {entry['id']} | {entry['dataset']} | {entry['published']:.2f} | {ours} | {difference} "
            f"| {entry.get('questions', 'pending')} | {entry['verdict']} | {entry['note']} |"
        )
    return "\n".join(lines) + "\n"


def update_document(table, path=None):
    path = path or DOC_PATH
    text = path.read_text(encoding="utf-8")
    if not AUTO.search(text):
        raise ValueError(f"no AUTO markers in {path}")
    path.write_text(AUTO.sub(lambda m: m.group(1) + table + m.group(2), text), encoding="utf-8")


def main():
    summary = make_summary()
    save_json(SUMMARY_PATH, summary)
    update_document(markdown_table(summary))
    for entry in summary["targets"]:
        print(entry["id"], entry["dataset"], entry["retriever"], entry["verdict"])


if __name__ == "__main__":
    main()
