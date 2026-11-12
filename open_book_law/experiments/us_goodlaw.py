"""Section 8.3: one reader on one good-law condition. No text reaches the run file. Suite: `us_goodlaw`.

Searched conditions read a scotus ranking from us_retrieval. A run with --limit goes to `us_smoke`.

The citator reads the top 1000 of the ranking from the data folder, drops overruled decisions, and keeps the
first k. It does not search further, so a question can get fewer than k passages. The run file records
how many each question got, and how many questions got fewer than k.

The date test of Amendment 1 part C has two conditions, `date-before` and `date-today`. Both show the
`both-dated` passages. The first asks for the law in the year before the overruling, where the superseded
rule is correct. The second asks for the law today. `goodlaw.both_forms_correct` combines the two runs."""

import argparse
import random
import sys
import time

from open_book_law import runlog
from open_book_law.experiments.us_reader import (
    answer_all,
    find_rank_run,
    rank_run_config,
    read_passages,
    summarize,
)
from open_book_law.reader import mlx_reader, prompts, samples
from open_book_law.us import goodlaw
from open_book_law.us.authority import status

SEARCHED = ("retrieved", "citator", "note")
DATE_TEST = ("date-before", "date-today")
FIXED = ("closed", "old-only", "new-only", "both", "both-dated", *DATE_TEST)


def old_goes_first(qid):
    """A seeded coin for each question. `both` and `both-dated` use the same order."""
    return random.Random(f"{samples.SEED}:order:{qid}").random() < 0.5


def fixed_context(q, condition):
    """Return (case ids in reading order, dict from case id to (text, None))."""
    old, new = q["old_id"], q["new_id"]
    texts = {old: (q["old_passage"], None), new: (q["new_passage"], None)}
    if condition in ("both-dated", *DATE_TEST):
        texts[old] = (f"{q['old_name']} ({q['old_year']}):\n{q['old_passage']}", None)
        texts[new] = (f"{q['new_name']} ({q['new_year']}):\n{q['new_passage']}", None)
    both = [old, new] if old_goes_first(q["qid"]) else [new, old]
    return {"closed": [], "old-only": [old], "new-only": [new]}.get(condition, both), texts


def date_form(q, condition):
    """One of two forms. Before the overruling the superseded rule is correct. Today the current rule is."""
    if condition == "date-before":
        return q | {"query": f"As of {q['new_year'] - 1}: {q['query']}", "answer": q["superseded_rule"]}
    return q | {"query": f"As of {goodlaw.TODAY}: {q['query']}"}


def citator_top_k(conn, docids, k, as_of=goodlaw.TODAY):
    """The first k passages whose decision had not been overruled on that date."""
    return [d for d in docids if status(conn, goodlaw.case_of(d), as_of)["status"] != "overruled"][:k]


def with_note(conn, docid, text):
    """The note goes before the passage, so that a cut at the context limit cannot remove it."""
    events = status(conn, goodlaw.case_of(docid), goodlaw.TODAY)["overruled_by"]
    notes = "; ".join(f"Overruled by {e['name']} ({e['year']})" for e in events)
    return f"[{notes}.]\n{text}" if notes else text


def outcome_fields(record, q):
    names = {q["current_rule"]: "current", q["superseded_rule"]: "superseded"}
    outcome = names.get(record["predicted"], "other_wrong")
    return {
        "outcome": outcome,
        "superseded": float(outcome == "superseded"),
        "old_first": old_goes_first(q["qid"]),
        "n_passages": len(record["docids"]),
    }


def summarize_goodlaw(records, k=None):
    """For searched conditions `k` is set, and the summary counts questions with fewer than k passages."""
    names = ("current", "superseded", "other_wrong")
    rates = {name: 100 * sum(r["outcome"] == name for r in records) / len(records) for name in names}
    left_out = [q["qid"] for q in goodlaw.read_questions()[1]]
    summary = summarize(records) | {"rates": rates, "left_out": left_out}
    if k:
        summary |= {"k": k, "questions_with_fewer_than_k": sum(r["n_passages"] < k for r in records)}
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    samples.add_question_args(parser, default_split="all")
    parser.add_argument("--reader", required=True, choices=list(mlx_reader.READERS))
    parser.add_argument("--condition", required=True, choices=[*FIXED, *SEARCHED])
    parser.add_argument("--retriever", help="Searched conditions: which scotus ranking to read.")
    parser.add_argument("--rank-run", help="Searched conditions: a run id, in place of the lookup.")
    parser.add_argument("--k", type=int, default=1, help="Searched conditions: passages to read.")
    args = parser.parse_args(["--dataset", "scotus", *(argv if argv is not None else sys.argv[1:])])
    args.library, args.rollout = "scotus", False
    started = time.time()
    searched = args.condition in SEARCHED
    args.rank_run = find_rank_run(args) if searched else None
    if searched:
        # --rank-run can name any run, so the config records what that run did.
        args.rollout = bool(rank_run_config(args.rank_run).get("rollout"))
    config = vars(args) | {"as_of": goodlaw.TODAY, "prompt_version": prompts.PROMPT_VERSION}
    questions = samples.load_questions("scotus", limit=args.limit)
    conn = goodlaw.connect()
    summarizer = summarize_goodlaw
    if searched:
        if args.condition == "citator" and not runlog.deep_rank_path(args.rank_run, None).exists():
            raise SystemExit(f"the citator needs the top 1000 of {args.rank_run} in the data folder")
        rankings = runlog.read_rankings(args.rank_run)[0]
        runlog.require_questions(questions, rankings, args.rank_run)
        summarizer = lambda records: summarize_goodlaw(records, args.k)  # noqa: E731
        pick = citator_top_k if args.condition == "citator" else (lambda _, docids, k: docids[:k])
        chosen = {q["qid"]: pick(conn, rankings[q["qid"]], args.k) for q in questions}
        texts = read_passages("scotus", {d for docids in chosen.values() for d in docids})
        if args.condition == "note":
            texts = {d: (with_note(conn, d, text), None) for d, (text, _) in texts.items()}
        contexts = {qid: (docids, texts) for qid, docids in chosen.items()}
    else:
        contexts = {q["qid"]: fixed_context(q, args.condition) for q in questions}
        if args.condition in DATE_TEST:
            questions = [date_form(q, args.condition) for q in questions]
    suite = "us_smoke" if args.limit else "us_goodlaw"
    answer_all(args, config, questions, contexts, suite, started, outcome_fields, summarizer)


if __name__ == "__main__":
    main()
