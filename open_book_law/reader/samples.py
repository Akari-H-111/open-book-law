"""Which questions a run uses.

The two fixed sample files in data/ were written once, from question ids and state names alone, by functions
that this module held at commit f89e35e. Those functions were later removed, and that commit still has them.
"""

import json

import numpy as np

from open_book_law.paths import REPO_ROOT
from open_book_law.prep.caselaw import PASSAGES_GZ, iter_cases
from open_book_law.us import barexam, goodlaw, housing
from open_book_law.us.authority import AUTHORITY_DB

SEED = 20261103
STATE_SPLITS = REPO_ROOT / "data" / "housing_state_splits.json"
SPLITS = ["all", "validation", "confirmatory", "test"]


def add_question_args(parser, default_split):
    parser.add_argument("--dataset", required=True, choices=["mbe", "housing", "scotus"])
    parser.add_argument("--split", default=default_split, choices=SPLITS)
    parser.add_argument("--sample", help="JSON file of housing question ids.")
    parser.add_argument("--limit", type=int, help="Smoke run: a seeded sample of N questions.")
    parser.add_argument("--rerun", type=int, default=0, help="Number that makes the run id of a rerun new.")


def choose_states(states, n):
    """N states chosen at random, for target R2c in Amendment 2. The same N always gives the same states."""
    order = sorted(states)
    picks = np.random.default_rng(SEED).choice(len(order), size=n, replace=False)
    return sorted(order[i] for i in picks)


def load_state_splits():
    with open(STATE_SPLITS, encoding="utf-8") as f:
        return json.load(f)


def load_questions(dataset, split="all", sample=None, limit=None, n_states=None):
    """Keep one split, then a sample file, then N random states, then a seeded limit for smoke runs.

    On mbe, confirmatory means train plus test. On housing, splits are by state and only validation has a use.
    On scotus, a limit keeps the first rows, because those stay the same while the file grows.
    """
    if dataset == "scotus":
        return goodlaw.read_questions()[0][:limit]
    questions = barexam.load_questions() if dataset == "mbe" else housing.load_questions()
    if dataset == "mbe" and split in ("validation", "test"):
        questions = [q for q in questions if q["split"] == split]
    elif dataset == "mbe" and split == "confirmatory":
        questions = [q for q in questions if q["split"] in ("train", "test")]
    elif dataset == "housing" and split != "all":
        states = set(load_state_splits()[split])
        questions = [q for q in questions if q["pool"] in states]
    if sample:
        with open(sample, encoding="utf-8") as f:
            wanted = {qid for qids in json.load(f)["qids_by_state"].values() for qid in qids}
        questions = [q for q in questions if q["qid"] in wanted]
    if n_states:
        chosen = choose_states({q["pool"] for q in questions}, n_states)
        questions = [q for q in questions if q["pool"] in chosen]
    if limit:
        rng = np.random.default_rng(SEED)
        picks = rng.choice(len(questions), size=min(limit, len(questions)), replace=False).tolist()
        questions = [questions[i] for i in sorted(picks)]
    return questions


def data_files(dataset):
    """The downloaded files that a run depends on. Each run file records their hashes."""
    if dataset == "scotus":
        return [goodlaw.QUESTIONS, PASSAGES_GZ, AUTHORITY_DB]
    if dataset == "mbe":
        names = ("qa", *barexam.SPLITS)
        return [barexam.BAREXAM_DIR / f"{name}.csv" for name in names] + [barexam.PASSAGES_ZIP]
    return [housing.QUESTIONS_ZIP, housing.STATUTES_ZIP]


def iter_passages(dataset):
    """Every row of the dataset's whole pool, in file order."""
    if dataset == "scotus":
        return (row | {"idx": row["id"]} for row in iter_cases(PASSAGES_GZ))
    return barexam.iter_pool("full") if dataset == "mbe" else housing.iter_statutes()
