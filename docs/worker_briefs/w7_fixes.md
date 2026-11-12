You are an implementation worker on the Open Book project in <repo>. A conductor session will review everything and re-run your checks, so report honestly: state what you ran and what you did not.

Read AGENTS.md and docs/PREREGISTRATION.md (sections 8, 9, 11, Amendments 1 to 5). A multi-hour encoding job and the good-law question generator are running from this checkout: never kill them, and never write under DATA_ROOT/derived/goodlaw or derived/embeddings/e5-base. Commit only explicit paths, never `git add -A`, and never push.

Size limit: `open_book_law/` without `prep/` is 2,970 lines and may reach about 3,250. The project owner must explain this code without AI, so write plainly. No dense one-liners to save lines.

## 1. Fix the defects from an independent review (the conductor confirmed each in the code)
1. **Dense `scotus` cannot start.** `suite_for` treats every `scotus` run as downstream, so `run_dense` requires an existing store and never reaches `prepare_store`. Let the first full dense `scotus` run create the store. `--limit` smoke runs must still refuse to create it.
2. **Empty rankings drop questions.** A BM25 query with no matching tokens writes no rank rows, and `us_reader.py` then silently drops that question, and so does `us_goodlaw.py`. Fix it so that the question stays and is answered with empty context, while a question missing because a run is incomplete still fails loudly. Keep reading old rank files working.
3. **Rollout runs can be picked for ordinary retrieval.** Reader config has no such field today, or lookups ignore it: check how a reader run knows that its rank run used a rollout. `us_select.py` and `us_hypotheses.py` must not use rollout-based runs for H1 to H3. Add a test.
4. **Citator depth.** `citator_top_k` filters only the rankings available. Read the top 1000 from the data folder, not the top 100 in git. Record per question how many passages it got, and report the number of questions with fewer than k. Do not search further.
5. **Agent budget.** The plan says 5 tool calls per question, but the loop counts turns, including malformed replies. Count tool calls against the budget, with a separate fixed limit of 3 malformed replies. Both limits are reported.
6. **Agent crash.** `{"tool": [], "args": {}}` raises TypeError at `name in ARGS`. Require a string name and count it as malformed. Add a test.

Do not change the dense tie handling: the conductor records it as a known limit in docs/EXECUTION_LEDGER.md.

## 2. Restore what an earlier worker cut for size
Untested drafts are in docs/drafts/. Rework them plainly, test them, and delete the drafts when done.
- `experiments/us_error_sample.py`, per section 11. **This one is required.** It draws a seeded sample of 100 wrong answers, gets first-pass labels from Claude through the CLI with the fixed label list, and writes docs/review/error_sample.md for the project owner, with blank review columns and only short attributed quotations.
- `experiments/us_label_audit.py`, per section 9.
- The date test of Amendment 1 part C, as a condition in `us_goodlaw.py`.
You cannot call `claude` yourself. Test them with a fake CLI, and leave exact commands for the conductor.

## 3. Small items
- Add `mcp` to requirements-lock.txt, with the exact installed version.
- Check that `questions.jsonl` keeps the five pilot pairs (4-1, 150-1, 2-1, 166-1, 82-1) as its first rows, because `--limit 5` smoke runs must touch only those. Say what you found.

## 4. Smoke tests on real models
The GPU is shared with the encoding job, so keep them short. Use at most 5 questions, the `us_smoke` suite, and `mbe` validation or the five pilot good-law questions only:
- `us_retrieval --dataset scotus --retriever bm25 --limit 5` (this builds an index of about 1 million passages, so report its time and memory);
- `us_goodlaw --reader llama8 --condition citator --rank-run <that id> --k 3 --limit 5`, and one condition with passages (`both-dated`);
- `us_agent --dataset mbe --split validation --reader qwen3 --library real --retriever bm25 --limit 5`.
Read the actual traces in the data folder, and report honestly whether the small model makes valid tool calls. If it does not, do not tune it on anything other than `mbe` validation.

## When you are done
`make test` and `make lint` pass, and everything is committed. End with a short factual report: each fix with its commit, tests added, line counts, smoke results and speeds, what valid-call share you saw and on how many turns, the commands left for the conductor, and every doubt. If something blocks you, say so and stop.
