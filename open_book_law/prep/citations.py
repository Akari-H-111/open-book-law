"""Find U.S. Reports citations in text, and turn every form into one canonical string, "410 U.S. 113".

The early reporters were later numbered into the U.S. Reports, with the same page numbers:
14 Pet. 60 and 39 U.S. (14 Pet.) 60 are the same citation as 39 U.S. 60.
Short forms such as "410 U.S., at 150" do not match, because they repeat a citation and name no first page.
"""

import json
import random
import re
from collections import Counter

from open_book_law.paths import REPO_ROOT

# Reporter name: (number to add to its volume to get the U.S. volume, its last volume).
NOMINATIVE = {
    "Dallas": (0, 4), "Dall": (0, 4),
    "Cranch": (4, 9), "Cr": (4, 9),
    "Wheaton": (13, 12), "Wheat": (13, 12),
    "Peters": (25, 16), "Pet": (25, 16),
    "Howard": (41, 24), "How": (41, 24),
    "Black": (65, 2),
    "Wallace": (67, 23), "Wall": (67, 23),
}  # fmt: skip
NAMES = "|".join(NOMINATIVE)
SEED = 20261103
SAMPLE_OPINIONS = 500
REVIEW_SIZE = 20
US_REPORTERS = frozenset(
    "U.S Dall Dallas Cranch Cr Wheat Wheaton Pet Peters How Howard Black Wall Wallace".split()
)
MIN_WORDS_LONG = 300
REVIEW_JSONL = REPO_ROOT / "data" / "citation_review.jsonl"
OVERRULED_LATE_YEAR = 2021
US_FORM = re.compile(
    rf"(?<![\d.-])(?P<volume>\d{{1,3}})\s+U\.?\s?S\.?\s*"
    rf"(?:\(\s*\d{{1,2}}\s+(?:{NAMES})\.?\s*\)\s*)?(?P<page>\d{{1,4}})\b"
)
NOMINATIVE_FORM = re.compile(
    rf"(?<![\d.-])(?P<volume>\d{{1,2}})\s+(?P<name>{NAMES})\.?,?\s+(?P<page>\d{{1,4}})\b"
)
YEAR_IN_PARENS = re.compile(r"\((?:[^()]{0,40}\s)?(\d{4})\)")


def canonical(volume, page):
    return f"{int(volume)} U.S. {int(page)}"


def extract(text):
    """Return the canonical citations in the text, in order of first appearance, without repeats."""
    found = [(m.start(), canonical(m["volume"], m["page"])) for m in US_FORM.finditer(text)]
    for m in NOMINATIVE_FORM.finditer(text):
        offset, last_volume = NOMINATIVE[m["name"]]
        # A volume that this reporter never had is not a citation.
        if 1 <= int(m["volume"]) <= last_volume:
            found.append((m.start(), canonical(int(m["volume"]) + offset, m["page"])))
    return list(dict.fromkeys(cite for _, cite in sorted(found)))


def normalize(cite):
    """Return the canonical form of one citation string, or None if it is not a U.S. Reports citation."""
    found = extract(cite or "")
    return found[0] if found else None


def reference_cites(case, opinion_index):
    """CAP's U.S. Reports citations for one opinion, from their printed form.

    CAP's link paths are not used, because their page can differ from the first page: 377 U. S. 271 links to
    /us/377/0403-01. An index of -1 means the head matter, so it never counts for an opinion.
    Returns (canonical citations, printed forms that we could not turn into a citation).
    """
    cites, unreadable = set(), []
    for cited in case["cites_to"]:
        if cited["opinion_index"] == opinion_index and (cited["reporter"] or "").rstrip(",.") in US_REPORTERS:
            found = normalize(cited["cite"])
            if found:
                cites.add(found)
            else:
                unreadable.append(cited["cite"])
    return cites, unreadable


def sample_opinions(cases_factory, min_words):
    """Choose opinions at random among those with text. Returns (case id, opinion) pairs and the total."""
    keys = [
        (case["id"], i)
        for case in cases_factory()
        for i, opinion in enumerate(case["opinions"])
        if opinion["text"].strip() and len(opinion["text"].split()) >= min_words
    ]
    return set(random.Random(SEED).sample(keys, SAMPLE_OPINIONS)), len(keys)


def score_sample(cases_factory, min_words=0):
    """Compare the regex with CAP metadata on the sample. Return totals and every disagreement."""
    chosen, population = sample_opinions(cases_factory, min_words)
    agreed = regex_only = cap_only = unreadable_total = 0
    disagreements = []
    for case in cases_factory():
        for i, opinion in enumerate(case["opinions"]):
            if (case["id"], i) in chosen:
                found = set(extract(opinion["text"]))
                reference, unreadable = reference_cites(case, i)
                agreed += len(found & reference)
                regex_only += len(found - reference)
                cap_only += len(reference - found) + len(unreadable)
                unreadable_total += len(unreadable)
                where = {"case_id": case["id"], "opinion": i, "year": case["date"][:4]}
                disagreements += [where | {"cite": c, "side": "regex"} for c in sorted(found - reference)]
                disagreements += [
                    where | {"cite": c, "side": "cap"} for c in sorted(reference - found) + unreadable
                ]
    summary = {
        "true_positive": agreed,
        "false_positive": regex_only,
        "false_negative": cap_only,
        "precision": agreed / (agreed + regex_only) if agreed + regex_only else None,
        "recall": agreed / (agreed + cap_only) if agreed + cap_only else None,
        "opinions_scored": len(chosen),
        "opinions_available": population,
        "seed": SEED,
        "unreadable_reference": unreadable_total,
    }
    return summary, disagreements


def review_sample(required, spare):
    """The disagreements that a reviewer read: all of `required`, then random ones up to 20."""
    missing = max(0, REVIEW_SIZE - len(required))
    return required[:REVIEW_SIZE] + random.Random(SEED).sample(spare, min(missing, len(spare)))


def audit_pool(pool_rows, pairs, scotus_ids):
    """Section 8.4: count pool passages that cite an overruled decision, and test the pool's dates.

    A decision counts as overruled "after 2021" if its first overruling came after 2021. It was still good law
    when the pool's opinions were written, if they do date from 2019 to 2021. Only full citations count.
    """
    decisions, without_cite = {}, set()
    for pair in pairs:
        if pair["old_canonical"]:
            decision = decisions.setdefault(pair["old_canonical"], {"name": pair["old_name"], "years": []})
            decision["years"].append(pair["new_year"])
        else:
            without_cite.add((pair["old_name"], pair["old_year"]))
    per_decision, by_source, newest_by_case, scanned = Counter(), Counter(), {}, Counter()
    for row in pool_rows:
        scanned[row["source"]] += 1
        for cite in extract(row["text"]):
            if cite in decisions:
                per_decision[cite] += 1
                late = min(decisions[cite]["years"]) > OVERRULED_LATE_YEAR
                by_source[f"{row['source']}/{'after_2021' if late else 'by_2021'}"] += 1
        if row["source"] == "caselaw" and row["case_id"]:
            case_id = row["case_id"].split(".")[0]
            years = [int(y) for y in YEAR_IN_PARENS.findall(row["text"]) if 1700 < int(y) < 2030]
            newest_by_case[case_id] = max(newest_by_case.get(case_id, 0), *years, 0)
    rows = [
        {
            "cite": cite,
            "name": decisions[cite]["name"],
            "first_overruled": min(decisions[cite]["years"]),
            "passages": per_decision[cite],
        }
        for cite in sorted(decisions, key=lambda c: (-per_decision[c], c))
    ]
    late_rows = [r for r in rows if r["first_overruled"] > OVERRULED_LATE_YEAR]
    early_rows = [r for r in rows if r["first_overruled"] <= OVERRULED_LATE_YEAR]
    return {
        "passages_scanned": dict(sorted(scanned.items())),
        "decisions_with_a_citation": len(decisions),
        "decisions_without_a_citation_not_counted": len(without_cite),
        "after_2021": group_totals(late_rows),
        "by_2021": group_totals(early_rows),
        "citing_passages_by_source": dict(sorted(by_source.items())),
        "all_after_2021": late_rows,
        "top_20_by_2021": early_rows[:20],
        "pool_dates": pool_dates(newest_by_case, scotus_ids),
    }


def group_totals(rows):
    return {
        "decisions": len(rows),
        "decisions_cited": sum(r["passages"] > 0 for r in rows),
        "citing_passages": sum(r["passages"] for r in rows),
    }


def pool_dates(newest_by_case, scotus_ids):
    """What the pool says about its dates. The newest year in parentheses is only a lower bound on a date."""
    years = Counter(y for y in newest_by_case.values() if y)
    return {
        "caselaw_case_ids": len(newest_by_case),
        "case_ids_also_in_scotus_corpus": len(set(newest_by_case) & scotus_ids),
        "cases_with_no_year_in_parentheses": sum(not y for y in newest_by_case.values()),
        "newest_parenthesized_year_per_case": {str(y): n for y, n in sorted(years.items()) if y >= 2010},
        "cases_whose_newest_year_is_before_2010": sum(n for y, n in years.items() if y < 2010),
    }


def main():
    # Imported here because caselaw imports this module for `normalize`.
    from open_book_law.prep.caselaw import iter_cases
    from open_book_law.prep.overruled import PAIRS_JSONL, read_jsonl, update_audit
    from open_book_law.us.barexam import iter_pool

    summary, disagreements = score_sample(iter_cases)
    long_summary, long_disagreements = score_sample(iter_cases, MIN_WORDS_LONG)
    verdicts = read_jsonl(REVIEW_JSONL)
    update_audit(
        "extraction",
        summary
        | {
            "disagreements": len(disagreements),
            "post_hoc_opinions_of_at_least_300_words": long_summary
            | {"disagreements": len(long_disagreements)},
            "reviewed": review_sample(disagreements, long_disagreements),
            "review_by": "AI (Claude Opus 5.5) from the printed text, not human-verified",
            "review_verdicts": verdicts,
            "review_counts": dict(Counter(row["verdict"] for row in verdicts)),
        },
    )
    scotus_ids = {case["id"] for case in iter_cases()}
    report = audit_pool(iter_pool("full"), read_jsonl(PAIRS_JSONL), scotus_ids)
    update_audit("pool_audit", report)
    print(json.dumps({k: report[k] for k in ("passages_scanned", "after_2021", "by_2021")}))


if __name__ == "__main__":
    main()
