"""Build site/data.js, the data of the static results site, from committed files only.

Run from the repository root:  python3 -I tools/build_site_data.py [--no-goodlaw-text]

It reads run files, summaries and the two review samples, and needs no downloaded data and no model.
The output does not depend on time or machine, so CI can rebuild it and require `git diff` to be empty.
No exam question text and no passage text goes into the output. The good-law sample is the project's
own AI-written questions with short quotations, already in docs/review/. --no-goodlaw-text leaves out
its question text, options and quotations, and keeps only IDs and model answers.
Uses only the standard library.
"""

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "results" / "runs"
OUT = REPO / "site" / "data.js"

# Conditions of the good-law test, in the order of section 8.3 of the preregistration.
GOODLAW_CONDITIONS = ["closed", "old-only", "new-only", "both", "both-dated", "retrieved", "citator", "note"]
H1_DOCTRINE, H1_CLOSED, H3_GOLD = "5feb10aa4a385948", "37b2a24e08bf9b8c", "15eb1f50138858a0"
H9_RUN, H10_RETRIEVED, H10_AGENT = "f90498bed7d31fdb", "fe9cca9d1cb8b3b5", "6146f77693af14f4"


def r2(x):
    return None if x is None else round(x, 2)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run(rid):
    [path] = RUNS.glob(f"*/{rid}.json")
    return load_json(path)


def by_qid(record):
    return {row["qid"]: row for row in record["per_query"]}


def tests():
    summary = load_json(REPO / "results" / "summary" / "us_hypotheses.json")
    out = []
    for tid in sorted(summary["tests"], key=lambda name: (int(re.sub(r"\D", "", name)), name)):
        t = summary["tests"][tid]
        out.append({
            "id": tid,
            "difference": r2(t["difference"]),
            "low": r2(t["low"]),
            "high": r2(t["high"]),
            "p_holm": t["p_holm"],
            "threshold": t["threshold"],
            "questions": t["questions"],
            "verdict": t["verdict"],
            "only_first_right": t.get("a_only"),
            "only_second_right": t.get("b_only"),
            "runs": t["runs"],
        })
    return out


def reproduction():
    summary = load_json(REPO / "results" / "summary" / "us_repro.json")
    rows = [{"id": t["id"], "dataset": t["dataset"], "method": t["retriever"], "verdict": t["verdict"],
             "questions": t.get("questions")} for t in summary["targets"]]
    rows += [{"id": t["id"], "dataset": t["dataset"], "method": "llama8 reader", "verdict": t["verdict"],
              "questions": t.get("questions")} for t in summary["reader_targets"]]
    return rows


def goodlaw_runs():
    """Outcome rates per condition, the per-question answers, and the questions that left the test."""
    rates, answers, left_out = {}, {}, set()
    records = [load_json(path) for path in (RUNS / "us_goodlaw").glob("*.json")]
    # As in the summary scripts, the earliest run of a setting decides. A rerun cannot replace it.
    for record in sorted(records, key=lambda r: (r["utc_time"], r["run_id"])):
        c = record["config"]
        key = f"{c['reader']}:{c['condition']}"
        if key in rates:
            continue
        r = record["metrics"]["all"]["rates"]
        rates[key] = {"run": record["run_id"], "questions": record["metrics"]["all"]["questions"],
                      "current": r2(r["current"]), "superseded": r2(r["superseded"]),
                      "other": r2(r["other_wrong"])}
        answers[key] = {q: row["predicted"] for q, row in by_qid(record).items()}
        left_out |= set(record["metrics"]["all"]["left_out"])
    agent = run(H10_AGENT)
    m = agent["metrics"]["all"]
    rates["qwen3:agent"] = {"run": agent["run_id"], "questions": m["questions"], "current": r2(m["accuracy"]),
                            "superseded": r2(m["superseded_rate"]),
                            "other": r2(100 - m["accuracy"] - m["superseded_rate"]),
                            "tool_calls_per_question": r2(m["tool_calls_per_question"])}
    answers["qwen3:agent"] = {q: row["predicted"] for q, row in by_qid(agent).items()}
    for by_q in answers.values():
        if any(letter not in "ABCD" for letter in by_q.values()):
            raise ValueError("an answer is not one of the letters A to D")
    return rates, answers, sorted(left_out)


def h9_ranks():
    record = run(H9_RUN)
    rows = by_qid(record)
    types = {}
    for row in rows.values():
        for kind, n in row["types_top10"].items():
            types[kind] = types.get(kind, 0) + n
    return rows, {"run": H9_RUN, "questions": len(rows),
                  "old_outranks_new": sum(int(r["old_outranks_new"]) for r in rows.values()),
                  "opinion_types_in_top10": dict(sorted(types.items()))}


def parse_goodlaw_sample():
    text = (REPO / "docs" / "review" / "goodlaw_sample.md").read_text(encoding="utf-8")
    items = []
    for block in text.split("\n## Pair ")[1:]:
        lines = block.split("\n")
        pair_id, title = lines[0].split(": ", 1)
        overrules = re.match(r"Overrules (.*)\. Partial: (True|False)\.", lines[1])
        body = "\n".join(lines[2:])
        options = dict(re.findall(r"^- ([ABCD])\. (.*)$", body, re.M))
        rule = re.search(r"Current rule: ([ABCD])\. Superseded rule: ([ABCD])\.", body)
        quotes = re.findall(r'^Quoted from (.*?): "(.*)"$', body, re.M)
        question = next(line for line in lines[2:] if line.strip() and not line.startswith("- "))
        items.append({"id": pair_id, "new": title, "old": overrules.group(1),
                      "partial": overrules.group(2) == "True", "question": question, "options": options,
                      "current": rule.group(1), "superseded": rule.group(2),
                      "quotes": [{"from": name, "text": quote} for name, quote in quotes]})
    return items


def goodlaw_sample(answers, ranks, left_out, with_text):
    out = []
    for item in parse_goodlaw_sample():
        qid = item["id"]
        row = {k: item[k] for k in ("id", "new", "old", "partial", "current", "superseded")}
        if with_text:
            row |= {k: item[k] for k in ("question", "options", "quotes")}
        row["answers"] = {key: by_q.get(qid) for key, by_q in sorted(answers.items())}
        rank = ranks.get(qid)
        row["rank_old"] = rank and rank["rank_old"]
        row["rank_new"] = rank and rank["rank_new"]
        row["left_out"] = qid in left_out
        out.append(row)
    return out


def error_sample():
    text = (REPO / "docs" / "review" / "error_sample.md").read_text(encoding="utf-8")
    doctrine, closed, gold = by_qid(run(H1_DOCTRINE)), by_qid(run(H1_CLOSED)), by_qid(run(H3_GOLD))
    out = []
    for line in text.splitlines():
        if not line.startswith("| mbe_"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        qid, passages, label, reason, quote, author_label, author_note = cells
        d = doctrine[qid]
        out.append({
            "id": qid, "passages": passages, "ai_label": label, "ai_reason": reason, "quote": quote,
            "author_label": author_label, "answer": d["gold"], "predicted": d["predicted"],
            "probabilities": {k: r2(100 * v) for k, v in sorted(d["probabilities"].items())},
            "closed_book": closed[qid]["predicted"], "gold_passage": gold[qid]["predicted"],
        })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-goodlaw-text", action="store_true")
    args = parser.parse_args()
    rates, answers, left_out = goodlaw_runs()
    ranks, h9 = h9_ranks()
    hyp = load_json(REPO / "results" / "summary" / "us_hypotheses.json")
    audit = load_json(REPO / "results" / "data_audit" / "goodlaw_audit.json")
    data = {
        "tests": tests(),
        "reproduction": reproduction(),
        "goodlaw": {
            "conditions": GOODLAW_CONDITIONS,
            "rates": rates,
            "date_test_both_forms_correct": r2(hyp["exploratory"]["date_test_both_forms_correct"]),
            "h9": h9,
            "left_out": left_out,
            "written": audit["generator"]["step_b_kept"],
            "sample": goodlaw_sample(answers, ranks, left_out, not args.no_goodlaw_text),
            "sample_has_text": not args.no_goodlaw_text,
        },
        "errors": error_sample(),
        "sources": {
            "tests": "results/summary/us_hypotheses.json",
            "reproduction": "results/summary/us_repro.json",
            "goodlaw": "results/runs/us_goodlaw/, results/runs/us_agent/" + H10_AGENT + ".json",
            "h9": f"results/runs/us_downstream/{H9_RUN}.json",
            "goodlaw_sample": "docs/review/goodlaw_sample.md",
            "errors": f"docs/review/error_sample.md, runs {H1_DOCTRINE}, {H1_CLOSED}, {H3_GOLD}",
        },
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1)
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("// Written by tools/build_site_data.py. Do not edit by hand.\n")
        f.write(f"window.OPEN_BOOK_DATA = {text};\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
