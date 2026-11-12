You are an independent code reviewer from another AI vendor. All this code was written by Claude models, and it is about to run confirmatory experiments. Your job is to find real bugs before those runs. The current folder is a read-only copy. Change nothing. Do not read anything outside this folder.

Read AGENTS.md and docs/PREREGISTRATION.md, then review for correctness, in this order: open_book_law/evalx.py, retrieval/bm25.py, retrieval/dense.py, retrieval/fusion.py, reader/mlx_reader.py, reader/prompts.py, experiments/us_reader.py, experiments/us_hypotheses.py, experiments/us_select.py, experiments/us_goodlaw.py, us/authority.py, us/goodlaw.py, agent/loop.py, agent/tools.py.

Look especially for:
- a metric or statistic that does not compute what its name or the preregistration says (paired bootstrap, McNemar, Holm, Wilson, verdict rules, the sign of differences, the population each hypothesis uses);
- data leakage: test or train records reaching selection, gold answers reaching a prompt, answer letters leaking through option order;
- off-by-one and tie-breaking errors in rankings, library filtering after ranking that silently shrinks k, truncation that removes the question or the options;
- reader mistakes: a wrong token for an answer letter, a wrong prompt cue;
- the good-law logic: the current and superseded letters, the citator date, and the rule that drops questions whose overruling decision was itself overruled;
- the agent loop: budget counting, malformed calls, forced answers.

Report only defects that you can demonstrate from the code. For each: file and line, the concrete input that goes wrong, what happens, and the smallest fix. Rank by how much it could change a reported result. Say clearly which files you read completely. Do not report style, and do not pad the list. If a file looks correct, say so in one line.
