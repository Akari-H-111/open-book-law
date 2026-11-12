"""Write results/data_audit/us_audit.json, as section 2 of the preregistration asks. Only ids and counts."""

import hashlib
import json
import re
from collections import Counter, defaultdict

from open_book_law.paths import REPO_ROOT
from open_book_law.us import barexam, housing

AUDIT_PATH = REPO_ROOT / "results" / "data_audit" / "us_audit.json"
JACCARD = 0.8


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def digest(text):
    return hashlib.sha1(text.encode()).digest()


def char_grams(text, n=5):
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def near_duplicate_pairs(texts, threshold=JACCARD):
    """Pairs of positions with character 5-gram Jaccard >= threshold. Very different sizes cannot reach it."""
    grams = [char_grams(normalize(t)) for t in texts]
    pairs = []
    for i, a in enumerate(grams):
        for j in range(i + 1, len(grams)):
            b = grams[j]
            if a and b and min(len(a), len(b)) >= threshold * max(len(a), len(b)):
                shared = len(a & b)
                score = shared / (len(a) + len(b) - shared)
                if score >= threshold:
                    pairs.append((i, j, round(score, 4)))
    return pairs


def source_year(tag):
    if tag == "malformed":
        return "malformed"
    return re.search(r"\d{4}(-\d{2})?", tag).group(0)


def audit_duplicates(questions):
    """Exact and near duplicates of the query text, within and across splits."""
    texts = [q["query"] for q in questions]
    groups = defaultdict(list)
    for i, text in enumerate(texts):
        groups[digest(normalize(text))].append(i)
    exact = [g for g in groups.values() if len(g) > 1]
    pair_rows, counts = [], Counter()
    for i, j, score in near_duplicate_pairs(texts):
        a, b = questions[i], questions[j]
        kind = "within" if a["split"] == b["split"] else "across"
        same_prompt = bool(a["prompt"].strip()) and a["prompt"] == b["prompt"]
        counts[f"{kind}_split"] += 1
        counts[f"{kind}_split_same_prompt"] += same_prompt
        pair_rows.append({"a": a["qid"], "b": b["qid"], "jaccard": score, "same_prompt": same_prompt})
    return {
        "exact_groups": [[questions[i]["qid"] for i in g] for g in exact],
        "exact_groups_across_splits": sum(len({questions[i]["split"] for i in g}) > 1 for g in exact),
        "near_duplicate_pair_counts": dict(counts),
        "near_duplicate_pairs": pair_rows,
    }


def split_file_differences():
    """Fields where a split file disagrees with qa.csv. This is why the loader takes its text from qa.csv."""
    qa_rows = {r["idx"]: r for r in barexam.read_rows(barexam.BAREXAM_DIR / "qa.csv")}
    differences = []
    for split in barexam.SPLITS:
        for row in barexam.read_rows(barexam.BAREXAM_DIR / f"{split}.csv"):
            for field, value in qa_rows[row["idx"]].items():
                if row[field] != value:
                    differences.append({"qid": row["idx"], "split": split, "field": field})
    return differences


def audit_barexam():
    questions = barexam.load_questions()
    gold_ids = {q["gold_idx"] for q in questions}
    gold_texts = {digest(normalize(q["gold_passage"])) for q in questions}
    pool_counts, distinct_text, source_of_gold = Counter(), set(), {}
    rows_with_gold_text = defaultdict(list)
    for row in barexam.iter_pool("full"):
        pool_counts[row["source"]] += 1
        distinct_text.add(digest(row["text"]))
        if row["idx"] in gold_ids:
            source_of_gold[row["idx"]] = row["source"]
        text = digest(normalize(row["text"]))
        if text in gold_texts:
            rows_with_gold_text[text].append((row["idx"], row["source"]))

    same_text_elsewhere = []
    for q in questions:
        rows = rows_with_gold_text[digest(normalize(q["gold_passage"]))]
        hits = [(i, s) for i, s in rows if i != q["gold_idx"] and s != "mbe"]
        if hits:
            same_text_elsewhere.append({"qid": q["qid"], "gold_idx": q["gold_idx"], "pool_rows": hits})
    gold_use = Counter(q["gold_idx"] for q in questions)
    return {
        "questions": len(questions),
        "by_split": dict(Counter(q["split"] for q in questions)),
        "by_source_year": dict(Counter(source_year(q["source_tag"]) for q in questions)),
        "by_subject_tag": dict(Counter(q["subject"] or "(blank)" for q in questions)),
        "malformed_question_rows": [
            {
                "qid": q["qid"],
                "split": q["split"],
                "gold_idx": q["gold_idx"],
                "source_chars": len(q["source"]),
                "source_equals_gold_passage": q["source"] == q["gold_passage"],
            }
            for q in questions
            if not q["source_ok"]
        ],
        "split_file_differs_from_qa_file": split_file_differences(),
        "duplicates_by_query": audit_duplicates(questions),
        "pool_rows": sum(pool_counts.values()),
        "pool_by_source": dict(pool_counts),
        "pool_distinct_texts": len(distinct_text),
        "gold_passages": {
            "questions_by_pool_source_of_gold": dict(
                Counter(source_of_gold.get(q["gold_idx"], "not_in_pool") for q in questions)
            ),
            "distinct_gold_idx": len(gold_use),
            "gold_idx_shared_by_several_questions": sum(v > 1 for v in gold_use.values()),
            "questions_sharing_a_gold_idx": sum(v for v in gold_use.values() if v > 1),
            "questions_with_gold_text_identical_to_caselaw_or_wex": same_text_elsewhere,
        },
    }


def audit_housing():
    questions = housing.load_questions()
    gold_ids = {g for q in questions for g in q["gold"]}
    statute_state, statutes_per_state = {}, Counter()
    for row in housing.iter_statutes():
        statutes_per_state[row["state"]] += 1
        if row["idx"] in gold_ids:
            statute_state[row["idx"]] = row["state"]

    missing_gold = wrong_state = 0
    for q in questions:
        for gold in q["gold"]:
            if gold not in statute_state:
                missing_gold += 1
            elif statute_state[gold] != q["pool"]:
                wrong_state += 1
    question_states = {q["pool"] for q in questions}
    return {
        "questions": len(questions),
        "question_groups": len({q["question_group"] for q in questions}),
        "gold_statutes_per_question": {
            str(k): v for k, v in sorted(Counter(len(q["gold"]) for q in questions).items())
        },
        "gold_list_entries_per_question_before_removing_repeats": {
            str(k): v for k, v in sorted(Counter(len(q["statutes"]) for q in questions).items())
        },
        "statute_rows": sum(statutes_per_state.values()),
        "statutes_per_state": dict(statutes_per_state),
        "jurisdictions_with_questions": len(question_states),
        "jurisdictions_with_statutes_but_no_questions": sorted(set(statutes_per_state) - question_states),
        "gold_entries_not_in_pool": missing_gold,
        "gold_entries_in_another_state": wrong_state,
    }


def main():
    report = {"barexam_qa": audit_barexam(), "housing_qa": audit_housing()}
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {AUDIT_PATH}")


if __name__ == "__main__":
    main()
