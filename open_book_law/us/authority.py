"""A dated store of authority: which decision cites which, and which had been overruled on a given date.

The cases and citations come from Caselaw Access Project metadata, and the overrulings come from the official
table. No AI is involved. Limits: decisions that CAP lacks have no outgoing citations here, and the table
lists only overrulings by the Supreme Court itself.
"""

import sqlite3

from open_book_law.paths import DERIVED_DIR
from open_book_law.prep.citations import normalize

AUTHORITY_DB = DERIVED_DIR / "authority.sqlite"
SCHEMA = """
CREATE TABLE cases(id TEXT PRIMARY KEY, cite TEXT, name TEXT, date TEXT);
CREATE TABLE cites(src TEXT, dst TEXT, PRIMARY KEY(src, dst)) WITHOUT ROWID;
CREATE TABLE overruled(old TEXT, new TEXT, year INTEGER, in_part INTEGER, PRIMARY KEY(old, new));
CREATE INDEX cases_cite ON cases(cite);
CREATE INDEX cites_dst ON cites(dst);
"""


def build(conn, cases, pairs):
    """Fill an empty database. `cases` is a list of case dicts, and `pairs` holds resolved table rows."""
    conn.executescript(SCHEMA)
    known = {case["id"] for case in cases}
    for case in cases:
        row = (case["id"], case["cite"], case["name"], case["date"])
        conn.execute("INSERT INTO cases VALUES (?,?,?,?)", row)
        for cited in case.get("cites_to", []):
            for dst in cited["case_ids"]:
                if dst in known and dst != case["id"]:
                    conn.execute("INSERT OR IGNORE INTO cites VALUES (?,?)", (case["id"], dst))
    for pair in pairs:
        old = add_table_case(conn, known, pair, "old")
        new = add_table_case(conn, known, pair, "new")
        row = (old, new, pair["new_year"], int(pair["in_part"]))
        conn.execute("INSERT OR IGNORE INTO overruled VALUES (?,?,?,?)", row)
    conn.commit()


def add_table_case(conn, known, pair, side):
    """Return the case id of one side, adding a row with no date for a decision that has no text."""
    if pair[f"{side}_id"]:
        return pair[f"{side}_id"]
    name, cite = pair[f"{side}_name"], pair[f"{side}_cite"]
    case_id = f"table:{name}:{pair[f'{side}_year']}"
    if case_id not in known:
        conn.execute("INSERT INTO cases VALUES (?,?,?,?)", (case_id, normalize(cite), name, None))
        known.add(case_id)
    return case_id


def effective_date(decision_date, year):
    """The day from which an overruling counts. With only a year, count from the last day of that year."""
    if decision_date and len(decision_date) == 10:
        return decision_date
    return f"{year}-12-31"


def overrulings(conn, ids):
    """Every overruling of these case ids, oldest first."""
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT n.name, n.cite, n.date, o.year, o.in_part FROM overruled o JOIN cases n ON n.id = o.new "
        f"WHERE o.old IN ({marks})",
        ids,
    ).fetchall()
    events = [
        {
            "name": name,
            "cite": cite,
            "year": year,
            "in_part": bool(part),
            "effective": effective_date(date, year),
        }
        for name, cite, date, year, part in rows
    ]
    return sorted(events, key=lambda e: e["effective"])


def find_case_ids(conn, reference):
    """Case ids for a citation, a case id or a docket number.

    Decisions that share a first page come back together. A decision that the table names by docket alone
    came from Cornell, so its id is "cornell:" and the docket. It may have no citation in this store.
    """
    cite = normalize(reference)
    if cite:
        rows = conn.execute("SELECT id FROM cases WHERE cite = ?", (cite,))
    else:
        docket = reference.removeprefix("No. ")
        rows = conn.execute("SELECT id FROM cases WHERE id IN (?, ?)", (reference, f"cornell:{docket}"))
    return [row[0] for row in rows]


def status(conn, reference, as_of_date):
    """Status on a date: good, overruled, not_decided or unknown. `as_of_date` is a YYYY-MM-DD string."""
    ids = find_case_ids(conn, reference)
    if not ids:
        return {"status": "unknown", "names": [], "overruled_by": []}
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT name, date FROM cases WHERE id IN ({marks})", ids).fetchall()
    names = [name for name, _ in rows]
    dates = [date for _, date in rows if date]
    if dates and as_of_date < min(dates):
        return {"status": "not_decided", "names": names, "overruled_by": []}
    events = [e for e in overrulings(conn, ids) if e["effective"] <= as_of_date]
    return {"status": "overruled" if events else "good", "names": names, "overruled_by": events}


def build_file(cases, pairs):
    """Build through a temporary name and return row counts. No journal files are written on this drive."""
    part = AUTHORITY_DB.with_name(AUTHORITY_DB.name + ".part")
    part.unlink(missing_ok=True)
    conn = sqlite3.connect(part)
    conn.execute("PRAGMA journal_mode=OFF")
    build(conn, cases, pairs)
    tables = ("cases", "cites", "overruled")
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()
    part.rename(AUTHORITY_DB)
    return counts
