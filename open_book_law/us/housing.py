"""Loader for reglab/housing_qa, split rc_questions. Text never reaches a run file.

Assumptions, each checked or labelled in docs/REPRODUCTION.md:
- Query text is the `question` field alone. Table 8 of the paper shows the query with the jurisdiction in a
  separate row, and the search is already limited to one jurisdiction.
- Passage text is the `text` field alone, with no citation or path. Table 8 shows statute text only.
- A question's pool is the statutes whose `state` equals the question's lowercased `state`.
  The 51 pools run from 10,676 to 155,974 statutes, the same range that section 5.2 of the paper gives.
- Gold is the set of `statute_idx` values of the question, kept for every question as published.
"""

import csv
import io
import json
import sys
import zipfile

from open_book_law.paths import DATA_ROOT

HOUSING_DIR = DATA_ROOT / "housing_qa"
QUESTIONS_ZIP = HOUSING_DIR / "questions.json.zip"
STATUTES_ZIP = HOUSING_DIR / "statutes.tsv.zip"
POOL_SIZE = 1_837_403

csv.field_size_limit(sys.maxsize)


def load_questions(path=None):
    with zipfile.ZipFile(path or QUESTIONS_ZIP) as archive, archive.open(archive.namelist()[0]) as f:
        rows = json.load(f)
    return [
        {
            **row,
            "qid": str(row["idx"]),
            "pool": row["state"].lower(),
            "query": row["question"].strip(),
            "gold": {str(s["statute_idx"]) for s in row["statutes"]},
        }
        for row in rows
    ]


def iter_statutes(path=None):
    """Stream statute rows from inside the zip, in file order."""
    with zipfile.ZipFile(path or STATUTES_ZIP) as archive, archive.open("statutes.tsv") as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""), delimiter="\t")


def iter_states(path=None):
    """Yield (state, rows) one jurisdiction at a time, so that only one state's text is in memory."""
    current, rows = None, []
    for row in iter_statutes(path):
        if row["state"] != current:
            if current is not None:
                yield current, rows
            current, rows = row["state"], []
        rows.append(row)
    if current is not None:
        yield current, rows
