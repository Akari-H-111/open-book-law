"""Run one reader on one condition and write one run file. No question or passage text reaches the run file.

Suites: `us_reader` holds full runs. `us_smoke` holds any run with --limit, and those run on validation only.
Answers are appended to a partial file under DATA_ROOT, so that a stopped run continues where it stopped.
"""

import argparse
import json
import time

from open_book_law import runlog
from open_book_law.paths import DERIVED_DIR
from open_book_law.reader import mlx_reader, prompts, samples
from open_book_law.us import barexam

PARTIAL_DIR = DERIVED_DIR / "reader_partial"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    samples.add_question_args(parser, default_split="validation")
    parser.add_argument("--reader", required=True, choices=list(mlx_reader.READERS))
    parser.add_argument("--condition", required=True, choices=["closed", "gold", "retrieved"])
    parser.add_argument("--retriever", help="Retrieved: which ranking to read.")
    parser.add_argument("--library", help="Retrieved: mbe library, or within-state or all-states on housing.")
    parser.add_argument(
        "--rollout", action="store_true", help="Retrieved: use the ranking of a rollout query."
    )
    parser.add_argument("--rank-run", help="Retrieved: a run id, in place of the lookup. For smoke runs.")
    parser.add_argument("--k", type=int, default=1, help="Retrieved: passages to read.")
    parser.add_argument(
        "--answer-form",
        default="yes-no",
        choices=list(prompts.HOUSING_FORMS),
        help="Housing: what the prompt asks for and which labels are scored. Other forms are diagnostics.",
    )
    args = parser.parse_args(argv)
    if args.limit and args.split != "validation":
        parser.error("smoke runs use --split validation")
    if args.answer_form != "yes-no" and args.dataset != "housing":
        parser.error("--answer-form applies only to housing")
    return args


def rank_run_config(rank_run):
    with open(runlog.find_run(rank_run), encoding="utf-8") as f:
        return json.load(f)["config"]


def make_config(args, rank_run):
    """`rollout` comes from the ranking run itself, because --rank-run can name any run."""
    retrieved = args.condition == "retrieved"
    # A diagnostic form is recorded only when it is used, so the preregistered runs keep their ids.
    form = {"answer_form": args.answer_form} if args.answer_form != "yes-no" else {}
    return form | {
        "dataset": args.dataset,
        "reader": args.reader,
        "condition": args.condition,
        "retriever": args.retriever if retrieved else None,
        "library": args.library if retrieved else None,
        "rollout": retrieved and bool(rank_run_config(rank_run).get("rollout")),
        "rank_run": rank_run,
        "k": args.k if retrieved else None,
        "split": args.split,
        "sample": args.sample,
        "limit": args.limit,
        "rerun": args.rerun,
        "prompt_version": prompts.PROMPT_VERSION,
        "context_tokens": prompts.CONTEXT_TOKENS,
    }


def find_rank_run(args):
    """The earliest ranking that matches and covers the split. A rerun cannot replace it silently."""
    if args.rank_run:
        return args.rank_run
    runs = runlog.load_runs("us_retrieval") + runlog.load_runs("us_downstream")
    found = [
        (run["utc_time"], run["run_id"])
        for run in runs
        if run["config"]["dataset"] == args.dataset
        and run["config"].get("retriever") == args.retriever
        and run["config"].get("library") == args.library
        and run["config"].get("split", "all") in ("all", args.split)
        and bool(run["config"].get("rollout")) == args.rollout
    ]
    if not found:
        raise SystemExit(
            f"no ranking for {args.dataset} {args.retriever} {args.library}: run us_retrieval first"
        )
    return min(found)[1]


def load_candidates(args, questions, rank_run):
    """Return (questions, docids that may be read per question).

    A ranking of a larger pool keeps every docid, because filter_library cuts it to k later. Any other ranking
    keeps only k, so that the text of few passages sits in memory.
    """
    if args.condition == "closed":
        return questions, {q["qid"]: [] for q in questions}
    if args.condition == "gold":
        return questions, {q["qid"]: sorted(q["gold"]) for q in questions}
    depth = args.k if args.library in (None, rank_run_config(rank_run)["library"]) else None
    rankings = runlog.read_rankings(rank_run)[0]
    runlog.require_questions(questions, rankings, rank_run)
    return questions, {q["qid"]: rankings[q["qid"]][:depth] for q in questions}


def read_passages(dataset, wanted):
    """Dict from docid to (text, source), for wanted docids only. One pass over the pool."""
    if not wanted:
        return {}
    return {
        row["idx"]: (row["text"], row.get("source"))
        for row in samples.iter_passages(dataset)
        if row["idx"] in wanted
    }


def filter_library(docids, passages, library, k):
    """The first k docids whose source is in the library. Without a named mbe library, the first k."""
    if library not in barexam.LIBRARIES:
        return docids[:k]
    sources = barexam.LIBRARIES[library]
    return [d for d in docids if passages[d][1] in sources][:k]


def answer_one(model, tokenizer, args, question, chosen, passages, token_ids):
    form = answer_form(args)
    text = prompts.question_text(args.dataset, question, form)
    truncated = False
    if args.condition != "closed":
        context, truncated = prompts.truncate_context(tokenizer, [passages[d][0] for d in chosen])
        text = prompts.with_context(args.dataset, question, context, form)
    ids = prompts.prompt_ids(tokenizer, text, args.reader)
    probabilities, mass = mlx_reader.score_labels(model, ids, token_ids)
    predicted = max(prompts.labels(args.dataset, form), key=lambda label: probabilities[label])
    gold = prompts.gold_label(args.dataset, question, form)
    return {
        "qid": question["qid"],
        "group": question.get("split") or question["pool"],
        "predicted": predicted,
        "gold": gold,
        "correct": float(predicted == gold),
        "probabilities": probabilities,
        "label_mass": mass,
        "docids": chosen,
        "truncated": truncated,
        "prompt_tokens": len(ids),
    }


def answer_form(args):
    """Callers such as us_goodlaw have no --answer-form, so they get the preregistered form."""
    return getattr(args, "answer_form", "yes-no")


def summarize(records):
    return {
        "questions": len(records),
        "accuracy": 100 * sum(r["correct"] for r in records) / len(records),
        "contexts_cut": sum(r["truncated"] for r in records),
        "mean_label_mass": sum(r["label_mass"] for r in records) / len(records),
    }


def main(argv=None):
    args = parse_args(argv)
    started = time.time()
    rank_run = find_rank_run(args) if args.condition == "retrieved" else None
    config = make_config(args, rank_run)
    questions = samples.load_questions(args.dataset, args.split, args.sample, args.limit)
    questions, candidates = load_candidates(args, questions, rank_run)
    passages = read_passages(args.dataset, {d for docids in candidates.values() for d in docids})

    contexts = {}
    for q in questions:
        chosen = candidates[q["qid"]]
        if args.condition == "retrieved":
            chosen = filter_library(chosen, passages, args.library, args.k)
        contexts[q["qid"]] = chosen, passages
    suite = "us_smoke" if args.limit else "us_reader" if args.answer_form == "yes-no" else "us_diagnostics"
    answer_all(args, config, questions, contexts, suite, started)


def answer_all(args, config, questions, contexts, suite, started, add=None, summarizer=summarize):
    """Answer each question from its (docids, passages), and write the run file. A stopped run continues."""
    model, tokenizer = mlx_reader.load_reader(args.reader)
    token_ids = mlx_reader.label_token_ids(tokenizer, prompts.labels(args.dataset, answer_form(args)))
    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
    partial_path = PARTIAL_DIR / f"{runlog.run_id(config)}.jsonl"
    records = runlog.read_partial(partial_path)
    resumed = len(records)
    read_seconds = 0.0
    with open(partial_path, "a", encoding="utf-8") as partial:
        for done, q in enumerate(questions, start=1):
            if q["qid"] in records:
                continue
            begun = time.time()
            record = answer_one(model, tokenizer, args, q, *contexts[q["qid"]], token_ids)
            read_seconds += time.time() - begun
            records[q["qid"]] = record | add(record, q) if add else record
            runlog.append_record(partial, records[q["qid"]])
            answered = len(records) - resumed
            print(f"{done}/{len(questions)} {answered / read_seconds:.2f} questions/s", flush=True)

    ordered = [records[q["qid"]] for q in questions]
    metrics = {"all": summarizer(ordered), "label_token_ids": token_ids}
    model_id = mlx_reader.READERS[args.reader]
    pin = {"id": model_id, "revision": runlog.model_pin(model_id)["revision"]}
    speed = (len(records) - resumed) / max(read_seconds, 1e-9)
    throughput = {"questions_per_second": speed, "read_seconds": read_seconds, "resumed_questions": resumed}
    data = samples.data_files(args.dataset)
    path = runlog.write_run(suite, config, data, pin, metrics, ordered, time.time() - started, throughput)
    print(f"wrote {path}")
    print(json.dumps({"accuracy": metrics["all"]["accuracy"], **throughput}))


if __name__ == "__main__":
    main()
