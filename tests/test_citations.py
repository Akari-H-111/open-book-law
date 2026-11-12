from open_book_law.prep.citations import canonical, extract, normalize


def test_modern_forms():
    assert normalize("410 U.S. 113") == "410 U.S. 113"
    assert normalize("410 U. S. 113") == "410 U.S. 113"
    assert normalize("410 U.\xa0S. 113") == "410 U.S. 113"
    assert extract("See Roe v. Wade, 410 U. S. 113, 150 (1973).") == ["410 U.S. 113"]


def test_parallel_and_nominative_forms_give_one_citation():
    assert normalize("39 U.S. (14 Pet.) 60") == "39 U.S. 60"
    assert normalize("14 Pet. 60") == "39 U.S. 60"
    assert normalize("9 U.S. (5 Cr.) 61") == "9 U.S. 61"
    assert normalize("5 Cranch 61") == "9 U.S. 61"
    assert normalize("9 Wheat. 738") == "22 U.S. 738"
    assert normalize("17 How. 477") == "58 U.S. 477"
    assert normalize("67 U.S. (2 Black) 499") == "67 U.S. 499"
    assert normalize("13 Wall. 29") == "80 U.S. 29"
    assert normalize("3 Dall. 401") == "3 U.S. 401"
    assert extract("14 Pet. 60; 39 U. S. 60") == ["39 U.S. 60"]


def test_things_that_are_not_full_citations():
    assert extract("42 U.S.C. 1983") == []
    assert extract("42 U. S. C. § 1983") == []
    assert extract("410 U. S., at 150") == []
    assert extract("597 U. S. ___") == []
    assert extract("7 How. (Miss.) 12") == []
    assert extract("5 How. Pr. 12") == []
    assert extract("3 Wall. Jr. 20") == []
    assert extract("1 F. 2d 100") == []


def test_volumes_that_the_reporter_never_had():
    assert extract("99 How. 10") == []
    assert extract("17 Pet. 10") == []
    assert extract("3 Black 10") == []


def test_order_of_first_appearance():
    assert extract("2 U.S. 3, then 1 U.S. 5, then 2 U.S. 3") == ["2 U.S. 3", "1 U.S. 5"]
    assert canonical("007", "010") == "7 U.S. 10"
