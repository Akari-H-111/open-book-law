"""The hand-check rows below were typed from the official table CSV. They test the committed pairs file."""

import pytest

from open_book_law.paths import REPO_ROOT
from open_book_law.prep.overruled import (
    find_by_name,
    names_match,
    parse_cell,
    parse_row,
    read_jsonl,
    resolve_pair,
    split_names,
    split_years,
)


def row(order, new, year, old, years):
    return {
        "Order": order,
        "Overruling Decision": new,
        "Year of Overruling Decision": year,
        "Overruled Decision(s)": old,
        "Year(s) of Overruled Decision(s)": years,
    }


@pytest.mark.parametrize(
    "text, names",
    [
        ("Adamson v. California,Twining v. New Jersey,", ["Adamson v. California", "Twining v. New Jersey,"]),
        ("United States v. Arnold, Schwinn & Co.,", ["United States v. Arnold, Schwinn & Co.,"]),
        (
            "Thompson v. Immigration & Naturalization Service,"
            "Harris Truck Lines, Inc. v. Cherry Meat Packers, Inc.,",
            [
                "Thompson v. Immigration & Naturalization Service",
                "Harris Truck Lines, Inc. v. Cherry Meat Packers, Inc.,",
            ],
        ),
        ("In re Moore,Ex parte Wisner,", ["In re Moore", "Ex parte Wisner,"]),
        (
            "Indian Territory Illuminating Oil Co. v. Oklahoma, "
            "Choctaw, Oklahoma & Gulf Railroad v. Harrison,",
            [
                "Indian Territory Illuminating Oil Co. v. Oklahoma",
                "Choctaw, Oklahoma & Gulf Railroad v. Harrison,",
            ],
        ),
    ],
)
def test_split_names(text, names):
    assert split_names(text) == names


def test_parse_cell_forms():
    assert parse_cell("Roe v. Wade,410 U.S. 113 (1973)")[0]["cite"] == "410 U.S. 113"
    assert parse_cell("Slocomb, 39 U.S. (14 Pet.) 60 (1840)")[0]["cite"] == "39 U.S. (14 Pet.) 60"
    assert parse_cell("Noonan v. Lee, 67 U.S. (2 Black) 499 (1863)")[0]["cite"] == "67 U.S. (2 Black) 499"
    assert (
        parse_cell("Orchard v. Hughes, 68 U.S. (1 Wall.) 73, 77 (1864)")[0]["cite"] == "68 U.S. (1 Wall.) 73"
    )
    assert parse_cell("Gouled v. United States,255 U.S. 298 1921 (1921)")[0]["cite"] == "255 U.S. 298"
    docket = parse_cell("Trump v. Slaughter, No. 25-332 (U.S. June 29, 2026)")[0]
    assert (docket["name"], docket["cite"], docket["docket"]) == ("Trump v. Slaughter", None, "25-332")
    assert docket["docket_date"] == "June 29, 2026"
    bare = parse_cell("Federal Election Commission v. Colorado Republican Federal Campaign Committee,")[0]
    assert bare["cite"] is None and not bare["name"].endswith(",")
    part = parse_cell("Teague v. Lane,489 U.S. 288 (1989) (in part)")[0]
    assert part["notes"] == ["in part"]


def test_split_years():
    assert split_years("19921973", 2) == [1992, 1973]
    assert split_years("1972", 2) == [1972, 1972]
    assert split_years("1973197219701969", 4) == [1973, 1972, 1970, 1969]
    assert split_years("19921973", 3) is None
    assert split_years("199", 1) is None


def test_row_that_does_not_line_up_is_reported_and_not_dropped():
    pairs, problem = parse_row(
        row("9", "A v. B, 1 U.S. 1 (1800)", "1800", "C v. D, 1 U.S. 2 (1790)", "17901791")
    )
    assert pairs == []
    assert problem["order"] == "9"


def pairs_by_id():
    return {p["pair_id"]: p for p in read_jsonl(REPO_ROOT / "data" / "overruled_pairs.jsonl")}


# pair_id: new name, new cite, new docket, new year, old name, old cite, old year, in part.
HAND_CHECK = {
    "1-1": (
        "Trump v. Slaughter",
        None,
        "25-332",
        2026,
        "Humphrey's Executor v. United States",
        "295 U.S. 602",
        1935,
        False,
    ),
    "4-2": (
        "Dobbs v. Jackson Women’s Health Organization",
        "597 U.S. 215",
        None,
        2022,
        "Roe v. Wade",
        "410 U.S. 113",
        1973,
        False,
    ),
    "14-2": ("Hurst v. Florida", None, "14-7505", 2016, "Spaziano v. Florida", "468 U.S. 447", 1984, False),
    "15-1": ("Johnson v. United States", None, "13-7120", 2015, "Sykes v. United States", None, 2011, False),
    "23-1": (
        "Central Virginia Community College v. Katz",
        "546 U.S. 356",
        None,
        2006,
        "Hoffman v. Connecticut Department of Income Maintenance",
        None,
        1989,
        False,
    ),
    "30-1": ("United States v. Cotton", "535 U.S. 625", None, 2002, "Ex parte Bain", None, 1887, False),
    "34-1": (
        "Minnesota v. Mille Lacs Band of Chippewa Indians",
        "526 U.S. 172",
        None,
        1999,
        "Ward v. Race Horse",
        "163 U.S. 504",
        1896,
        True,
    ),
    "49-1": (
        "Quill Corp. v. North Dakota",
        "504 U.S. 298",
        None,
        1992,
        "National Bellas Hess, Inc. v. Department of Revenue of Illinois",
        "386 U.S. 753",
        1967,
        True,
    ),
    "66-1": ("Batson v. Kentucky", "476 U.S. 79", None, 1986, "Swain v. Alabama", "380 U.S. 202", 1965, True),
    "87-1": (
        "Continental T.V., Inc. v. GTE Sylvania",
        "433 U.S. 36",
        None,
        1977,
        "United States v. Arnold, Schwinn & Co.",
        None,
        1967,
        False,
    ),
    "101-3": ("Edelman v. Jordan", "415 U.S. 651", None, 1974, "Wyman v. Bowens", None, 1970, False),
    "132-1": (
        "Warden, Maryland Penitentiary v. Hayden",
        "387 U.S. 294",
        None,
        1967,
        "Gouled v. United States",
        "255 U.S. 298",
        1921,
        False,
    ),
    "141-2": ("Malloy v. Hogan", "378 U.S. 1", None, 1964, "Twining v. New Jersey", None, 1908, False),
    "158-3": (
        "Standard Oil Co. v. Peck",
        "342 U.S. 382",
        None,
        1952,
        "St. Louis v. The Ferry Co.",
        "78 U.S. (11 Wall.) 423",
        1870,
        False,
    ),
    "163-5": (
        "Oklahoma Tax Commission v. Texas Co.",
        "336 U.S. 342",
        None,
        1949,
        "Choctaw, Oklahoma & Gulf Railroad v. Harrison",
        None,
        1914,
        False,
    ),
    "188-2": (
        "Helvering v. Hallock",
        "309 U.S. 106",
        None,
        1940,
        "Helvering v. St. Louis Union Trust Co.",
        None,
        1935,
        False,
    ),
    "212-1": (
        "Minnesota Rate Cases",
        "230 U.S. 352",
        None,
        1913,
        "Peik v. Chicago & Northwestern Railway",
        None,
        1877,
        False,
    ),
    "226-3": (
        "Hornbuckle v. Toombs",
        "85 U.S. (18 Wall.) 648",
        None,
        1874,
        "Noonan v. Lee",
        "67 U.S. (2 Black) 499",
        1863,
        False,
    ),
    "228-1": (
        "Knox v. Lee",
        "79 U.S. (12 Wall.) 457",
        None,
        1871,
        "Hepburn v. Griswold",
        "75 U.S. (8 Wall.) 603",
        1870,
        False,
    ),
    "237-1": (
        "Gordon v. Ogden",
        "28 U.S. (3 Pet.) 33",
        None,
        1830,
        "Wilson v. Daniel",
        "3 U.S. (3 Dall.) 401",
        1798,
        False,
    ),
}


@pytest.mark.parametrize("pair_id", HAND_CHECK)
def test_hand_checked_rows(pair_id):
    p = pairs_by_id()[pair_id]
    fields = ("new_name", "new_cite", "new_docket", "new_year", "old_name", "old_cite", "old_year", "in_part")
    assert tuple(p[f] for f in fields) == HAND_CHECK[pair_id]


def test_every_row_of_the_table_gave_at_least_one_pair():
    assert {p["order"] for p in pairs_by_id().values()} == set(range(1, 238))


def index_of(*cases):
    by_year = {}
    for case_id, name, year, words in cases:
        by_year.setdefault(year, []).append({"id": case_id, "name": name, "words": words})
    return {"by_year": by_year}


def test_names_match_abbreviations_and_a_bare_state():
    assert names_match("Doyle v. Cont’l Ins. Co.", "Doyle v. Continental Insurance")
    assert names_match("Coppage v. Kansas", "Coppage v. State")
    assert not names_match("Coppage v. Kansas", "Coppage v. Smith")


def test_name_search_narrows_step_by_step_and_never_guesses():
    memo_and_opinion = index_of(
        ("memo", "Sykes v. United States", 2011, 26), ("full", "Sykes v. United States", 2011, 5000)
    )
    assert find_by_name("Sykes v. United States", 2011, memo_and_opinion, frozenset()) == (
        "full",
        "name_year+full_opinion",
    )
    two_opinions = index_of(("a", "Leeds v. Victor", 1909, 5000), ("b", "Leeds v. Victor", 1909, 3000))
    assert find_by_name("Leeds v. Victor", 1909, two_opinions, frozenset()) == (None, "name_year_ambiguous")
    assert find_by_name("Leeds v. Victor", 1909, two_opinions, {"b"})[0] == "b"
    term_date = index_of(("pace", "Pace v. Alabama", 1882, 536))
    assert find_by_name("Pace v. Alabama", 1883, term_date, frozenset()) == ("pace", "name_near_year")
    assert find_by_name("Pace v. Alabama", 1890, term_date, frozenset()) == (None, "name_not_found")


def test_bare_state_is_allowed_only_on_the_second_side():
    assert not names_match("Obergefell v. Hodges", "State v. State")
    assert not names_match("Kansas v. Coppage", "State v. Coppage")


def test_memorandum_with_the_same_name_does_not_beat_the_opinion():
    cases = index_of(
        ("memo", "United States v. Arnold, Schwinn & Co.", 1967, 38),
        ("full", "United States v. Arnold, Schwinn & Co. et al.", 1967, 9000),
    )
    assert find_by_name("United States v. Arnold, Schwinn & Co.", 1967, cases, frozenset())[0] == "full"


def test_docket_decision_is_not_searched_by_name():
    pair = {
        "new_name": "Obergefell v. Hodges",
        "new_cite": None,
        "new_docket": "14-556",
        "new_year": 2015,
        "old_name": "Baker v. Nelson",
        "old_cite": None,
        "old_year": 1972,
    }
    state = {
        "id": "wrong",
        "name": "Obergefell v. Hodges",
        "words": 9000,
        "cite": "1 U.S. 1",
        "cites_ids": set(),
    }
    index = {"cases": {"wrong": state}, "by_year": {2015: [state]}, "by_cite": {}, "by_docket": {}}
    resolved = resolve_pair(pair, index)
    assert (resolved["new_id"], resolved["new_found_by"]) == (None, "docket_not_fetched")
