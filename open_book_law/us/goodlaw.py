"""The good-law questions, in the shape of mbe questions."""

import json
import sqlite3

from open_book_law.paths import DERIVED_DIR
from open_book_law.us.authority import AUTHORITY_DB, status

QUESTIONS = DERIVED_DIR / "goodlaw" / "questions.jsonl"
POOL_SIZE = 1_007_513
TODAY = "2026-11-03"  # Fixed, so that a rerun gives the same answer. The table is current to June 2026.


def connect():
    """A read-only connection that another thread may use, because an MCP server may call from one."""
    return sqlite3.connect(f"file:{AUTHORITY_DB}?mode=ro", uri=True, check_same_thread=False)


def read_questions(conn=None):
    """Return (kept, left out) in file order. Amendment 3: a question leaves if its new decision was overruled."""  # noqa: E501
    with open(QUESTIONS, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.endswith("\n")]
    conn = conn or connect()
    kept, left_out = [], []
    for row in rows:
        shaped = {f"choice_{letter.lower()}": text for letter, text in row["options"].items()}
        shaped |= {"qid": row["pair_id"], "query": row["question"], "answer": row["current_rule"]}
        overruled = status(conn, row["new_id"], TODAY)["overruled_by"]
        (left_out if overruled else kept).append(row | shaped | {"split": "overruled"})
    return kept, left_out


def both_forms_correct(before, today):
    """Percent of questions that the runs `date-before` and `date-today` both answered correctly."""
    first = {r["qid"]: r["correct"] for r in before["per_query"]}
    second = {r["qid"]: r["correct"] for r in today["per_query"]}
    if set(first) != set(second):
        raise ValueError("the two runs cover different questions")
    return 100 * sum(first[qid] * second[qid] for qid in first) / len(first)


def case_of(docid):
    """The case id inside a passage id, case:opinion:position. A Cornell case id has a colon of its own."""
    return docid.rsplit(":", 2)[0]
