# The good-law test: data and question building

Status: the data steps have run. The question generator has also run on real data, first as a pilot and then as a full generation. There are 227 questions. They stay labelled "AI-written, not human-verified" until the project author has checked the random sample of 30 in `docs/review/goodlaw_sample.md`. That check has not happened yet.

All counts below come from `results/data_audit/goodlaw_audit.json`. `make goodlaw-data` writes that file.

## Why the test exists

A lawyer must check that an authority is still good law. A retriever has no sense of time, so it can return an overruled decision as readily as a current one. A small model may then follow that decision.

This test measures that risk. It needs a list of decisions that are no longer good law. The official table gives that list, so no AI decides what was overruled.

## Sources and their status

| Source | What we use | Status | Where it lives |
|---|---|---|---|
| Constitution Annotated, table of overruled decisions | Which decision overruled which | US government work | Parsed pairs are in `data/overruled_pairs.jsonl` |
| Caselaw Access Project (CAP), U.S. Reports volumes | Opinion text and citation metadata | Judicial opinions are public domain | Data folder only, never in git |
| Cornell Legal Information Institute | 16 decisions that CAP lacks | Judicial opinions are public domain | Data folder only, never in git |

Every download has a manifest with its URL, SHA-256 hash and size.

## How pairs are built

`prep/overruled.py` turns each table row into one pair per overruled decision.

| Measure | Count |
|---|---:|
| Table rows | 237 |
| Rows that failed to parse | 0 |
| Pairs | 293 |
| Distinct overruled decisions | 283 |
| Pairs marked "in part" in the table | 36 |
| Overruled decisions with no citation in the table | 100 |
| Overruling decisions with only a docket number | 14 |

**The preregistration says 271 overruled decisions, and this count differs.** The figure 271 equals the number of rows plus the number of semicolons. The exported table also joins some names with only a comma, as in `Adamson v. California,Twining v. New Jersey,`. Its years column confirms that these are separate decisions, so we count 293 pairs.

### Matching pairs to text

A citation in the table decides the match. If the table has no citation, the name and year must lead to exactly one decision. When several decisions fit, the code applies these tests in order, and it stops as soon as one decision remains:

1. The overruling opinion cites the decision, according to CAP.
2. The decision is a full opinion of at least 300 words. Many one-line orders share a name with the real opinion.
3. The name matches exactly.

If more than one decision remains, the pair stays unmatched. The code never picks at random. CAP often dates old cases by court term, so a search with no result also tries one year either side of the table's year.

| How a decision was found (586 sides of 293 pairs) | Count |
|---|---:|
| Table citation | 460 |
| Table citation, under another name in CAP | 6 |
| Table citation absent from CAP, then name and year | 2 |
| Docket number | 18 |
| Name and year | 94 |
| Name and a year one away | 5 |
| Not matched | 1 |

The "another name" group holds cases such as the Minnesota Rate Cases, which CAP files as Simpson v. Shepard. An early version of the matching picked some wrong decisions, including a one-line order in place of a full opinion. I found these by checking whether each overruling opinion cites its match, and then fixed the rules. That check is not a test that runs on every build.

### Coverage

| Measure | Count |
|---|---:|
| Pairs with text for both decisions | 291 |
| ... of which one text has under 300 words | 13 |
| Pairs that lack a text | 2 |
| Decisions fetched from Cornell | 16 |
| Decisions that we tried and failed to fetch | 0 |

The two pairs without text are:

- **Pair 169-1, Leeds & Catlin Co. v. Victor Talking Machine Co.** The table gives no citation. CAP has two full opinions with this name on the same day, and the overruling opinion does not settle which one is meant. We did not guess.
- **Pair 215-1, Peirce v. New Hampshire.** CAP has an entry at this citation, but it holds no opinion text. Cornell has a page for it in a layout that our parser does not read. We did not try other sources.

### Disagreements with the table

The audit lists these and we keep them. They do not change which decisions count as overruled.

- The table's year differs from the decision date in 34 entries. Most are old decisions that CAP dates by term. One looks like a slip in the table: Jones v. Alfred H. Mayer Co. has the year 1969 in the table, and CAP dates it 1968.
- Two citations differ. The table gives `406 U.S. 366` for Johnson v. Louisiana, and CAP has the case at `406 U.S. 356`. That table row concerns Justice Powell's concurrence, so 366 may be the page where it starts. For United States v. Dixon the table gives `509 U.S. 688`, and CAP has `509 U.S. 690`.

## Case text and passages

`prep/caselaw.py` reads each case from its zip file, without unpacking the volumes.

| Measure | Count |
|---|---:|
| Cases | 330,011 |
| ... from CAP | 329,995 |
| ... from Cornell | 16 |
| Cases with no opinion text | 11,263 |
| Passages | 1,007,513 |

Each passage holds whole paragraphs, merged up to about 150 words. A longer paragraph stays whole. Most CAP entries are short orders, so a count of cases says little about the amount of legal reasoning.

## The authority graph

`us/authority.py` builds one SQLite file with 330,012 cases, 564,602 citation links and 293 overruling records. The case count is one higher than above, because the table names one decision that we could not match to any text. No AI is involved.

`status(reference, as_of_date)` takes a citation, a case id or a docket number. It returns one of four answers: `good`, `overruled`, `not_decided` or `unknown`. An overruling counts from the decision date of the overruling case. If only a year is known, it counts from the last day of that year. A case overruled twice shows only the overrulings that had happened by the date asked about.

We added one column to the planned schema: `in_part`, which marks partial overrulings.

## Citation extraction

`prep/citations.py` finds U.S. Reports citations with a regular expression, including the early reporters such as `14 Pet. 60`. We scored it against CAP's `cites_to` metadata, as Amendment 1 part B asks.

| Sample | Opinions | Agreed | Regex only | CAP only | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Random, as preregistered (seed 20261103) | 500 | 342 | 5 | 0 | 0.986 | 1.000 |
| Post hoc: opinions of at least 300 words | 500 | 4,074 | 38 | 10 | 0.991 | 0.998 |

The second row is post hoc. I added it because most opinions in the first sample are short orders, which contain few citations.

**The reference changed after the first run.** The first run used the page in CAP's link paths and gave precision 0.971 and recall 0.988. Those values are in the git history of the audit file, at commit `470df42`. That history is private, as the release notes explain. Reading the disagreements showed that this page can differ from the first page of the case. For example, `377 U. S. 271` links to `/us/377/0403-01`. The scores above use CAP's printed citations. This change raised both scores, so please read them with that in mind.

### Which side was wrong

I read 20 disagreements: all 5 from the preregistered sample, plus 15 chosen at random from the post hoc sample. These verdicts are AI-made and are in `data/citation_review.jsonl`.

| Verdict | Count |
|---|---:|
| The text prints the citation and CAP missed it | 17 |
| CAP is right and the regex missed the citation | 3 |

CAP often missed longhand forms such as `12 Peters, 54`. The regex missed `5 Wheat. Rep. 1`, and it missed two citations with a comma typo, such as `101 U. S, 184`. One of the 17 may give a page inside a case and not its first page.

Three limits apply:

- These scores measure agreement with CAP, and CAP is not the truth.
- A citation that both sides miss stays invisible, for example one with damaged scanned text.
- The regex does not count short forms such as `410 U. S., at 150`.

## Audit of the `mbe` pool (section 8.4)

This counts pool passages that cite an overruled decision. A passage that cites two such decisions counts twice. A decision counts as "overruled after 2021" if its first overruling came after 2021.

| Group | Decisions | Decisions cited at least once | Citing passages |
|---|---:|---:|---:|
| First overruled after 2021 | 5 | 5 | 329 |
| First overruled by 2021 | 275 | 104 | 630 |

| Decision first overruled after 2021 | First overruled | Citing passages |
|---|---:|---:|
| Chevron U.S.A., Inc. v. Natural Resources Defense Council, Inc. | 2024 | 210 |
| Planned Parenthood of Southeastern Pennsylvania v. Casey | 2022 | 72 |
| Roe v. Wade | 2022 | 36 |
| Humphrey's Executor v. United States | 2026 | 8 |
| Federal Election Commission v. Colorado Republican Federal Campaign Committee | 2026 | 3 |

Most of the citing passages are case law (321 and 602), and some are `wex` (8 and 24). Four `mbe` passages cite a decision from the second group. One decision has no usable citation, so it is not counted. A passage may cite a decision only to criticize it or to note that it was overruled, so these counts do not show reliance on bad law.

### Does the pool date from 2019 to 2021?

The pool has no date column, so the data cannot settle this. As a rough check, I took the newest year in parentheses in each of the 23,406 case-law opinions. That year is only a lower limit on the date of the opinion, and a passage shows only part of an opinion.

| Newest year in parentheses | Opinions |
|---|---:|
| None found | 6,443 |
| Before 2010 | 1,545 |
| 2010 to 2017 | 5,061 |
| 2018 | 6,345 |
| 2019 | 3,966 |
| 2020 | 42 |
| 2021 | 2 |
| 2023 or 2024 | 2 |

This fits opinions written up to about 2019 or 2020, but it does not prove that date range. I did not inspect the two opinions with 2023 or 2024. The pool has few opinions with a year after 2019, so 2019 to 2021 may overstate the end of the range.

None of the pool's case ids appear in our Supreme Court corpus. If those ids are CAP ids, as they appear to be, then the pool's case law contains no Supreme Court opinions, and it only cites them.

## How questions are built

`prep/goodlaw_questions.py` follows section 8.2 of the preregistration. It calls the Claude command-line tool. It has run on real data, as a pilot and then as a full generation.

| Step | Made by | What happens |
|---|---|---|
| Choose the pairs | Table and code | Pairs with text on both sides |
| Build the input | Code | Paragraphs that use "overrule" or name the old decision, their neighbours, the head matter, and the old opinion's paragraphs that best match |
| Write the question | Claude Opus 5.5 | One neutral question, four options, one quoted sentence from each opinion, a note on partial overruling, and a verdict on whether the point is fair to test |
| Check the question | Code | No party or case name, no citation, quoted sentences found in the input, options of balanced length, options all different |
| Shuffle the options | Code | Seeded by pair |
| Answer with one passage | Claude Sonnet 5.5 | Answers twice, each time with one passage only, and it never sees the writer's reasoning |
| Keep or drop | Code | Keep only if the overruling passage leads to the current rule and the overruled passage leads to the superseded rule |

The input is capped at 300 words of head matter, 2,500 words from the overruling decision and 1,500 words from the overruled decision. Each input records what was cut.

The table decides what was overruled. Only the wording of the questions is AI-made. Questions stay labelled "AI-written, not human-verified" until the project author has checked a random sample of 30 in `docs/review/goodlaw_sample.md`. That file does not exist yet, so no question has been checked by a person.

## Known limits

- **The table is narrow.** It lists only decisions that the Supreme Court itself overruled. It does not cover decisions weakened without being overruled, statutes that replaced a rule, or lower-court law.
- **Partial overrulings are hard.** The table marks 36 pairs "in part", but it does not say which part. The AI step must identify the part, and that judgment is not independently checked until the hand review.
- **Some decisions are very short.** Some overruled decisions are one-line orders, such as Baker v. Nelson. We expect these to fail the fairness step, and we will report how many do.
- **CAP stops before the newest decisions.** The authority graph has no outgoing citations from the 16 Cornell decisions, so a count of later citations from the graph would be too low.
- **Some recent decisions have no reporter citation here.** The table gives only a docket number for them. `status` finds such a decision by its docket number or case id. A search by its later U.S. Reports citation still answers `unknown`.
- **Decisions on the same first page are treated together.** `status` looks up a first page, so a one-line order that shares a page with an overruled decision would appear overruled too.
- **The paragraph selection is a simple rule.** The overruled opinion's paragraphs are chosen by shared words and phrases such as "we hold". This rule can miss the real holding, and the question step may then mark the pair as unfair or write a weaker question.
- **The name check can be wrong.** It looks for capitalized words from the case names, so a question that fairly mentions a state that was also a party will fail.
- **This is a research benchmark.** It gives no legal advice.

## How to run it

```
make goodlaw-data
make goodlaw-questions ARGS="--limit 5"
```
