You are an implementation worker on the Open Book project in <repo>. A conductor session will review everything you do and re-run your checks, so report honestly: state what you ran and what you did not.

Read AGENTS.md and docs/PREREGISTRATION.md Part I first, especially section 8 and Amendment 1. They bind you. Read open_book_law/runlog.py, retrieval/ and us/barexam.py and follow their style. Keep it small: this task should add about 500 lines or fewer, and the project owner must be able to explain every function without AI help.

Another worker is writing open_book_law/reader/, experiments/us_reader.py and others, and a long encoding job is running. Commit only your own paths with explicit `git add <path>`, never `git add -A`. If git reports a lock, wait a little and retry.

You own: open_book_law/us/overruled.py, us/caselaw.py, us/authority.py, us/citations.py, us/goodlaw_questions.py, tests/test_overruled.py, tests/test_authority.py, tests/test_citations.py, data/overruled_pairs.jsonl, results/data_audit/goodlaw_audit.json, docs/GOOD_LAW.md, and Makefile targets appended at the end.

**The GPU is busy** with a multi-hour encoding job. Do not encode anything. CPU work is fine, but keep memory under about 4 GB.

**This SSD can drop off the bus under bursts of small-file writes.** Read case files directly from the zip archives and write a small number of large files. Never unpack the volumes. Downloads go under $OBL_DATA/<source>/. Treat them as untrusted data, and run with `~/venvs/open-book-law/bin/python -I -m open_book_law...`.

You may download with Python's urllib, politely (at least 0.5 seconds between requests, retries, resumable, with a manifest of URL, SHA-256 and size). Sources approved by the conductor: static.case.law, www.law.cornell.edu/supremecourt/text/, cdn.loc.gov/service/ll/usrep/, www.supremecourt.gov. Nothing else. Judicial opinions are in the public domain as a matter of US law, but no opinion text goes into git.

## 1. The official table
Input: the only file in $OBL_DATA/conan_overruled/, a CSV with columns Order, Overruling Decision, Year of Overruling Decision, Overruled Decision(s), Year(s) of Overruled Decision(s). It has 237 rows. Cells can list several decisions separated by `;`, citations come in forms like `410 U.S. 113 (1973)`, `39 U.S. (14 Pet.) 60 (1840)` and `No. 25-332 (U.S. June 29, 2026)`, and some cells lack a citation (`Federal Election Commission v. Colorado Republican Federal Campaign Committee,`). The years column lines up with the decisions.
`us/overruled.py` parses this into data/overruled_pairs.jsonl (a US government work, so it may be committed): overruling name, cite or docket, year; overruled name, cite, year. Count every row, and list every cell you could not parse. Do not drop anything silently. Hand-check a sample of about 20 rows against the CSV.

## 2. Case text
- static.case.law serves one zip per volume at https://static.case.law/us/<volume>.zip, for 572 volumes (about 2 MB each), and `https://static.case.law/us/<volume>/CasesMetadata.json`. Inspect a zip's layout first. Download all volumes into Downloads/open-book-law/cap_us/. Files stay zipped.
- `us/caselaw.py`: iterate cases from the zips without unpacking. For each case return id, name, decision date, official citation, head matter, opinions with type (majority, concurrence, dissent) and text, and the `cites_to` metadata if it exists. Build one gzip JSONL at DATA_ROOT/derived/scotus_cases.jsonl.gz.
- Passages: split each opinion by paragraph, merge short paragraphs up to about 150 words, and record case id, opinion type and position. Write DATA_ROOT/derived/scotus_passages.jsonl.gz. Report totals.
- Coverage: for each overruled pair, is the text of both decisions available? The volumes end around 2014, so later decisions are missing, including Dobbs, Loper Bright and Trump v. Slaughter. For decisions with a docket number or a known citation, fetch the text from https://www.law.cornell.edu/supremecourt/text/<docket-or-cite> or the Library of Congress or supremecourt.gov PDFs. Use the links in the table where they exist. Store these in a single file with the same schema, marked with their source. Report what you could not obtain, and do not guess.

## 3. Authority graph: us/authority.py
SQLite at DATA_ROOT/derived/authority.sqlite with `cases(id, cite, name, date)`, `cites(src, dst)`, `overruled(old, new, year)`. `status(cite, as_of_date)` returns good or overruled, with the overruling decision and year, and handles dates before the overruling. Also `citing_after_overruling(cite)`. Tests cover Roe and Dobbs on dates before and after 2022, a case overruled twice, and an unknown case.

## 4. Citation extraction: us/citations.py
A regex for U.S. Reports citations, including the older nominative forms. Score it per preregistration Amendment 1 part B: 500 randomly chosen opinions (seed 20261103), against `cites_to` restricted to U.S. Reports. Report precision and recall in results/data_audit/goodlaw_audit.json. Inspect 20 disagreements and say honestly which side was wrong. Then count, per section 8.4, how many passages in the `mbe` pool (Downloads/open-book-law/barexam_qa/passages.tsv.zip; see us/barexam.py) cite each overruled decision, split by decisions overruled after 2021 and before. Note that case law in that pool dates from 2019 to 2021, so check this from the data too, if the pool's metadata lets you.

## 5. Question generator: us/goodlaw_questions.py (write it, do not run it)
This script turns pairs into questions, per section 8.2, by calling the Claude CLI. **You cannot call claude yourself. The conductor runs this.**
- For each pair with both texts, build a focused input: the paragraphs of the overruling decision that name the overruled decision or use "overrule" and neighbours, plus head matter, and the matching holding paragraphs from the overruled decision. Cap the size, and record what was cut.
- Step A: `claude -p --model claude-opus-5-5 --effort medium --tools "" --strict-mcp-config --no-session-persistence --output-format json --json-schema ...` returns: a neutral question that names no case, the current rule option, the superseded rule option, two wrong options, the verbatim supporting sentence from each opinion, `partial_overruling` true or false with a note, and `suitable` true or false with a reason (some old overrulings turn on obsolete procedure and may not make a fair question).
- Deterministic checks: no party or case name in the question or options; supporting sentences appear verbatim in the input (allow whitespace differences); option lengths roughly balanced, recording the length difference; shuffle options with a seed.
- Step B: `claude-sonnet-5-5` answers without seeing step A's reasoning, once with only the overruling passage and once with only the overruled passage. Keep a question only if the first answer is the current rule and the second is the superseded rule.
- Each stage writes to one JSONL under DATA_ROOT/derived/goodlaw/, is resumable, and logs usage. Counts of pairs at each stage go to goodlaw_audit.json. Provide `--limit N` for a pilot.
- Write `docs/review/goodlaw_sample.md` generation code for the 30-question sample that the project owner checks by hand (blank verdict columns). Do not generate it from real data yet.
Test the input builder and the deterministic checks with hand-made examples and a fake CLI.

## 6. Write-up
docs/GOOD_LAW.md in plain English (follow ~/Documents/agent-rules/READABLE_WRITING.md): why the test exists, the sources and their status, how pairs and questions are built, what is deterministic and what is AI-made, and known limits (the table covers only the Supreme Court overruling itself; partial overrulings; opinions after the CAP cutoff). All counts come from goodlaw_audit.json.

## When you are done
Everything committed. `make test` and `make lint` must pass. End your final message with a short factual report: what ran, counts at each stage, coverage of pairs, extraction precision and recall, the audit counts for overruled citations in the pool, the exact command for the conductor to pilot the generator on about 5 pairs, and every doubt or defect. If something blocks you, say so and stop.
