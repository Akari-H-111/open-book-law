"""Run one retrieval configuration on mbe or housing and write one run file.

Suites: `us_retrieval` holds preregistered settings on all data. `us_diagnostics` holds any other setting.
`us_smoke` holds any run with --limit. `us_states` holds runs on sampled states (--states, Amendment 2).
`us_downstream` holds rankings that readers and hypotheses use: other libraries, splits or samples, hybrid,
rollout, all-states and scotus. The verdict script reads `us_retrieval`, and `us_states` for target R2c.

Rollouts: the paper "expands the query with the generated reasoning rollout" and speaks of "appending more
reasoning tokens" (section 5.3 and section 6). It gives no weights or repeats, so the query here is the
original query, one space, then the rollout. The paper used GPT-3.5, so this replicates it with a local model.
"""

import argparse
import json
import time
from collections import Counter

import numpy as np

from open_book_law import evalx, runlog
from open_book_law.reader import samples
from open_book_law.retrieval import bm25, dense, fusion
from open_book_law.us import barexam, goodlaw, housing

KS = (1, 10, 100, 1000)
QUERY_BATCH = 500


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    samples.add_question_args(parser, default_split="all")
    parser.add_argument("--retriever", required=True, choices=["bm25", "hybrid", *dense.MODELS])
    parser.add_argument(
        "--from", dest="from_runs", nargs=2, metavar="RUN", help="Hybrid: two run ids to fuse."
    )
    parser.add_argument("--scope", default="within-state", choices=["within-state", "all-states"])
    parser.add_argument("--states", type=int, help="Housing: search only N randomly chosen states.")
    parser.add_argument(
        "--rollout", help="JSONL of qid and text, from us_rollout: search with the expanded query."
    )
    parser.add_argument(
        "--library",
        default="full",
        choices=list(barexam.LIBRARIES),
        help="mbe only. On housing, the search is always within the question's state.",
    )
    parser.add_argument("--tokenizer", default="plain", choices=["plain", "porter"])
    args = parser.parse_args(argv)
    if args.dataset != "housing" and (args.states or args.scope != "within-state"):
        parser.error("--states and --scope apply only to housing")
    if args.scope == "all-states" and args.retriever not in dense.MODELS:
        parser.error("--scope all-states needs a dense retriever")
    return args


def suite_for(args):
    if args.limit:
        return "us_smoke"
    if args.tokenizer != "plain":
        return "us_diagnostics"
    if args.states:
        return "us_states"
    downstream = (
        args.dataset == "scotus"
        or args.split != "all"
        or args.sample
        or args.library != "full"
        or args.scope != "within-state"
        or args.rollout
        or args.retriever == "hybrid"
    )
    return "us_downstream" if downstream else "us_retrieval"


def make_config(args, questions):
    config = {
        "dataset": args.dataset,
        "retriever": args.retriever,
        "library": {"mbe": args.library, "scotus": "scotus"}.get(args.dataset, args.scope),
        "split": args.split,
        "sample": args.sample,
        "rollout": args.rollout and runlog.portable(args.rollout),
        "states": sorted({q["pool"] for q in questions}) if args.states else None,
        "limit": args.limit,
        "rerun": args.rerun,
        "ks": list(KS),
        "tie_break": f"fixed random order, seed {bm25.TIE_SEED}",
    }
    if args.rollout:
        config["rollout_sha256"] = runlog.sha256_file(args.rollout)
    if args.retriever == "bm25":
        config.update(tokenizer=args.tokenizer, k1=0.9, b=0.4)
    elif args.retriever == "hybrid":
        config.update(from_runs=args.from_runs, rrf_k=fusion.RRF_K, tie_break="smaller docid")
    else:
        config.update(
            max_length=dense.MAX_LENGTH,
            batch_size=dense.BATCH_SIZES[args.retriever],
            vector_dtype="float16",
            device=dense.DEVICE,
        )
    return config


def expand_queries(questions, rollout_path):
    """Append each rollout to its query. A question with no rollout is left out, and the count shows it."""
    with open(rollout_path, encoding="utf-8") as f:
        rollouts = {row["qid"]: row["text"] for row in map(json.loads, f)}
    kept = [q for q in questions if q["qid"] in rollouts]
    return [{**q, "query": f"{q['query']} {rollouts[q['qid']]}"} for q in kept]


def iter_groups(args, questions):
    """Yield (group name, docids, texts, questions of that group). A group is one searchable pool."""
    if args.dataset == "mbe":
        rows = list(barexam.iter_pool(args.library))
        yield "all", [r["idx"] for r in rows], [r["text"] for r in rows], questions
        return
    by_state = {}
    for q in questions:
        by_state.setdefault(q["pool"], []).append(q)
    for state, rows in housing.iter_states():
        if state in by_state:
            yield state, [r["idx"] for r in rows], [r["text"] for r in rows], by_state[state]


def passage_texts(dataset, states=None):
    """Every passage text to encode. Libraries are subsets of the whole pool. `states` limits housing."""
    for row in samples.iter_passages(dataset):
        if states is None or row["state"] in states:
            yield row["text"]


def score_query(question, ranked):
    relevant = question["gold"]
    record = {
        "qid": question["qid"],
        "n_gold": len(relevant),
        "n_ranked": len(ranked),
        "mrr@10": evalx.mrr_at_k(ranked, relevant, 10),
        "group": question.get("split") or question["pool"],
    }
    for k in KS:
        record[f"hit@{k}"] = evalx.hit_at_k(ranked, relevant, k)
        record[f"all@{k}"] = evalx.all_at_k(ranked, relevant, k)
        record[f"recall@{k}"] = evalx.recall_at_k(ranked, relevant, k)
    return record


def aggregate(records):
    """Mean of each metric over questions, in percent."""
    keys = [key for key in records[0] if "@" in key]
    summary = {key: 100 * sum(r[key] for r in records) / len(records) for key in keys}
    summary["questions"] = len(records)
    return summary


def rank_scotus(questions, rows, scores_for):
    """Rank each decision's best passage among all scores, so no cutoff hides it. A tie does not outrank."""
    positions_of = {}
    for position, row in enumerate(rows):
        positions_of.setdefault(row["case_id"], []).append(position)
    tie = bm25.neutral_tie_order(len(rows))
    rankings, records = {}, []
    for i, q in enumerate(questions):
        scores = scores_for(i)
        old, new = (int((scores > scores[positions_of[q[s]]].max()).sum()) + 1 for s in ("old_id", "new_id"))
        top = bm25.top_k(scores, max(KS), tie)[0]
        rankings[q["qid"]] = [rows[p]["id"] for p in top]
        record = {"qid": q["qid"], "group": "overruled", "rank_old": old, "rank_new": new}
        types = dict(Counter(rows[p]["opinion_type"] for p in top[:10]))
        records.append(record | {"old_outranks_new": float(old < new), "types_top10": types})
    return rankings, records


def summarize_scotus(records):
    types = sum((Counter(r["types_top10"]) for r in records), Counter())
    return {
        "questions": len(records),
        "old_outranks_new": 100 * sum(r["old_outranks_new"] for r in records) / len(records),
        "type_share_top10": {key: 100 * n / types.total() for key, n in sorted(types.items())},
        "left_out": [q["qid"] for q in goodlaw.read_questions()[1]],
    }


def run_bm25(args, questions):
    if args.dataset == "scotus":
        rows = list(samples.iter_passages("scotus"))
        index = bm25.build_index((r["text"] for r in rows), tokenizer=args.tokenizer)
        scores_for = lambda i: bm25.score_all(index, questions[i]["query"])  # noqa: E731
        return *rank_scotus(questions, rows, scores_for), {}
    rankings, records = {}, []
    index_seconds = search_seconds = 0.0
    for name, docids, texts, group in iter_groups(args, questions):
        started = time.time()
        index = bm25.build_index(texts, tokenizer=args.tokenizer)
        del texts
        built = time.time()
        for q in group:
            positions, _ = bm25.search(index, q["query"], k=max(KS))
            rankings[q["qid"]] = [docids[i] for i in positions]
            records.append(score_query(q, rankings[q["qid"]]))
        index_seconds += built - started
        search_seconds += time.time() - built
        print(f"{name}: {len(docids)} docs, {len(group)} queries", flush=True)
    return rankings, records, {"index_seconds": index_seconds, "search_seconds": search_seconds}


def run_hybrid(args, questions):
    """Reciprocal rank fusion of two existing rankings, over the deepest rank files available."""
    first, depth_a = runlog.read_rankings(args.from_runs[0])
    second, depth_b = runlog.read_rankings(args.from_runs[1])
    rankings, records = {}, []
    for q in questions:
        if q["qid"] in first and q["qid"] in second:
            rankings[q["qid"]] = fusion.reciprocal_rank_fusion([first[q["qid"]], second[q["qid"]]])
            records.append(score_query(q, rankings[q["qid"]]))
    return rankings, records, {"depths": [depth_a, depth_b]}


def prepare_store(args, questions, directory, tokenizer, model):
    """Encode what the run needs and return (store name, encoding stats).

    A run on sampled states encodes only those states, unless the whole dataset is already encoded.
    """
    batch_size = dense.BATCH_SIZES[args.retriever]
    states = {q["pool"] for q in questions} if args.states else None
    if states and not dense.is_complete(directory, args.dataset):
        collection = f"{args.dataset}-{args.states}-states"
        capacity = sum(1 for _ in passage_texts(args.dataset, states))
    else:
        collection, states = args.dataset, None
        # The extra row is part of the shape of the stores already on disk, so it must stay.
        capacity = {"mbe": barexam, "housing": housing, "scotus": goodlaw}[args.dataset].POOL_SIZE + 1
    texts = passage_texts(args.dataset, states)
    stats = dense.encode_store(tokenizer, model, texts, capacity, directory, collection, batch_size)
    return collection, stats


def search_all_states(questions, query_vectors, vectors, row_of):
    """Search all statutes at once, and record how many of the top 10 come from another state."""
    docids, states = [], []

    def texts():
        for row in housing.iter_statutes():
            docids.append(row["idx"])
            states.append(row["state"])
            yield row["text"]

    rows = dense.rows_for_texts(texts(), row_of)
    rankings, records = {}, []
    for start in range(0, len(questions), QUERY_BATCH):
        group = questions[start : start + QUERY_BATCH]
        results = dense.search_store(query_vectors[start : start + QUERY_BATCH], vectors, rows, k=max(KS))
        for q, (positions, _) in zip(group, results, strict=True):
            rankings[q["qid"]] = [docids[i] for i in positions]
            record = score_query(q, rankings[q["qid"]])
            record["other_state@10"] = float(np.mean([states[i] != q["pool"] for i in positions[:10]]))
            records.append(record)
        print(f"all states: {start + len(group)} of {len(questions)} queries", flush=True)
    return rankings, records


def search_each_group(args, questions, query_vectors, vectors, row_of):
    position_of = {q["qid"]: i for i, q in enumerate(questions)}
    rankings, records = {}, []
    for name, docids, texts, group in iter_groups(args, questions):
        rows = dense.rows_for_texts(texts, row_of)
        del texts
        wanted = query_vectors[[position_of[q["qid"]] for q in group]]
        results = dense.search_store(wanted, vectors, rows, k=max(KS))
        for q, (positions, _) in zip(group, results, strict=True):
            rankings[q["qid"]] = [docids[i] for i in positions]
            records.append(score_query(q, rankings[q["qid"]]))
        print(f"{name}: {len(docids)} docs, {len(group)} queries", flush=True)
    return rankings, records


def may_encode_store(args):
    """A smoke run never encodes. A downstream run must search vectors that exist, except on scotus.

    The first full dense scotus run creates its store, because no earlier run could have.
    """
    suite = suite_for(args)
    if suite == "us_downstream":
        return args.dataset == "scotus"
    return suite != "us_smoke"


def run_dense(args, questions):
    model_id = dense.MODELS[args.retriever]
    directory = dense.store_dir(args.retriever)
    if not may_encode_store(args):
        dense.load_store(directory, args.dataset)
    tokenizer, model = dense.load_model(model_id, runlog.model_pin(model_id)["revision"])
    collection, encoding = prepare_store(args, questions, directory, tokenizer, model)
    query_vectors = dense.encode_queries(tokenizer, model, [q["query"] for q in questions])
    del model, tokenizer
    import torch

    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    started = time.time()
    vectors, row_of = dense.load_store(directory, collection)
    if args.dataset == "scotus":
        rows = list(samples.iter_passages("scotus"))
        matrix = vectors[dense.rows_for_texts((r["text"] for r in rows), row_of)].astype(np.float32)
        rankings, records = rank_scotus(questions, rows, lambda i: matrix @ query_vectors[i])
    elif args.scope == "all-states":
        rankings, records = search_all_states(questions, query_vectors, vectors, row_of)
    else:
        rankings, records = search_each_group(args, questions, query_vectors, vectors, row_of)
    throughput = {
        "passages_encoded_in_this_run": encoding["encoded"],
        "encoding_seconds": encoding["seconds"],
        "passages_per_second": encoding["encoded"] / max(encoding["seconds"], 1e-9),
        "stored_rows": len(row_of),
        "search_seconds": time.time() - started,
    }
    return rankings, records, throughput


def main(argv=None):
    args = parse_args(argv)
    started = time.time()
    questions = samples.load_questions(args.dataset, args.split, args.sample, args.limit, args.states)
    if args.rollout:
        questions = expand_queries(questions, args.rollout)
    if args.retriever == "bm25":
        rankings, records, throughput = run_bm25(args, questions)
        model = {"id": "bm25-hand-written", "revision": None}
    elif args.retriever == "hybrid":
        rankings, records, throughput = run_hybrid(args, questions)
        model = {"id": "reciprocal-rank-fusion", "revision": None}
    else:
        rankings, records, throughput = run_dense(args, questions)
        model_id = dense.MODELS[args.retriever]
        model = {"id": model_id, "revision": runlog.model_pin(model_id)["revision"]}
    metrics = {"all": summarize_scotus(records) if args.dataset == "scotus" else aggregate(records)}
    validation = [r for r in records if r["group"] == "validation"]
    if validation:
        metrics["validation"] = aggregate(validation)
    path = runlog.write_run(
        suite_for(args),
        make_config(args, questions),
        samples.data_files(args.dataset) + ([args.rollout] if args.rollout else []),
        model,
        metrics,
        records,
        time.time() - started,
        throughput,
        rankings,
    )
    print(f"wrote {path}")
    if args.dataset == "scotus":
        return
    for key in ("hit@1", "hit@10", "mrr@10", "hit@100", "hit@1000", "all@10", "all@100", "all@1000"):
        print(f"{key} {metrics['all'][key]:.2f}")


if __name__ == "__main__":
    main()
