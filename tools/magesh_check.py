"""Check Figure 4 of Magesh et al. 2024 against the public half of their data.

Run: ~/venvs/open-book-law/bin/python -I tools/magesh_check.py
Reads the public file dataset.csv and writes results/data_audit/magesh_check.json.
Uses only the standard library.
"""
import csv
import hashlib
import io
import json
import math
import os
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("OBL_DATA", REPO / "data_local"))
DATA = DATA_ROOT / "legal_rag_hallucinations" / "dataset.csv"
OUT = REPO / "results/data_audit/magesh_check.json"

LABELS = ["Accurate", "Incomplete", "Hallucination"]
TOOLS = {"Lexis": "Lexis+ AI", "Westlaw": "Westlaw", "Pract. Law": "Practical Law", "GPT-4": "GPT-4"}

# Figure 4 of the paper, in percent: accurate, incomplete, hallucinated.
PAPER_FIG4 = {
    "Lexis+ AI": [65, 18, 17],
    "Westlaw": [42, 25, 33],
    "Practical Law": [20, 63, 17],
    "GPT-4": [49, 8, 43],
}

# Queries per category in the paper (Appendix A, 202 in total).
PAPER_QUERIES = {
    "Bar Exam": 20, "Rule QA": 20, "Treatment (Doctrinal Agreement)": 20,
    "Doctrine Test": 10, "Question with Irrelevant Context": 10,
    "SCALR": 30, "Circuit Splits": 10, "Changes in Law": 10, "Local Rules": 20,
    "False Holding Statements": 10, "Whimsical Holding Statements": 10,
    "False Judicial Contribution": 2,
    "Metadata: Citation": 10, "Metadata: Year": 10, "Metadata: Author": 10,
}


def wilson(k, n, z=1.96):
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def rebuild_label(correctness, groundedness):
    """Sections 4.1 to 4.4. "Partially Correct" is treated as correct;
    refusals and "Irrelevant / Unhelpful" are treated as refusals."""
    if correctness == "Incorrect":
        return "Hallucination"
    if correctness in ("Refusal", "Irrelevant / Unhelpful"):
        return "Incomplete"
    if groundedness == "Misgrounded":
        return "Hallucination"
    if groundedness == "Ungrounded":
        return "Incomplete"
    return "Accurate"


def main():
    raw = DATA.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))

    # 1. Queries per category (each query has one row per tool).
    per_category = Counter()
    for r in rows:
        if r["Model"] == "GPT-4":
            per_category[r["Question Category"]] += 1
    categories = {
        c: {"public": per_category.get(c, 0), "paper": n}
        for c, n in PAPER_QUERIES.items()
    }

    # 2. Label counts per tool, with 95% Wilson intervals.
    tools = {}
    for key, name in TOOLS.items():
        sub = [r for r in rows if r["Model"] == key]
        counts = Counter(r["Label"] for r in sub)
        n = len(sub)
        cells = {}
        for label, paper in zip(LABELS, PAPER_FIG4[name], strict=True):
            lo, hi = wilson(counts[label], n)
            cells[label] = {
                "count": counts[label], "percent": round(100 * counts[label] / n, 1),
                "wilson_low": round(100 * lo, 1), "wilson_high": round(100 * hi, 1),
                "paper_percent": paper, "paper_inside_interval": 100 * lo <= paper <= 100 * hi,
            }
        tools[name] = {"responses": n, "labels": cells}

    # 3. Rows where the file's Label differs from the label rebuilt from the rules.
    mismatches = Counter()
    for r in rows:
        rebuilt = rebuild_label(r["Correctness"], r["Groundedness"])
        if rebuilt != r["Label"]:
            mismatches[(r["Correctness"], r["Groundedness"], r["Label"], rebuilt)] += 1
    mismatch_list = [
        {"correctness": c, "groundedness": g, "file_label": f, "rebuilt_label": b, "rows": n}
        for (c, g, f, b), n in sorted(mismatches.items())
    ]

    # 4. Reweight each tool's category shares to the paper's category sizes.
    reweighted = {}
    total = sum(PAPER_QUERIES.values())
    for key, name in TOOLS.items():
        shares = {}
        for label in LABELS:
            s = 0.0
            for c, w in PAPER_QUERIES.items():
                sub = [r for r in rows if r["Model"] == key and r["Question Category"] == c]
                s += w / total * sum(r["Label"] == label for r in sub) / len(sub)
            shares[label] = round(100 * s, 1)
        reweighted[name] = {
            "reweighted_percent": shares,
            "max_shift_points": round(
                max(abs(shares[label] - tools[name]["labels"][label]["percent"]) for label in LABELS), 1
            ),
        }

    out = {
        "source_file": "$OBL_DATA/legal_rag_hallucinations/dataset.csv",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows),
        "queries": len(rows) // len(TOOLS),
        "categories": categories,
        "tools": tools,
        "label_rule_mismatches": {"total_rows": sum(mismatches.values()), "groups": mismatch_list},
        "reweighted_to_paper_categories": reweighted,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))


main()
