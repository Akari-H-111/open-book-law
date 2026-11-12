"""Hand-made cases and a fake Claude CLI. The real CLI never runs in tests."""

import json
import stat
import sys

from open_book_law.prep.goodlaw_questions import (
    OPTION_KEYS,
    build_input,
    call_claude,
    check_question,
    distinctive_words,
    focus_on_overruling,
    passage_with,
    run,
    shuffle_options,
    take_up_to,
    write_review_sample,
)

PAIR = {
    "pair_id": "1-1",
    "new_id": "new",
    "new_name": "Newman v. Ohio",
    "new_year": 2000,
    "old_id": "old",
    "old_name": "Oldfield v. Board of Education",
    "old_canonical": "100 U.S. 5",
    "old_year": 1950,
    "in_part": False,
}
FILLER = "Nothing here concerns anything of interest to this question at all."
NEW_CASE = {
    "head_matter": "Newman v. Ohio. Certiorari to the Supreme Court of Ohio.",
    "opinions": [
        {
            "type": "majority",
            "text": "\n".join(
                [
                    FILLER,
                    "The facts come first in this paragraph.",
                    "We have reconsidered Oldfield, 100 U. S. 5, and today we overrule it.",
                    "A landlord now owes a duty of repair to every tenant.",
                    FILLER,
                    FILLER,
                ]
            ),
        },
        {"type": "dissent", "text": "I would not overrule Oldfield at all."},
    ],
}
OLD_CASE = {
    "head_matter": "",
    "opinions": [
        {"type": "majority", "text": f"{FILLER}\nWe hold that a landlord owes no duty of repair to a tenant."}
    ],
}
ANSWER = {
    "question": "Does a landlord owe a tenant a duty of repair?",
    "current_rule": "Yes, a landlord owes every tenant a duty of repair.",
    "superseded_rule": "No, a landlord owes no tenant any duty of repair.",
    "wrong_1": "Only a landlord of farm land owes that duty of repair.",
    "wrong_2": "Only a tenant under a written lease has that repair right.",
    "support_overruling": "A landlord now owes a  duty of repair to every tenant.",
    "support_overruled": "We hold that a landlord owes no duty of repair to a tenant.",
    "partial_overruling": False,
    "partial_note": "",
    "suitable": True,
    "suitable_reason": "",
}


def focused():
    return build_input(PAIR, NEW_CASE, OLD_CASE)


def test_input_builder_finds_the_overruling_and_the_holding_and_skips_the_dissent():
    result = focused()
    assert any("overrule it" in p for p in result["new_paragraphs"])
    assert any("duty of repair to every tenant" in p for p in result["new_paragraphs"])
    assert FILLER not in result["new_paragraphs"][-1]
    assert not any("I would not" in p for p in result["new_paragraphs"])
    assert result["old_paragraphs"][-1].startswith("We hold")
    assert result["cut"]["new"]["paragraphs_total"] == 6
    assert result["new_head"].startswith("Newman")


def test_neighbours_score_lower_than_the_paragraph_itself():
    paragraphs = ["A.", "B.", "We overrule Oldfield.", "C.", "D."]
    assert focus_on_overruling(paragraphs, "Oldfield v. Board", None) == [0, 1, 5, 1, 0]


def test_size_cap_records_what_it_cut():
    paragraphs = ["one two three", "four five six", "seven eight"]
    kept, cut = take_up_to(paragraphs, [3, 2, 1], 5)
    assert kept == ["one two three", "seven eight"]
    assert cut["relevant_paragraphs_over_limit"] == 1
    assert (cut["paragraphs_total"], cut["words_total"], cut["words_kept"]) == (3, 8, 5)


def test_distinctive_words_leave_out_generic_ones():
    assert distinctive_words("Oldfield v. Board of Education") == {"Oldfield", "Education"}
    assert distinctive_words("Dobbs v. Jackson Women’s Health Organization") >= {"Dobbs", "Jackson", "Women"}
    assert "United" not in distinctive_words("Brown v. United States")


def test_good_question_passes_all_checks_with_whitespace_differences():
    result = check_question(ANSWER, focused(), PAIR)
    assert result["passed"], result


def test_name_in_an_option_fails():
    bad = ANSWER | {"wrong_1": "As in Oldfield, a landlord owes no repair duty here."}
    result = check_question(bad, focused(), PAIR)
    assert result["names_found"] == ["Oldfield"] and not result["passed"]


def test_citation_in_the_question_fails():
    result = check_question(ANSWER | {"question": "Under 100 U. S. 5, what is the duty?"}, focused(), PAIR)
    assert result["citation_found"] and not result["passed"]


def test_sentence_that_is_not_in_the_source_fails():
    result = check_question(
        ANSWER | {"support_overruled": "A sentence the opinion never had."}, focused(), PAIR
    )
    assert not result["support_overruled_found"] and not result["passed"]
    swapped = ANSWER | {"support_overruling": ANSWER["support_overruled"]}
    assert not check_question(swapped, focused(), PAIR)["support_overruling_found"]


def test_unbalanced_options_fail():
    long = "This option goes on far longer than any of the other three options do in this question, " * 2
    result = check_question(ANSWER | {"current_rule": long}, focused(), PAIR)
    assert not result["balanced"] and not result["passed"]


def test_shuffle_is_repeatable_and_keeps_every_option():
    first = shuffle_options(ANSWER, "1-1")
    assert first == shuffle_options(ANSWER, "1-1")
    assert sorted(first["letters"].values()) == sorted(OPTION_KEYS)
    for letter, key in first["letters"].items():
        assert first["options"][letter] == ANSWER[key]
    orders = {tuple(shuffle_options(ANSWER, f"{i}-1")["letters"].values()) for i in range(30)}
    assert len(orders) > 1


def test_passage_with_finds_the_paragraph():
    assert passage_with(["a b", "c  d e"], "c d") == "c  d e"
    assert passage_with(["a b", "c d"], "not there") == "a b\nc d"


FAKE_CLI = """#!{python}
import json, re, sys
open({log!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
prompt = sys.stdin.read()
mode = {mode!r}
if mode == "fail":
    sys.exit(3)
if "--model" in sys.argv and "claude-opus-5-5" in sys.argv:
    out = {answer!r}
else:
    # Answer from the passage: pick the option that the passage supports.
    passage = prompt.split("<passage>")[1].split("</passage>")[0]
    wanted = "no tenant" if "owes no duty" in passage else "every tenant"
    if mode == "wrong":
        wanted = "every tenant"
    letter = re.search(r"^([A-D])\\. .*" + wanted, prompt, re.M).group(1)
    out = {{"answer": letter}}
usage = {{"input_tokens": 10, "output_tokens": 2}}
print(json.dumps({{"structured_output": out, "usage": usage, "total_cost_usd": 0.5}}))
"""


def fake_cli(tmp_path, mode="good", answer=None):
    path = tmp_path / "fake_claude"
    log = str(tmp_path / "argv.log")
    path.write_text(FAKE_CLI.format(python=sys.executable, log=log, mode=mode, answer=answer or ANSWER))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path), tmp_path / "argv.log"


def test_call_uses_the_required_flags(tmp_path):
    binary, log = fake_cli(tmp_path)
    answer, usage = call_claude("prompt", "claude-opus-5-5", {"type": "object"}, binary)
    assert answer == ANSWER and usage["cost_usd"] == 0.5
    argv = json.loads(log.read_text())
    for flag in ("-p", "--strict-mcp-config", "--no-session-persistence", "--json-schema"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--effort") + 1] == "medium"


def run_fake(tmp_path, mode="good", answer=None, limit=None):
    binary, log = fake_cli(tmp_path, mode, answer)
    out = tmp_path / "out"
    return run([PAIR], {"new": NEW_CASE, "old": OLD_CASE}, out, binary, limit), out, log


def test_full_run_keeps_a_question_and_a_second_run_makes_no_new_calls(tmp_path):
    counts, out, log = run_fake(tmp_path)
    assert (counts["step_a_written"], counts["checks_failed"], counts["step_b_kept"]) == (1, 0, 1)
    row = json.loads((out / "questions.jsonl").read_text())
    assert row["label"] == "AI-written, not human-verified"
    assert row["options"][row["current_rule"]] == ANSWER["current_rule"]
    assert row["options"][row["superseded_rule"]] == ANSWER["superseded_rule"]
    calls = len(log.read_text().splitlines())
    assert calls == 3
    run_fake(tmp_path)
    assert len(log.read_text().splitlines()) == calls
    assert len((out / "questions.jsonl").read_text().splitlines()) == 1


def test_checker_sees_no_reasoning_from_the_writer(tmp_path):
    seen = tmp_path / "prompts.txt"
    script = tmp_path / "recording"
    script.write_text(
        FAKE_CLI.format(
            python=sys.executable, log=str(tmp_path / "argv.log"), mode="good", answer=ANSWER
        ).replace(
            "prompt = sys.stdin.read()",
            f"prompt = sys.stdin.read(); open({str(seen)!r}, 'a').write(prompt + '@@@')",
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    run([PAIR], {"new": NEW_CASE, "old": OLD_CASE}, tmp_path / "out", str(script))
    writer, with_new, with_old = seen.read_text().split("@@@")[:3]
    assert "<overruled>" in writer
    for prompt in (with_new, with_old):
        assert "current_rule" not in prompt and "suitable" not in prompt
    assert "owes no duty" not in with_new.split("</passage>")[0]
    assert "every tenant" not in with_old.split("</passage>")[0]


def test_question_is_dropped_if_the_checker_does_not_follow_the_old_passage(tmp_path):
    counts, out, _ = run_fake(tmp_path, mode="wrong")
    assert counts["step_b_answered"] == 1 and counts["step_b_kept"] == 0
    assert not (out / "questions.jsonl").exists()


def test_unsuitable_question_stops_before_the_checks(tmp_path):
    counts, _, log = run_fake(tmp_path, answer=ANSWER | {"suitable": False})
    assert counts["step_a_unsuitable"] == 1 and counts["checks_run"] == 0
    assert len(log.read_text().splitlines()) == 1


def test_failed_check_stops_before_the_checker(tmp_path):
    counts, _, log = run_fake(tmp_path, answer=ANSWER | {"question": "Was Newman right about the duty?"})
    assert counts["checks_failed_names"] == 1 and counts["step_b_answered"] == 0
    assert len(log.read_text().splitlines()) == 1


def test_cli_failure_is_logged_and_the_next_run_retries(tmp_path):
    counts, _, _ = run_fake(tmp_path, mode="fail")
    assert counts["cli_errors_logged"] == 1 and counts["step_a_written"] == 0
    counts, _, _ = run_fake(tmp_path)
    assert counts["step_a_written"] == 1 and counts["step_b_kept"] == 1


def test_limit_stops_after_that_many_pairs(tmp_path):
    second = PAIR | {"pair_id": "2-1"}
    binary, _ = fake_cli(tmp_path)
    counts = run([PAIR, second], {"new": NEW_CASE, "old": OLD_CASE}, tmp_path / "out", binary, limit=1)
    assert (
        counts["pairs_with_both_ids"] == 2
        and counts["pairs_in_this_run"] == 1
        and counts["step_a_written"] == 1
    )


def test_review_sample_has_blank_verdicts_and_the_label(tmp_path):
    _, out, _ = run_fake(tmp_path)
    questions = [json.loads(line) for line in (out / "questions.jsonl").read_text().splitlines()]
    path = write_review_sample(questions * 40, tmp_path / "sample.md", size=30)
    text = path.read_text()
    assert "AI-written, not human-verified" in text
    assert "Random sample of 30 of 40" in text
    assert text.count("## Pair") == 30
    assert "| Question is fair |  |  |" in text
