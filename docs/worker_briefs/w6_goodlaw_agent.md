You are an implementation worker on the Open Book project in <repo>. A conductor session will review everything you do and re-run your checks, so report honestly: state what you ran and what you did not.

Read AGENTS.md, docs/PREREGISTRATION.md (sections 8, 9, 11 and Amendments 1, 3, 4) and docs/GOOD_LAW.md first. Read the existing code and follow its style: experiments/us_reader.py, experiments/us_retrieval.py, experiments/us_hypotheses.py, reader/, retrieval/, us/authority.py, prep/caselaw.py.

**Size is a hard constraint.** You may add at most 450 lines to `open_book_law/` outside `prep/`. The project owner must be able to explain the agent loop line by line without AI help, so write it plainly. Reuse existing functions. If the plan cannot fit, cut the least important exploratory piece and say so.

Background jobs are running from this checkout: dense encoding on the GPU, and the question generator, which writes to DATA_ROOT/derived/goodlaw/. Never write to that folder, and never kill anything. Commit only explicit paths, never `git add -A`, and never push.

**The GPU is busy.** Run smoke tests only, on at most 5 questions, and put them in the `us_smoke` suite. Good-law questions exist so far only for part of the pairs; use whatever is in questions.jsonl for smoke tests. Do not start any full run. Leave exact commands for the conductor.

## 1. The `scotus` corpus in retrieval
Add `--dataset scotus` to us_retrieval, reading DATA_ROOT/derived/scotus_passages.jsonl.gz: BM25 and dense, about 1 million passages, with queries from DATA_ROOT/derived/goodlaw/questions.jsonl. Record for each question the rank of the best passage from the overruled decision and the best passage from the overruling decision, and the opinion types (majority, concurrence, dissent) in the top 10. Questions leave the test if the overruling decision was itself overruled later (Amendment 3); use the authority graph and report the count. H9 comes from this run.

## 2. Good-law reader experiment: experiments/us_goodlaw.py
Conditions from section 8.3: `closed`, `old-only`, `new-only`, `both`, `both-dated`, `retrieved`, `citator`, `note`, plus the date test of Amendment 1 part C. Each question has `current_rule` and `superseded_rule` letters and passages. Record per question: predicted letter, the outcome class (current, superseded, other wrong), the probabilities and the docids used. The order of the two passages in `both` and `both-dated` must be balanced by a seeded coin, and recorded. `citator` uses `status()` as of today to drop overruled decisions before taking the top k. `note` adds "Overruled by X (year)" next to any overruled decision. Passage text stays out of run files.

## 3. Research agent: open_book_law/agent/
- `tools.py`: `search(query, library)`, returning the top 3 with passage id, case name, year and a short snippet; `read(passage_id)`; `check_status(citation, as_of_date)`.
- `loop.py`: a hand-written loop of about 100 lines. One system prompt describes the tools and a fixed JSON format for tool calls and for the final answer. Greedy generation with a cap per turn. At most 5 tool calls per question. A malformed call gets one short correction message and counts as malformed. After the budget, force a final answer. Log the full trace under DATA_ROOT/derived/agent_traces/ as one JSONL file per run, never one file per question, and only counts in git.
- `mcp_server.py`: serve the same three tools over MCP in as few lines as possible, for an outside agent. Add `mcp` to the venv with `~/venvs/open-book-law/bin/pip install mcp`. Say if this causes trouble, and in that case leave it out and tell the conductor.
- `experiments/us_agent.py`: runs the agent on a set of questions with reader `best-open`, and reports accuracy, superseded-rule rate, tool calls per question, malformed share, budget exhaustion, and runs that ignored a `check_status` result. Also apply the rule of Amendment 1 part D: if fewer than 80% of turns are valid on validation questions, mark H10 "not testable with this model".
- For the Claude comparison, write the exact `claude -p --mcp-config ... --output-format json --json-schema ...` command for the conductor, with a small script that collects answers. You cannot run claude yourself.

## 4. Verdicts
Extend us_hypotheses.py with H7 to H10 per sections 6 and 8 and Amendment 1, and keep Holm across all 11 tests. A missing input shows `pending`.

## 5. Label audit and error sample
- `experiments/us_label_audit.py` per section 9: a seeded sample of 100 questions from validation plus test, pooled top 10 of `bm25` and the best dense model, judged by Claude Opus 5.5 and then Claude Sonnet 5.5 through the CLI. The conductor runs it. Report the share of questions with a judged-relevant passage in the top 10, next to gold recall, with agreement between the judges.
- `experiments/us_error_sample.py` per section 11: a seeded sample of 100 wrong answers, first-pass labels from Claude through the CLI, using the fixed label list. It writes a review file for the project owner under docs/review/, with blank columns, and with only short attributed quotations.

## Tests
Tiny hand-made examples: the loop with a fake model that makes a correct call, a malformed call and a budget overrun; `citator` dropping a decision and keeping a later date before the overruling; outcome classes; passage order balance; H7 to H10 logic on synthetic data, including failing cases. `make test` and `make lint` must pass.

## When you are done
Everything committed. End your final message with a short factual report: lines added per file and the total, what ran, smoke speeds, whether tool calls looked valid on the small model, exact commands for the conductor in order with estimated hours, and every doubt or defect. If something blocks you, say so and stop.
