"""Loader for reglab/barexam_qa. Text stays in memory and never reaches a run file.

Query text is prompt + question, without the answer choices. The paper's examples of a "Query" (Tables 7
and 15) show the fact pattern and the question stem and no options, and Table 1 reports an average query
length of 172 tokens for the historical questions. The paper never states the rule in words.
"""

import csv
import io
import re
import sys
import zipfile

from open_book_law.paths import DATA_ROOT

BAREXAM_DIR = DATA_ROOT / "barexam_qa"
PASSAGES_ZIP = BAREXAM_DIR / "passages.tsv.zip"
SPLITS = ("train", "validation", "test")
POOL_SIZE = 856_835
LIBRARIES = {
    "doctrine": {"wex"},
    "cases": {"caselaw"},
    "real": {"wex", "caselaw"},
    "full": {"wex", "caselaw", "mbe"},
}
VALID_SOURCE = re.compile(r"^(MBE-\d{4}(-\d+)?-part\d+|\d{4}(-(Feb|July))?)$")

csv.field_size_limit(sys.maxsize)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_questions(split="all", directory=None):
    """Questions in split-file order. `split` is one split name or "all".

    The split files say which split a question is in. All fields come from qa.csv, because validation.csv has
    an empty `question` for mbe_1121 where qa.csv has the text. The audit reports this difference.
    Rows with a bad `source` field are kept: `source_ok` is False and `source_tag` is "malformed".
    """
    directory = directory or BAREXAM_DIR
    names = SPLITS if split == "all" else (split,)
    full_rows = {row["idx"]: row for row in read_rows(directory / "qa.csv")}
    questions = []
    for name in names:
        for split_row in read_rows(directory / f"{name}.csv"):
            row = full_rows[split_row["idx"]]
            ok = bool(VALID_SOURCE.match(row["source"]))
            questions.append(
                {
                    **row,
                    "qid": row["idx"],
                    "split": name,
                    "query": f"{row['prompt'].strip()} {row['question'].strip()}".strip(),
                    "gold": {row["gold_idx"]},
                    "source_ok": ok,
                    "source_tag": row["source"] if ok else "malformed",
                }
            )
    return questions


def iter_pool(library="full", path=None):
    """Stream pool rows from inside the zip, in file order, keeping one library's sources."""
    sources = LIBRARIES[library]
    with zipfile.ZipFile(path or PASSAGES_ZIP) as archive, archive.open("passages.tsv") as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""), delimiter="\t"):
            if row["source"] in sources:
                yield row
