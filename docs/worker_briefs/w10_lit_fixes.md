You are editing docs/LITERATURE.md in <repo>. Follow ~/Documents/agent-rules/READABLE_WRITING.md. Paper texts are in $OBL_DATA/papers/.

1. Apply every item in sections 1 and 2 of docs/review/literature_check_codex.md. First check each against the paper text, and if an item is wrong, say so and do not apply it.
2. The rule of this project is that every number traces to a committed script. Your partial check of Magesh et al. used a script outside the repository. Write it as tools/magesh_check.py (short, plain, reads $OBL_DATA/legal_rag_hallucinations/dataset.csv, writes results/data_audit/magesh_check.json), run it with `~/venvs/open-book-law/bin/python -I tools/magesh_check.py`, and update the section so that it names these files and uses their numbers.
3. Item 3 of section 3 of the check notes that docs/GOOD_LAW.md says that no question exists on real data, which is out of date: a pilot and a full generation have run, and more than 150 questions exist. Correct only that status wording in docs/GOOD_LAW.md, with no counts unless a committed file holds them.

Commit only these paths, with explicit `git add`: docs/LITERATURE.md, docs/GOOD_LAW.md, tools/magesh_check.py, results/data_audit/magesh_check.json, docs/review/literature_check_codex.md. Never push. Reply with: items applied, items rejected and why, and the script's output.
