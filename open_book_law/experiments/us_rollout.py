"""Generate structured reasoning rollouts with a local reader. Text stays under DATA_ROOT, not in run files.

The prompts are the paper's Tables 13 and 14. The paper used GPT-3.5, and this is a replication with another
generator: temperature 0, at most 256 new tokens. `us_retrieval --rollout PATH` then searches with the result.
"""

import argparse
import hashlib
import time

from open_book_law import runlog
from open_book_law.paths import DERIVED_DIR
from open_book_law.reader import mlx_reader, prompts, samples

ROLLOUT_DIR = DERIVED_DIR / "rollouts"
MAX_NEW_TOKENS = 256


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    samples.add_question_args(parser, default_split="validation")
    parser.add_argument("--reader", default="llama8", choices=list(mlx_reader.READERS))
    args = parser.parse_args(argv)
    if args.limit and args.split != "validation":
        parser.error("smoke runs use --split validation")
    started = time.time()
    config = {
        "dataset": args.dataset,
        "reader": args.reader,
        "split": args.split,
        "sample": args.sample,
        "limit": args.limit,
        "rerun": args.rerun,
        "prompt_version": prompts.PROMPT_VERSION,
        "temperature": 0,
        "max_new_tokens": MAX_NEW_TOKENS,
    }
    questions = samples.load_questions(args.dataset, args.split, args.sample, args.limit)
    model, tokenizer = mlx_reader.load_reader(args.reader)
    ROLLOUT_DIR.mkdir(parents=True, exist_ok=True)
    path = ROLLOUT_DIR / f"{args.dataset}-{args.reader}-{prompts.PROMPT_VERSION}.jsonl"
    cached = runlog.read_partial(path)
    with open(path, "a", encoding="utf-8") as f:
        for q in questions:
            if q["qid"] not in cached:
                ids = prompts.prompt_ids(tokenizer, prompts.rollout_text(args.dataset, q), args.reader)
                text, n_tokens, stopped = mlx_reader.generate(model, tokenizer, ids, MAX_NEW_TOKENS)
                cached[q["qid"]] = {"qid": q["qid"], "text": text, "tokens": n_tokens, "stopped": stopped}
                runlog.append_record(f, cached[q["qid"]])
                print(f"{len(cached)} rollouts", flush=True)
    records = [
        {
            "qid": q["qid"],
            "tokens": cached[q["qid"]]["tokens"],
            "stopped": cached[q["qid"]]["stopped"],
            "text_sha1": hashlib.sha1(cached[q["qid"]]["text"].encode()).hexdigest(),
        }
        for q in questions
    ]
    model_id = mlx_reader.READERS[args.reader]
    output = runlog.write_run(
        "us_smoke" if args.limit else "us_rollouts",
        config,
        [path],
        {"id": model_id, "revision": runlog.model_pin(model_id)["revision"]},
        {"all": {"questions": len(records), "hit_token_limit": sum(not r["stopped"] for r in records)}},
        records,
        time.time() - started,
        {},
    )
    print(f"wrote {output} and rollouts in {path}")


if __name__ == "__main__":
    main()
