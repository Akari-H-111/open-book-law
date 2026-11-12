"""Fine-tune e5-small on housing, then compare it with the zero-shot model on held-out states (H6).

`train` learns from question and gold-statute pairs of the training states. It reports R@10 on validation
states against gold plus a fixed sample of other statutes, because each epoch cannot encode whole states.
That number only compares settings. `eval` encodes the statutes of one split with the tuned model and searches
within each state. It compares with zero-shot e5-small vectors and reports question groups unseen in training.
"""

import argparse
import time

import numpy as np

from open_book_law import runlog
from open_book_law.evalx import hit_at_k
from open_book_law.paths import DERIVED_DIR
from open_book_law.reader import samples
from open_book_law.retrieval import dense
from open_book_law.us import housing

MODEL_ID = dense.MODELS["e5-small"]
SEED = 20261103
TRAIN_MAX_LENGTH = 256


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["train", "eval"])
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.01)
    parser.add_argument("--val-docs", type=int, default=20_000, help="Train: statutes per validation state.")
    parser.add_argument("--limit-pairs", type=int, help="Train smoke run: train on N pairs.")
    parser.add_argument("--model-run", help="Eval: the run id of the training run.")
    parser.add_argument("--split", default="validation", choices=["validation", "test"])
    parser.add_argument("--rerun", type=int, default=0, help="Number that makes the run id of a rerun new.")
    return parser.parse_args(argv)


def mnr_loss(query_vectors, passage_vectors, temperature):
    """Multiple-negatives ranking loss: each query's own passage against the other passages of the batch."""
    import torch

    logits = query_vectors @ passage_vectors.T / temperature
    return torch.nn.functional.cross_entropy(logits, torch.arange(len(logits), device=logits.device))


def make_batches(pairs, batch_size, rng):
    """Shuffled batches in which no question text or statute text repeats, since a repeat is a false negative.

    Housing asks the same question text in many states, so a check on the question id alone is not enough.
    """
    pending = [pairs[i] for i in rng.permutation(len(pairs))]
    batches = []
    while pending:
        batch, later, seen = [], [], set()
        for pair in pending:
            keys = (("query", pair["query"]), ("text", pair["text"]))
            if len(batch) < batch_size and not seen.intersection(keys):
                batch.append(pair)
                seen.update(keys)
            else:
                later.append(pair)
        pending = later
        if len(batch) > 1:
            batches.append(batch)
    return batches


def load_pools(splits, limit_pairs, val_docs):
    """Questions of each split, training pairs, and a reduced statute pool for each validation state."""
    questions = {name: [] for name in ("train", "validation", "test")}
    split_of = {state: name for name in questions for state in splits[name]}
    for q in housing.load_questions():
        questions[split_of[q["pool"]]].append(q)
    wanted = {}
    for q in questions["train"]:
        for docid in q["gold"]:
            wanted.setdefault(docid, []).append(q)
    gold_validation = {d for q in questions["validation"] for d in q["gold"]}
    rng = np.random.default_rng(SEED)
    pairs, pools = [], {}
    for state, rows in housing.iter_states():
        if split_of.get(state) == "train":
            for row in rows:
                pairs += [
                    {"qid": q["qid"], "query": q["query"], "text": row["text"]}
                    for q in wanted.get(row["idx"], [])
                ]
        elif split_of.get(state) == "validation":
            keep = set(rng.choice(len(rows), size=min(val_docs, len(rows)), replace=False).tolist())
            pools[state] = [r for i, r in enumerate(rows) if i in keep or r["idx"] in gold_validation]
    if limit_pairs:
        pairs = [pairs[i] for i in rng.choice(len(pairs), size=min(limit_pairs, len(pairs)), replace=False)]
    return questions, pairs, pools


def validation_r10(tokenizer, model, questions, pools, batch_size=64):
    """R@10 in percent over validation questions, searching within each state's reduced pool."""
    hits = []
    for state, rows in pools.items():
        group = [q for q in questions if q["pool"] == state]
        if group:
            parts = [
                dense.encode_batch(
                    tokenizer, model, [f"passage: {r['text']}" for r in rows[start : start + batch_size]]
                )
                for start in range(0, len(rows), batch_size)
            ]
            queries = dense.encode_queries(tokenizer, model, [q["query"] for q in group])
            results = dense.search_store(queries, np.concatenate(parts), np.arange(len(rows)), k=10)
            for q, (positions, _) in zip(group, results, strict=True):
                hits.append(hit_at_k([rows[i]["idx"] for i in positions], q["gold"], 10))
    return 100 * sum(hits) / len(hits)


def train(args):
    import torch

    # Seeds dropout too. Runs before Amendment 8 seeded only NumPy, so they cannot be repeated exactly.
    torch.manual_seed(SEED)
    started = time.time()
    config = {
        "mode": "train",
        "model": MODEL_ID,
        "seed": SEED,
        "rerun": args.rerun,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "temperature": args.temperature,
        "train_max_length": TRAIN_MAX_LENGTH,
        "val_docs": args.val_docs,
        "limit_pairs": args.limit_pairs,
    }
    rid = runlog.run_id(config)
    questions, pairs, pools = load_pools(samples.load_state_splits(), args.limit_pairs, args.val_docs)
    validation = questions["validation"]
    tokenizer, model = dense.load_model(MODEL_ID, runlog.model_pin(MODEL_ID)["revision"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    rng = np.random.default_rng(SEED)
    log = [{"epoch": 0, "validation_r@10": validation_r10(tokenizer, model, validation, pools)}]
    print(log[0], flush=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        begun, losses = time.time(), []
        for batch in make_batches(pairs, args.batch_size, rng):
            q = dense.pooled_vectors(
                tokenizer, model, [f"query: {p['query']}" for p in batch], TRAIN_MAX_LENGTH
            )
            d = dense.pooled_vectors(
                tokenizer, model, [f"passage: {p['text']}" for p in batch], TRAIN_MAX_LENGTH
            )
            loss = mnr_loss(q, d, args.temperature)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        model.eval()
        log.append(
            {
                "epoch": epoch,
                "mean_loss": float(np.mean(losses)),
                "seconds": time.time() - begun,
                "validation_r@10": validation_r10(tokenizer, model, validation, pools),
            }
        )
        print(log[-1], flush=True)
    model_dir = DERIVED_DIR / "models" / f"ft-small-{rid}"
    model.save_pretrained(model_dir, safe_serialization=True)
    tokenizer.save_pretrained(model_dir)
    path = runlog.write_run(
        "us_smoke" if args.limit_pairs else "us_finetune",
        config,
        [housing.QUESTIONS_ZIP, housing.STATUTES_ZIP, samples.STATE_SPLITS],
        {
            "id": MODEL_ID,
            "revision": runlog.model_pin(MODEL_ID)["revision"],
            "saved_to": runlog.portable(model_dir),
        },
        {"training_pairs": len(pairs), "log": log},
        [],
        time.time() - started,
        {},
    )
    print(f"wrote {path} and {model_dir}")


def rank_within_states(tokenizer, model, directory, collection, questions, states):
    """Rankings per question within its state, from a complete store."""
    vectors, row_of = dense.load_store(directory, collection)
    rankings = {}
    for state, rows in housing.iter_states():
        group = [q for q in questions if q["pool"] == state]
        if state in states and group:
            positions = dense.rows_for_texts([r["text"] for r in rows], row_of)
            queries = dense.encode_queries(tokenizer, model, [q["query"] for q in group])
            results = dense.search_store(queries, vectors, positions, k=100)
            for q, (picks, _) in zip(group, results, strict=True):
                rankings[q["qid"]] = [rows[i]["idx"] for i in picks]
    return rankings


def evaluate(args):
    started = time.time()
    config = {
        "mode": "eval",
        "model": MODEL_ID,
        "seed": SEED,
        "rerun": args.rerun,
        "model_run": args.model_run,
        "split": args.split,
        "max_length": dense.MAX_LENGTH,
    }
    splits = samples.load_state_splits()
    states = set(splits[args.split])
    every = housing.load_questions()
    seen_groups = {q["question_group"] for q in every if q["pool"] in splits["train"]}
    questions = [q for q in every if q["pool"] in states]

    def texts():
        return (r["text"] for state, rows in housing.iter_states() if state in states for r in rows)

    capacity = sum(1 for _ in texts())
    tuned_dir = dense.store_dir(f"ft-small-{args.model_run}")
    tuned_path = DERIVED_DIR / "models" / f"ft-small-{args.model_run}"
    tokenizer, tuned = dense.load_model(tuned_path)
    collection = f"housing-{args.split}"
    encoded = dense.encode_store(
        tokenizer, tuned, texts(), capacity, tuned_dir, collection, dense.BATCH_SIZES["e5-small"]
    )
    tuned_rank = rank_within_states(tokenizer, tuned, tuned_dir, collection, questions, states)
    del tuned
    base_revision = runlog.model_pin(MODEL_ID)["revision"]
    tokenizer, base = dense.load_model(MODEL_ID, base_revision)
    zero_rank = rank_within_states(tokenizer, base, dense.store_dir("e5-small"), "housing", questions, states)
    records = []
    for q in questions:
        record = {
            "qid": q["qid"],
            "group": q["pool"],
            "question_group": q["question_group"],
            "unseen_group": q["question_group"] not in seen_groups,
        }
        for k in (10, 100):
            record[f"hit@{k}"] = hit_at_k(tuned_rank[q["qid"]], q["gold"], k)
            record[f"zero_hit@{k}"] = hit_at_k(zero_rank[q["qid"]], q["gold"], k)
        records.append(record)
    metrics = {
        "all": summarize(records),
        "unseen_groups": summarize([r for r in records if r["unseen_group"]]),
    }
    path = runlog.write_run(
        "us_finetune",
        config,
        [housing.QUESTIONS_ZIP, housing.STATUTES_ZIP, samples.STATE_SPLITS],
        {"id": runlog.portable(tuned_path), "revision": None, "base": MODEL_ID,
         "base_revision": base_revision},
        metrics,
        records,
        time.time() - started,
        {"passages_encoded": encoded["encoded"], "encoding_seconds": encoded["seconds"]},
    )
    print(f"wrote {path}: {metrics}")


def summarize(records):
    """Percentages over the records; None for an empty subset, since it has no rate."""
    keys = ("hit@10", "hit@100", "zero_hit@10", "zero_hit@100")
    summary = {key: 100 * sum(r[key] for r in records) / len(records) if records else None for key in keys}
    return {**summary, "questions": len(records)}


def main(argv=None):
    args = parse_args(argv)
    train(args) if args.mode == "train" else evaluate(args)


if __name__ == "__main__":
    main()
