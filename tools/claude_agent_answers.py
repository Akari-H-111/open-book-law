"""Amendment 1 part D, exploratory: Claude answers through the CLI, with the agent's tools served over MCP.

Start the MCP server first. Each answer is appended to a JSONL file under DATA_ROOT, so a stopped run goes on.
The CLI reports only turns, so this run has no counts of malformed calls or of status checks. The CLI cannot
stop parallel calls within a turn, so `--max-turns` only roughly enforces the budget.
This script is outside the line limit of open_book_law/.
"""

import json
import sys

from open_book_law.agent import loop
from open_book_law.paths import DERIVED_DIR, REPO_ROOT
from open_book_law.prep.goodlaw_questions import CliError, call_claude
from open_book_law.reader import samples
from open_book_law.runlog import append_record, read_partial, save_json
from open_book_law.us import goodlaw

MODEL = "claude-opus-5-5"
OUT = DERIVED_DIR / "agent_traces" / "claude_scotus.jsonl"
SUMMARY = REPO_ROOT / "results" / "summary" / "us_agent_claude.json"
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": list(loop.LETTERS)}},
    "required": ["answer"],
    "additionalProperties": False,
}
EXTRA = [
    "--mcp-config", str(REPO_ROOT / "tools" / "agent_mcp.json"),
    "--allowedTools", "mcp__open-book__search,mcp__open-book__read,mcp__open-book__check_status",
    "--max-turns", str(loop.BUDGET + 1),
]  # fmt: skip
INSTRUCTION = "Use the tools search, read and check_status, at most 5 calls in all, and then answer."


def main(binary="claude"):
    questions = samples.load_questions("scotus")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = read_partial(OUT)
    with open(OUT, "a", encoding="utf-8") as f:
        for q in questions:
            if q["qid"] in records:
                continue
            prompt = f"{loop.question_message(q, 'scotus', goodlaw.TODAY)}\n\n{INSTRUCTION}"
            try:
                reply, usage = call_claude(prompt, MODEL, SCHEMA, binary, EXTRA)
            except CliError as error:
                print(q["qid"], error, flush=True)
                continue
            letter = reply["answer"]
            outcome = {"correct": letter == q["answer"], "superseded": letter == q["superseded_rule"]}
            records[q["qid"]] = {"qid": q["qid"], "predicted": letter, "turns": usage["num_turns"], **outcome}
            append_record(f, records[q["qid"]])
    done = [records[q["qid"]] for q in questions if q["qid"] in records]
    summary = {
        "label": f"exploratory, {MODEL} through the CLI",
        "questions": len(questions),
        "answered": len(done),
        "accuracy": 100 * sum(r["correct"] for r in done) / max(len(done), 1),
        "superseded_rate": 100 * sum(r["superseded"] for r in done) / max(len(done), 1),
        "turns_per_question": sum(r["turns"] or 0 for r in done) / max(len(done), 1),
    }
    save_json(SUMMARY, summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main(*sys.argv[1:])
