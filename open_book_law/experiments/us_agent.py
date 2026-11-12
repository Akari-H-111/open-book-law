"""Amendment 1 part D: run the agent and write a run file that holds only counts. mbe uses validation or test.

Full traces go to DATA_ROOT/derived/agent_traces/<run id>.jsonl, which also lets a stopped run continue."""

import argparse
import time

from open_book_law import runlog
from open_book_law.agent import loop, tools
from open_book_law.paths import DERIVED_DIR
from open_book_law.reader import mlx_reader, samples
from open_book_law.us import goodlaw

TRACE_DIR = DERIVED_DIR / "agent_traces"
MAX_NEW_TOKENS = 200


def chat_ids(tokenizer, messages, reader, opening=""):
    extra = {"enable_thinking": False} if reader == "qwen3" else {}
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **extra)
    return tokenizer.encode(rendered + opening, add_special_tokens=False)


def score(q, result):
    """`ignored_status`: check_status said overruled, and the answer is still the old rule. Not on mbe."""
    superseded = float(result["predicted"] == q.get("superseded_rule"))
    ignored = bool(result["saw_overruled"] and superseded)
    extra = {"qid": q["qid"], "group": q["split"], "correct": float(result["predicted"] == q["answer"])}
    return result | extra | {"superseded": superseded, "ignored_status": ignored}


def summarize_agent(records):
    n, turns = len(records), sum(r["turns"] for r in records)
    malformed = sum(r["malformed"] for r in records)
    return {
        "questions": n,
        "accuracy": 100 * sum(r["correct"] for r in records) / n,
        "superseded_rate": 100 * sum(r["superseded"] for r in records) / n,
        "tool_calls_per_question": sum(r["tool_calls"] for r in records) / n,
        "malformed_share": 100 * malformed / max(turns, 1),
        "valid_turn_share": 100 * (turns - malformed) / max(turns, 1),
        "tool_call_budget": loop.BUDGET,
        "malformed_limit": loop.MAX_MALFORMED,
        "budget_exhausted": sum(r["stop"] == "tool_budget" for r in records),
        "malformed_limit_hit": sum(r["stop"] == "malformed_limit" for r in records),
        "ignored_status": sum(r["ignored_status"] for r in records),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    samples.add_question_args(parser, default_split="validation")
    parser.add_argument("--reader", required=True, choices=["qwen3", "phi4"])
    parser.add_argument("--library", required=True, help="scotus, or an mbe library.")
    parser.add_argument("--retriever", required=True)
    args = parser.parse_args(argv)
    started = time.time()
    limits = {"budget": loop.BUDGET, "max_malformed": loop.MAX_MALFORMED}
    config = vars(args) | limits | {"tokens": MAX_NEW_TOKENS, "prompt": loop.PROMPT_VERSION}
    questions = samples.load_questions(args.dataset, args.split, args.sample, args.limit)
    model, tokenizer = mlx_reader.load_reader(args.reader)
    token_ids = mlx_reader.label_token_ids(tokenizer, loop.LETTERS)
    tools_now = tools.open_tools(args.library, args.retriever)

    def generate(messages):
        ids = chat_ids(tokenizer, messages, args.reader)
        return mlx_reader.generate(model, tokenizer, ids, MAX_NEW_TOKENS)[0]

    def force_answer(messages):
        # Open the JSON answer for the model, and take the letter that its next token scores highest.
        ids = chat_ids(tokenizer, messages, args.reader, opening='{"answer": "')
        probabilities = mlx_reader.score_labels(model, ids, token_ids)[0]
        return max(loop.LETTERS, key=lambda letter: probabilities[letter])

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"{runlog.run_id(config)}.jsonl"
    records = runlog.read_partial(trace_path)
    with open(trace_path, "a", encoding="utf-8") as trace:
        for done, q in enumerate(questions, start=1):
            if q["qid"] not in records:
                result = loop.run_question(q, args.library, goodlaw.TODAY, tools_now, generate, force_answer)
                records[q["qid"]] = score(q, result)
                runlog.append_record(trace, records[q["qid"]])
                print(f"{done}/{len(questions)} {time.time() - started:.0f} s", flush=True)
    ordered = [records[q["qid"]] for q in questions]
    counts = [{key: value for key, value in r.items() if key != "trace"} for r in ordered]
    elapsed = time.time() - started
    model_id = mlx_reader.READERS[args.reader]
    pin = {"id": model_id, "revision": runlog.model_pin(model_id)["revision"]}
    suite, data = "us_smoke" if args.limit else "us_agent", samples.data_files(args.dataset)
    metrics, speed = {"all": summarize_agent(ordered)}, {"seconds_per_question": elapsed / len(ordered)}
    print(runlog.write_run(suite, config, data, pin, metrics, counts, elapsed, speed), metrics["all"])


if __name__ == "__main__":
    main()
