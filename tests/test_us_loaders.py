"""Loaders and the audit's duplicate search, on small synthetic files."""

import csv
import json
import zipfile

import pytest

from open_book_law.prep import audit
from open_book_law.us import barexam, housing

QA_FIELDS = [
    "idx",
    "dataset",
    "example_id",
    "prompt_id",
    "source",
    "subject",
    "question_number",
    "prompt",
    "question",
    "choice_a",
    "choice_b",
    "choice_c",
    "choice_d",
    "answer",
    "gold_passage",
    "gold_idx",
]
PASSAGE_FIELDS = [
    "idx",
    "source",
    "faiss_id",
    "case_id",
    "absolute_paragraph_id",
    "opinion_id",
    "relative_paragraph_id",
    "text",
]
STATUTE_FIELDS = ["citation", "path", "state", "text", "idx"]


def qa_row(idx, source="1998", prompt="", question="Who wins?"):
    return dict(
        zip(
            QA_FIELDS,
            [
                idx,
                "mbe",
                "1",
                "1",
                source,
                "TORTS",
                "1",
                prompt,
                question,
                "A1",
                "B1",
                "C1",
                "D1",
                "A",
                "gold text",
                "mbe_9",
            ],
            strict=True,
        )
    )


def write_table(path, fields, rows, delimiter=","):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def write_zip(path, name, data):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, data)


def table_text(tmp_path, fields, rows):
    scratch = tmp_path / "scratch.tsv"
    write_table(scratch, fields, rows, delimiter="\t")
    return scratch.read_text(encoding="utf-8")


def test_barexam_text_comes_from_qa_file_and_split_from_split_file(tmp_path):
    empty = qa_row("mbe_5", question="")
    full = qa_row("mbe_5", question="The real question?")
    write_table(tmp_path / "qa.csv", QA_FIELDS, [full])
    write_table(tmp_path / "train.csv", QA_FIELDS, [])
    write_table(tmp_path / "validation.csv", QA_FIELDS, [empty])
    write_table(tmp_path / "test.csv", QA_FIELDS, [])
    question = barexam.load_questions(directory=tmp_path)[0]
    assert question["split"] == "validation"
    assert question["query"] == "The real question?"


def test_barexam_questions_and_malformed_rows_are_kept(tmp_path):
    train = [
        qa_row("mbe_0", prompt="Facts here.", question="Who wins?"),
        qa_row("mbe_1", source="Because an explanation sits in this field."),
    ]
    validation = [qa_row("mbe_2", source="MBE-1978-83-part1")]
    test = [qa_row("mbe_3", source="1991-Feb")]
    write_table(tmp_path / "qa.csv", QA_FIELDS, train + validation + test)
    write_table(tmp_path / "train.csv", QA_FIELDS, train)
    write_table(tmp_path / "validation.csv", QA_FIELDS, validation)
    write_table(tmp_path / "test.csv", QA_FIELDS, test)
    questions = barexam.load_questions(directory=tmp_path)
    assert [q["split"] for q in questions] == ["train", "train", "validation", "test"]
    assert questions[0]["query"] == "Facts here. Who wins?"
    assert questions[1]["query"] == "Who wins?"
    assert "A1" not in questions[0]["query"]
    assert questions[0]["gold"] == {"mbe_9"}
    assert questions[1]["source_ok"] is False and questions[1]["source_tag"] == "malformed"
    assert questions[2]["source_ok"] is True
    assert questions[3]["source_tag"] == "1991-Feb"
    assert len(barexam.load_questions("validation", directory=tmp_path)) == 1


@pytest.mark.parametrize(
    "tag", ["MBE-1972-78-part2", "MBE-1985-part7", "MBE-1989-90-part2", "1992", "1991-July"]
)
def test_barexam_accepts_every_source_form(tag):
    assert barexam.VALID_SOURCE.match(tag)


def test_barexam_pool_by_library(tmp_path):
    rows = [
        dict(zip(PASSAGE_FIELDS, [f"{source}_{i}", source, "", "", "", "", "", f"text {i}"], strict=True))
        for i, source in enumerate(["mbe", "wex", "caselaw", "caselaw"])
    ]
    path = tmp_path / "passages.tsv.zip"
    write_zip(path, "passages.tsv", table_text(tmp_path, PASSAGE_FIELDS, rows))
    assert [r["idx"] for r in barexam.iter_pool("doctrine", path)] == ["wex_1"]
    assert [r["idx"] for r in barexam.iter_pool("cases", path)] == ["caselaw_2", "caselaw_3"]
    assert [r["idx"] for r in barexam.iter_pool("real", path)] == ["wex_1", "caselaw_2", "caselaw_3"]
    assert len(list(barexam.iter_pool("full", path))) == 4


def housing_question(idx, state, statutes):
    return {
        "idx": idx,
        "state": state,
        "question": " Is it legal? ",
        "answer": "Yes",
        "question_group": 3,
        "statutes": [{"statute_idx": s, "citation": "c", "excerpt": "e"} for s in statutes],
        "original_question": "Original?",
        "caveats": [""],
    }


def test_housing_questions(tmp_path):
    path = tmp_path / "questions.json.zip"
    write_zip(path, "questions.json", json.dumps([housing_question(0, "New York", [5, 7, 5])]))
    question = housing.load_questions(path)[0]
    assert question["qid"] == "0"
    assert question["pool"] == "new york"
    assert question["query"] == "Is it legal?"
    assert question["gold"] == {"5", "7"}


def statute(idx, state, text='Quoted "text" here'):
    return dict(zip(STATUTE_FIELDS, ["cite", "a|b", state, text, str(idx)], strict=True))


def test_housing_states_are_streamed_one_at_a_time(tmp_path):
    path = tmp_path / "statutes.tsv.zip"
    rows = [statute(0, "ohio"), statute(1, "ohio"), statute(2, "iowa", "tab\there")]
    write_zip(path, "statutes.tsv", table_text(tmp_path, STATUTE_FIELDS, rows))
    groups = list(housing.iter_states(path))
    assert [(state, [r["idx"] for r in group]) for state, group in groups] == [
        ("ohio", ["0", "1"]),
        ("iowa", ["2"]),
    ]
    assert groups[0][1][0]["text"] == 'Quoted "text" here'
    assert groups[1][1][0]["text"] == "tab\there"


def test_near_duplicates_agree_with_brute_force():
    base = "the quick brown fox jumps over the lazy dog near the old river bank today"
    texts = [
        base,
        base.replace("today", "again"),
        base.upper(),
        "completely different words that share almost nothing with the sentence above",
        base[:30],
        "",
    ]
    grams = [audit.char_grams(audit.normalize(t)) for t in texts]
    expected = set()
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if grams[i] and grams[j] and len(grams[i] & grams[j]) / len(grams[i] | grams[j]) >= 0.8:
                expected.add((i, j))
    found = {(i, j) for i, j, _ in audit.near_duplicate_pairs(texts)}
    assert found == expected
    assert (0, 1) in found and (0, 2) in found


def test_source_year():
    assert audit.source_year("MBE-1978-83-part1") == "1978-83"
    assert audit.source_year("MBE-1985-part7") == "1985"
    assert audit.source_year("1991-Feb") == "1991"
    assert audit.source_year("malformed") == "malformed"
