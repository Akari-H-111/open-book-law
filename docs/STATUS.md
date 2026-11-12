# Status

Last updated on 2026-11-12, for release v1.0.0.

## Done

- All 11 preregistered tests have run. `docs/RESULTS.md` has the verdicts: 6 supported and 5 not.
- The reproduction of the published baselines is in `docs/REPRODUCTION.md`.
- Scripts rebuild the summaries of the tests, the two results tables and the data of the website from the committed run files. The `verify` workflow checks this on every push. Another script builds the release files from a tagged commit.

## Not checked by a person yet

- The author has not yet checked any result.
- The 30-question sample of the AI-written good-law questions (`docs/review/goodlaw_sample.md`) and the 100 AI labels of wrong answers (`docs/review/error_sample.md`) wait for the author's review.

## Not done

These parts of the plan did not run, and no result depends on them:

- R1d, the reproduction with the largest search model (`e5-large`) on MBE questions. It would take about a day on this laptop.
- R2d, the same model on housing questions. It would take about 121 hours, so it is not attempted.
- The exploratory comparison with a Claude model as reader. The script `tools/claude_agent_answers.py` exists but has not run.
- The single run on the free NextGen sample questions (section 10 of the preregistration).
- The cause of the high recall of `e5-small` in target R1b is still unknown.
- The causes of the R3a divergence that were not tested: 4-bit weights, the chat template and the prompt wording.
- A check of why fine-tuning did not help in H6, for example the different text lengths in training (256 tokens) and evaluation (512 tokens).
- A rerun of everything from a clean container.
