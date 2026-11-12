import sqlite3

import pytest

from open_book_law.us.authority import build, status


def case(case_id, cite, name, date, cites=()):
    return {
        "id": case_id,
        "cite": cite,
        "name": name,
        "date": date,
        "cites_to": [{"case_ids": [c]} for c in cites],
    }


def pair(old_id, old_name, old_cite, old_year, new_id, new_name, new_cite, new_year, in_part=False):
    return {
        "old_id": old_id,
        "old_name": old_name,
        "old_cite": old_cite,
        "old_year": old_year,
        "new_id": new_id,
        "new_name": new_name,
        "new_cite": new_cite,
        "new_year": new_year,
        "in_part": in_part,
    }


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    cases = [
        case("roe", "410 U.S. 113", "Roe v. Wade", "1973-01-22"),
        case("casey", "505 U.S. 833", "Casey", "1992-06-29", cites=["roe"]),
        case("dobbs", "597 U.S. 215", "Dobbs", "2022-06-24", cites=["roe", "casey"]),
        case("later", "600 U.S. 1", "Later", "2023-01-10", cites=["roe"]),
        case("race", "163 U.S. 504", "Ward v. Race Horse", "1896-05-25"),
        case("lacs", "526 U.S. 172", "Mille Lacs", "1999-03-24"),
        case("herrera", None, "Herrera v. Wyoming", "2019-05-20", cites=["race"]),
        case("good", "1 U.S. 1", "Still Good", "1790-01-01", cites=["not-in-the-corpus"]),
        case("noted", "380 U.S. 202", "Yearly", "1965-03-08"),
        case("cornell:14-556", None, "Obergefell v. Hodges", "2015-06-26"),
    ]
    pairs = [
        pair("roe", "Roe v. Wade", "410 U.S. 113", 1973, "dobbs", "Dobbs", "597 U.S. 215", 2022),
        pair("casey", "Casey", "505 U.S. 833", 1992, "dobbs", "Dobbs", "597 U.S. 215", 2022),
        pair("race", "Ward", "163 U.S. 504", 1896, "lacs", "Mille Lacs", "526 U.S. 172", 1999, in_part=True),
        pair("race", "Ward", "163 U.S. 504", 1896, "herrera", "Herrera", None, 2019),
        pair("noted", "Yearly", "380 U.S. 202", 1965, None, "No Text v. Table", None, 1986),
    ]
    build(connection, cases, pairs)
    return connection


def test_roe_before_and_after_dobbs(conn):
    assert status(conn, "410 U.S. 113", "2022-06-23")["status"] == "good"
    assert status(conn, "410 U.S. 113", "2022-06-24")["status"] == "overruled"
    after = status(conn, "410 U. S. 113", "2026-11-03")
    assert after["names"] == ["Roe v. Wade"]
    assert [(e["name"], e["year"], e["in_part"]) for e in after["overruled_by"]] == [("Dobbs", 2022, False)]


def test_dobbs_itself_is_good_after_it_is_decided(conn):
    assert status(conn, "597 U.S. 215", "2021-01-01")["status"] == "not_decided"
    assert status(conn, "597 U.S. 215", "2026-11-03")["status"] == "good"


def test_case_overruled_twice_shows_only_the_overrulings_so_far(conn):
    assert status(conn, "163 U.S. 504", "1998-01-01")["status"] == "good"
    middle = status(conn, "163 U.S. 504", "2000-01-01")
    assert [(e["name"], e["in_part"]) for e in middle["overruled_by"]] == [("Mille Lacs", True)]
    late = status(conn, "163 U.S. 504", "2026-11-03")
    assert [e["name"] for e in late["overruled_by"]] == ["Mille Lacs", "Herrera v. Wyoming"]


def test_unknown_case(conn):
    assert status(conn, "999 U.S. 999", "2026-11-03") == {
        "status": "unknown",
        "names": [],
        "overruled_by": [],
    }
    assert status(conn, "not a citation", "2026-11-03")["status"] == "unknown"


def test_year_only_overruling_counts_from_the_end_of_that_year(conn):
    assert status(conn, "380 U.S. 202", "1986-06-01")["status"] == "good"
    assert status(conn, "380 U.S. 202", "1987-01-01")["status"] == "overruled"


def test_early_nominative_form_finds_the_same_case(conn):
    assert status(conn, "1 Dall. 1", "2026-11-03")["names"] == ["Still Good"]


def test_status_accepts_a_case_id_and_a_docket(conn):
    assert status(conn, "roe", "2026-11-03")["status"] == "overruled"
    assert status(conn, "roe", "2022-06-23")["status"] == "good"
    for reference in ("14-556", "No. 14-556", "cornell:14-556"):
        found = status(conn, reference, "2026-11-03")
        assert (found["status"], found["names"]) == ("good", ["Obergefell v. Hodges"])
    assert status(conn, "14-556", "2015-06-25")["status"] == "not_decided"
    assert status(conn, "99-999", "2026-11-03")["status"] == "unknown"


def test_citations_outside_the_corpus_are_dropped(conn):
    assert conn.execute("SELECT COUNT(*) FROM cites WHERE dst = 'not-in-the-corpus'").fetchone()[0] == 0
