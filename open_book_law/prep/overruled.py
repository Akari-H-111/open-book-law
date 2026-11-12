"""Parse the Constitution Annotated table of overruled decisions into one row per decision pair.

Some cells lost their citations when the table was exported, so names can run together with only a comma:
`Adamson v. California,Twining v. New Jersey,`. The years column has either one year per decision, or a
single year shared by all of them. A cell that fits neither pattern goes to the `unparsed` list.
"""

import csv
import json
import re

from open_book_law.paths import DATA_ROOT, REPO_ROOT
from open_book_law.prep.citations import normalize

TABLE_DIR = DATA_ROOT / "conan_overruled"
PAIRS_JSONL = REPO_ROOT / "data" / "overruled_pairs.jsonl"
AUDIT_JSON = REPO_ROOT / "results" / "data_audit" / "goodlaw_audit.json"

REPORTER_CITE = re.compile(
    r",?\s*(?P<cite>\d+ U\.S\.(?: \(\d+ [A-Za-z]+\.?\))? \d+)(?:, \d+)?(?: \d{4})?\s+\((?P<year>\d{4})\)"
)
DOCKET_CITE = re.compile(
    r",?\s*No\. (?P<docket>[\d-]+) \(U\.S\. (?P<date>[A-Z][a-z]+\.? \d+, (?P<year>\d{4}))\)"
)
NOTE = re.compile(r"\s*\(([^()]*)\)\s*$")
CORPORATE_TAIL = re.compile(r"\s*(Inc|Co|Corp|Ltd)\b")
SINGLE_PARTY = re.compile(r"^(In re|Ex parte) ")
NAME_STOPWORDS = frozenset("v of the in re ex parte rel inc co corp company ltd et al and s".split())
GENERIC_GOVERNMENT = frozenset(("state", "commonwealth"))
FULL_OPINION_WORDS = 300


def split_names(text):
    """Split names that only a comma separates. A comma ends a name if another name follows it."""
    names, current = [], ""
    pieces = text.split(",")
    for i, piece in enumerate(pieces):
        current = f"{current},{piece}" if current else piece
        rest = ",".join(pieces[i + 1 :]).strip()
        complete = " v. " in current or SINGLE_PARTY.match(current.strip())
        starts_name = " v. " in rest or SINGLE_PARTY.match(rest)
        if complete and starts_name and not CORPORATE_TAIL.match(rest):
            names.append(current.strip())
            current = ""
    if current.strip():
        names.append(current.strip())
    return names


def parse_decision_chunk(chunk):
    """Parse text between semicolons into decisions. Only the last decision can have a citation."""
    chunk = chunk.strip()
    notes = []
    while note := NOTE.search(chunk):
        if re.fullmatch(r"\d{4}", note.group(1)) or note.group(1).startswith("U.S. "):
            break
        notes.insert(0, note.group(1))
        chunk = chunk[: note.start()]
    found = REPORTER_CITE.search(chunk) or DOCKET_CITE.search(chunk)
    fields = found.groupdict() if found else {}
    name_text = chunk[: found.start()] if found else chunk
    names = [n.rstrip(" ,") for n in split_names(name_text)]
    decisions = [{"name": n, "cite": None, "docket": None, "notes": []} for n in names]
    if decisions:
        decisions[-1].update(cite=fields.get("cite"), docket=fields.get("docket"), notes=notes)
        decisions[-1]["docket_date"] = fields.get("date")
    return decisions


def parse_cell(cell):
    return [d for chunk in cell.split(";") for d in parse_decision_chunk(chunk)]


def split_years(cell, count):
    """Return one year per decision, or None if the column does not line up with the decisions."""
    years = re.findall(r"\d{4}", cell)
    if len(years) * 4 != len(cell.strip()):
        return None
    if len(years) == count:
        return [int(y) for y in years]
    return [int(years[0])] * count if len(years) == 1 else None


def parse_row(row):
    """Return (pairs, problem). A row with a problem gives no pairs, and the caller lists it."""
    order = row["Order"].strip()
    new = parse_cell(row["Overruling Decision"])
    old = parse_cell(row["Overruled Decision(s)"])
    years = split_years(row["Year(s) of Overruled Decision(s)"], len(old))
    if len(new) != 1 or not old or years is None:
        return [], {"order": order, "new_cells": len(new), "old_decisions": len(old), "row": dict(row)}
    pairs = []
    for i, (decision, year) in enumerate(zip(old, years, strict=True)):
        pairs.append(
            {
                "pair_id": f"{order}-{i + 1}",
                "order": int(order),
                "new_name": new[0]["name"],
                "new_cite": new[0]["cite"],
                "new_docket": new[0]["docket"],
                "new_docket_date": new[0].get("docket_date"),
                "new_year": int(row["Year of Overruling Decision"]),
                "new_notes": new[0]["notes"],
                "old_name": decision["name"],
                "old_cite": decision["cite"],
                "old_year": year,
                "old_notes": decision["notes"],
                "in_part": "in part" in decision["notes"] or "in part" in new[0]["notes"],
            }
        )
    return pairs, None


def parse_table(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    pairs, unparsed = [], []
    for row in rows:
        row_pairs, problem = parse_row(row)
        pairs += row_pairs
        if problem:
            unparsed.append(problem)
    return rows, pairs, unparsed


def name_words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower().replace("’", "'")) if w not in NAME_STOPWORDS}


def words_overlap(table_words, cap_words):
    """Share a word, or a word and its abbreviation (the table has "Cont'l Ins." for Continental)."""
    return any(
        t == c or (min(len(t), len(c)) >= 3 and (t.startswith(c) or c.startswith(t)))
        for t in table_words
        for c in cap_words
    )


def names_match(table_name, cap_name):
    """Both sides of "A v. B" must share a word. CAP may say only "State" on the second side."""
    table_sides, cap_sides = table_name.split(" v. "), cap_name.split(" v. ")
    if len(table_sides) == 2 and len(cap_sides) == 2:
        first = words_overlap(name_words(table_sides[0]), name_words(cap_sides[0]))
        second = name_words(cap_sides[1]) <= GENERIC_GOVERNMENT or words_overlap(
            name_words(table_sides[1]), name_words(cap_sides[1])
        )
        return first and second
    return words_overlap(name_words(table_name), name_words(cap_name))


def narrow_by_name(name, candidates, cited_by_new):
    """Apply each test in turn while more than one decision remains. A test that rejects all is skipped.

    One-line orders often carry the same name as the opinion, so the exact name comes last.
    """
    tests = (
        ("cited_by_new", lambda c: c["id"] in cited_by_new),
        ("full_opinion", lambda c: c["words"] >= FULL_OPINION_WORDS),
        ("exact", lambda c: name_words(c["name"]) == name_words(name)),
    )
    how = []
    for label, test in tests:
        narrowed = [c for c in candidates if test(c)]
        if len(candidates) > 1 and narrowed:
            candidates = narrowed
            how.append(label)
    return candidates, how


def find_by_name(name, year, index, cited_by_new):
    """Name and year must lead to one decision. CAP often dates old cases by term, a year from the table's."""
    for years, tag in (((year,), "name_year"), ((year - 1, year + 1), "name_near_year")):
        named = [c for y in years for c in index["by_year"].get(y, []) if names_match(name, c["name"])]
        if named:
            narrowed, how = narrow_by_name(name, named, cited_by_new)
            if len(narrowed) == 1:
                return narrowed[0]["id"], "+".join([tag, *how])
            return None, f"{tag}_ambiguous"
    return None, "name_not_found"


def resolve_side(name, cite, year, index, cited_by_new=frozenset()):
    """Find one decision in the case index. Return (case id or None, how it was found). Never pick at random.

    A table citation decides, and the name only chooses between decisions on the same first page. If CAP has
    nothing at that citation, or if the table gives no citation, the name and year must decide.
    """
    if not cite:
        return find_by_name(name, year, index, cited_by_new)
    found = index["by_cite"].get(normalize(cite), [])
    named = [c for c in found if names_match(name, c["name"])]
    if len(named) == 1:
        return named[0]["id"], "cite"
    if len(found) == 1:
        return found[0]["id"], "cite_other_name"
    if found:
        return None, "cite_ambiguous"
    case_id, how = find_by_name(name, year, index, cited_by_new)
    return case_id, f"cite_not_in_cap+{how}"


def resolve_pair(pair, index):
    """Add the case ids of both decisions to a pair. A docket number never falls back to a name search."""
    if pair["new_docket"]:
        new_id = index["by_docket"].get(pair["new_docket"])
        new_by = "docket" if new_id else "docket_not_fetched"
    else:
        new_id, new_by = resolve_side(pair["new_name"], pair["new_cite"], pair["new_year"], index)
    cited = index["cases"][new_id]["cites_ids"] if new_id else frozenset()
    old_id, old_by = resolve_side(pair["old_name"], pair["old_cite"], pair["old_year"], index, cited)
    new_cite = index["cases"][new_id]["cite"] if new_id else normalize(pair["new_cite"])
    old_cite = index["cases"][old_id]["cite"] if old_id else normalize(pair["old_cite"])
    return pair | {
        "new_id": new_id,
        "new_found_by": new_by,
        "new_canonical": new_cite,
        "old_id": old_id,
        "old_found_by": old_by,
        "old_canonical": old_cite,
    }


def table_path():
    """The directory holds exactly one CSV."""
    return next(TABLE_DIR.glob("*.csv"))


def update_audit(section, values):
    """Replace one section of the audit file, keeping the sections that other scripts wrote."""
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8")) if AUDIT_JSON.exists() else {}
    audit[section] = values
    text = json.dumps(audit, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    AUDIT_JSON.write_text(text, encoding="utf-8")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    """Audit the parsed table. `caselaw link` writes the pairs file, because only it can add the case ids."""
    rows, pairs, unparsed = parse_table(table_path())
    update_audit(
        "table",
        {
            "rows": len(rows),
            "rows_parsed": len(rows) - len(unparsed),
            "pairs": len(pairs),
            # The preregistration says 271. Check whether that figure counts only semicolons as separators.
            "rows_plus_semicolons": len(rows) + sum(r["Overruled Decision(s)"].count(";") for r in rows),
            "distinct_old_decisions": len({p["old_cite"] or p["old_name"].lower() for p in pairs}),
            "pairs_in_part": sum(p["in_part"] for p in pairs),
            "old_decisions_without_cite_in_table": sum(p["old_cite"] is None for p in pairs),
            "new_decisions_with_docket_only": len({p["order"] for p in pairs if p["new_cite"] is None}),
            "unparsed_rows": unparsed,
        },
    )
    print(f"rows {len(rows)}, pairs {len(pairs)}, unparsed rows {len(unparsed)}")


if __name__ == "__main__":
    main()
