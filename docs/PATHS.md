# Local paths

Before publication, on 2026-11-12, we removed the paths of the author's machine from every tracked file. This page says what changed, why the results did not change, and how to read the placeholders.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `$OBL_DATA` | The folder that holds the downloaded data and everything derived from it. The code reads the environment variable `OBL_DATA`. Without it, the code uses `data_local/` in the repository, which git ignores |
| `<repo>` | The root of this repository. Used only in the worker briefs |
| `<drive>` | The external drive that holds all projects and downloads on the author's machine. Used only in the worker briefs |

In the `data_sha256` field of a run file, a path without a placeholder is relative to the repository root, for example `data/overruled_pairs.jsonl`.

## What changed

Two commits made this change.

1. **Code and scripts.** `open_book_law/paths.py` no longer names a folder on the author's machine. `open_book_law/runlog.py` has a new function, `portable`, so new run files store `$OBL_DATA/...` and repository-relative paths. `us_finetune.py` uses it for the path of a saved model. The shell scripts in `tools/` find the repository from their own location and use `$HOME` for the virtual environment. `tools/run_queue.sh` expands `$OBL_DATA` inside a queue line. `tools/magesh_check.py` reads `OBL_DATA` too.
2. **Records.** A script replaced the paths as plain text in 133 tracked files. It did not parse and rewrite any JSON file, so the order of keys and the layout stayed the same. The rules, in the order they ran:
   1. In `docs/review/`, a Markdown link to `.../open-book-law/docs/X.md:N` became `../X.md`. The line numbers are still in the visible text.
   2. In JSON files, a string that started with the repository path became relative.
   3. The data folder became `$OBL_DATA`.
   4. The repository path became `<repo>`.
   5. Any other path on the external drive became `<drive>`.

## Why run files were edited

`AGENTS.md` says that run files are append-only. This edit is the one exception, and the author agreed to it.

**The reason.** The stored paths contained the author's user name and the name of a private drive. They would also not work on any other computer, so they told a reader nothing useful. Leaving them would have published private details. Rerunning the experiments to get clean files would have taken days on this laptop, and the new runs would not have been the runs that the verdicts rest on.

The edit changed only where a file was stored, never a number. In the run files, the paths sat in four places:

| Field | Files | Read by any script? |
|---|---:|---|
| keys of `data_sha256` | 116 | No. The hashes are unchanged |
| `model.saved_to` | 8 | No |
| `model.id` (the fine-tuned model) | 2 | No |
| `config.rollout` | 3 | Only as true or false, and it is still true |

**One consequence.** A run id is a hash of the run's `config`. In three files, `config.rollout` changed, so their run ids no longer equal the hash of the stored `config`:

| Run id | File |
|---|---|
| `c32ecf8920ae7b1d` | `results/runs/us_downstream/c32ecf8920ae7b1d.json` (test H4a) |
| `fb646bf5a440f2bf` | `results/runs/us_downstream/fb646bf5a440f2bf.json` (test H4b) |
| `37fbf29d54ace455` | `results/runs/us_smoke/37fbf29d54ace455.json` (a smoke run) |

No script checks a run id against its `config`, so nothing else changed. The only place where the original text survives is the author's private git history, which is not published. To recompute these three run ids, a person would need that history.

**Check.** After the edit, we ran the four summary scripts of `make reproduce` (`us_answers`, `us_verdicts`, `us_select`, `us_hypotheses`). They rewrote `results/summary/`, `docs/REPRODUCTION.md` and `docs/RESULTS.md`, and `git diff` showed no change in any of them.

## What this does not cover

- **Git history.** Earlier commits still contain the old paths and the author's commit email. So the public repository starts from a single new commit, and the full history stays private.
- **Files outside git.** `logs/`, the data folder and the local partial files were not changed.

## Files changed by the script

Some of these files were later moved out of the public tree, as `docs/EXECUTION_LEDGER.md` records on the same date. The second column counts the replacements by rule: `link` (rule 1), `json-repo` (rule 2), `data` (rule 3), `repo` (rule 4) and `drive` (rule 5).

| File | Replacements |
|---|---|
| `docs/review/walkthrough_codex_review_1.md` | link=19 repo=15 |
| `docs/review/walkthrough_codex_review_2.md` | link=16 repo=19 |
| `docs/worker_briefs/c2_walkthrough_review.md` | drive=1 |
| `docs/worker_briefs/c3_walkthrough_review.md` | drive=1 |
| `docs/worker_briefs/w10_lit_fixes.md` | data=2 repo=1 |
| `docs/worker_briefs/w11_walkthrough.md` | drive=1 |
| `docs/worker_briefs/w2_us_retrieval.md` | data=1 repo=1 |
| `docs/worker_briefs/w3_us_reader.md` | data=1 repo=1 |
| `docs/worker_briefs/w4_goodlaw_data.md` | data=2 repo=1 |
| `docs/worker_briefs/w5_simplify.md` | repo=1 |
| `docs/worker_briefs/w6_goodlaw_agent.md` | repo=1 |
| `docs/worker_briefs/w7_fixes.md` | repo=1 |
| `docs/worker_briefs/w8_literature.md` | data=2 repo=1 |
| `docs/worker_briefs/w9_us_primer.md` | data=2 repo=1 |
| `results/data_audit/magesh_check.json` | data=1 |
| `results/runs/us_agent/6146f77693af14f4.json` | data=3 |
| `results/runs/us_agent/76a12e241af2b42d.json` | data=5 |
| `results/runs/us_agent/be70e40cef95a279.json` | data=5 |
| `results/runs/us_diagnostics/062d8d251c0b1d7c.json` | data=4 |
| `results/runs/us_diagnostics/3270c3032dcc33a7.json` | data=2 |
| `results/runs/us_diagnostics/375991b9ed5aead2.json` | data=2 |
| `results/runs/us_diagnostics/65cb3b18226d7b1c.json` | data=2 |
| `results/runs/us_downstream/09a02f60f0e0eed3.json` | data=5 |
| `results/runs/us_downstream/3ca352e2b22e80d0.json` | data=5 |
| `results/runs/us_downstream/57439e3bc633bb80.json` | data=2 |
| `results/runs/us_downstream/6d44032e0dc1bc95.json` | data=5 |
| `results/runs/us_downstream/8061e50323d4bd10.json` | data=5 |
| `results/runs/us_downstream/b0ce7af8d9c06334.json` | data=5 |
| `results/runs/us_downstream/ba7b0eae6667c2b2.json` | data=5 |
| `results/runs/us_downstream/bc9866b8f509d13c.json` | data=5 |
| `results/runs/us_downstream/c32ecf8920ae7b1d.json` | data=7 |
| `results/runs/us_downstream/f90498bed7d31fdb.json` | data=3 |
| `results/runs/us_downstream/fb646bf5a440f2bf.json` | data=7 |
| `results/runs/us_downstream/ff58a1cf81f5e4ac.json` | data=3 |
| `results/runs/us_finetune/428a001d43e56e9c.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/58ffe701f96ad482.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/a37ef8eb21b1b248.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/b628f684d20678d0.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/bd578ac4833d144c.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/def9a6b167863e14.json` | json-repo=1 data=3 |
| `results/runs/us_finetune/fdc6a2962798a444.json` | json-repo=1 data=3 |
| `results/runs/us_goodlaw/07838f54df6478e4.json` | data=3 |
| `results/runs/us_goodlaw/508192938bff6bd8.json` | data=3 |
| `results/runs/us_goodlaw/5597b4ca02870a96.json` | data=3 |
| `results/runs/us_goodlaw/706be530bacd2057.json` | data=3 |
| `results/runs/us_goodlaw/759a7321f03faa87.json` | data=3 |
| `results/runs/us_goodlaw/83124cd0618e215c.json` | data=3 |
| `results/runs/us_goodlaw/9a170bc33890eef8.json` | data=3 |
| `results/runs/us_goodlaw/d1fa719011ae04dd.json` | data=3 |
| `results/runs/us_goodlaw/d7adb44527635e73.json` | data=3 |
| `results/runs/us_goodlaw/dd658d2b7cfeff72.json` | data=3 |
| `results/runs/us_goodlaw/fe9cca9d1cb8b3b5.json` | data=3 |
| `results/runs/us_label_audit/e5982ad2199fda3a.json` | data=5 |
| `results/runs/us_reader/0a3bd283a1dd357b.json` | data=2 |
| `results/runs/us_reader/0e42fd0375717698.json` | data=5 |
| `results/runs/us_reader/0e7dc49f227b66a2.json` | data=5 |
| `results/runs/us_reader/15eb1f50138858a0.json` | data=5 |
| `results/runs/us_reader/37b2a24e08bf9b8c.json` | data=5 |
| `results/runs/us_reader/3a800718b8513119.json` | data=5 |
| `results/runs/us_reader/42bfc4709b07d14b.json` | data=2 |
| `results/runs/us_reader/4e6221e859aaf510.json` | data=2 |
| `results/runs/us_reader/516980c4b1bbd93a.json` | data=5 |
| `results/runs/us_reader/5961e73dee531437.json` | data=5 |
| `results/runs/us_reader/5feb10aa4a385948.json` | data=5 |
| `results/runs/us_reader/77b704031495cce7.json` | data=2 |
| `results/runs/us_reader/7ec96a250bcaea28.json` | data=5 |
| `results/runs/us_reader/902459050758c302.json` | data=5 |
| `results/runs/us_reader/95a18b34264b1938.json` | data=5 |
| `results/runs/us_reader/9bb3d74024beaa42.json` | data=5 |
| `results/runs/us_reader/a578b30b19fabf60.json` | data=5 |
| `results/runs/us_reader/dc5d0f854fe0300e.json` | data=2 |
| `results/runs/us_reader/e2da78d159ce9f8d.json` | data=5 |
| `results/runs/us_retrieval/009ec399e8e08026.json` | data=2 |
| `results/runs/us_retrieval/064ab92f0a8e8c80.json` | data=4 |
| `results/runs/us_retrieval/362e4429624184c3.json` | data=5 |
| `results/runs/us_retrieval/b89510c86c4e05b5.json` | data=4 |
| `results/runs/us_retrieval/ba48ee23902af913.json` | data=2 |
| `results/runs/us_rollouts/b1d95d164355cff1.json` | data=1 |
| `results/runs/us_smoke/01ff1be3362f765f.json` | data=2 |
| `results/runs/us_smoke/0955ba859113b361.json` | data=2 |
| `results/runs/us_smoke/0f6def6b26c1a976.json` | data=5 |
| `results/runs/us_smoke/119f5f7652d24723.json` | data=3 |
| `results/runs/us_smoke/12e0c3c0fd113f22.json` | data=4 |
| `results/runs/us_smoke/13e28fd00b74b60b.json` | data=3 |
| `results/runs/us_smoke/189dd0a3d3f4113c.json` | data=5 |
| `results/runs/us_smoke/191ce5e24e39fc89.json` | data=2 |
| `results/runs/us_smoke/20459b79aab4d37d.json` | data=2 |
| `results/runs/us_smoke/21148c411760ab8a.json` | data=2 |
| `results/runs/us_smoke/22755798907fb3e5.json` | data=2 |
| `results/runs/us_smoke/2669c4c73ab0af25.json` | data=4 |
| `results/runs/us_smoke/2850394db2e26c6e.json` | data=1 |
| `results/runs/us_smoke/2d36da496704cf75.json` | data=3 |
| `results/runs/us_smoke/317a517377ea44f6.json` | data=5 |
| `results/runs/us_smoke/37fbf29d54ace455.json` | data=6 |
| `results/runs/us_smoke/3fb636754492de68.json` | data=5 |
| `results/runs/us_smoke/41b9390fd30ca0db.json` | data=2 |
| `results/runs/us_smoke/548353700231a8ea.json` | data=2 |
| `results/runs/us_smoke/5affe215a77eb85c.json` | data=2 |
| `results/runs/us_smoke/5b3e7a505b9fd770.json` | data=4 |
| `results/runs/us_smoke/66056f296c26fea2.json` | data=4 |
| `results/runs/us_smoke/6a9a5c11223f74be.json` | data=5 |
| `results/runs/us_smoke/6e3b522c9bb9851b.json` | data=3 |
| `results/runs/us_smoke/729ca8ac0735189c.json` | data=2 |
| `results/runs/us_smoke/74d7dddb11adc5f8.json` | data=2 |
| `results/runs/us_smoke/788ba5c164c2a3ce.json` | data=5 |
| `results/runs/us_smoke/7925228b9e1a9e02.json` | data=2 |
| `results/runs/us_smoke/81a6c35dc6fdd83f.json` | data=5 |
| `results/runs/us_smoke/82b37608b6c94ba6.json` | data=3 |
| `results/runs/us_smoke/88d315054eb39eb4.json` | data=3 |
| `results/runs/us_smoke/8ca9f6f2699ab874.json` | data=5 |
| `results/runs/us_smoke/90ca780bea6390d3.json` | data=2 |
| `results/runs/us_smoke/9492d1aab16165c2.json` | data=2 |
| `results/runs/us_smoke/9530352736e33ffd.json` | data=2 |
| `results/runs/us_smoke/98bafc5556d0477b.json` | data=3 |
| `results/runs/us_smoke/a00b79185f113425.json` | data=3 |
| `results/runs/us_smoke/a22d9601fc1c814f.json` | data=4 |
| `results/runs/us_smoke/a71180b3cdb164bd.json` | data=2 |
| `results/runs/us_smoke/ad0912ed268ab6ba.json` | data=5 |
| `results/runs/us_smoke/b0ad7d8724d2b529.json` | data=2 |
| `results/runs/us_smoke/b6e139f22154d735.json` | json-repo=1 data=3 |
| `results/runs/us_smoke/b8cf24289d639c38.json` | data=2 |
| `results/runs/us_smoke/c34c2834d1acce09.json` | data=3 |
| `results/runs/us_smoke/ce0b7c360fa35fde.json` | json-repo=1 data=3 |
| `results/runs/us_smoke/dcdda91f87498e8b.json` | data=4 |
| `results/runs/us_smoke/e102908957ae4e65.json` | json-repo=1 data=3 |
| `results/runs/us_smoke/e934e4fc0e21de3a.json` | data=2 |
| `results/runs/us_smoke/fab2baea9c27f413.json` | data=2 |
| `results/runs/us_smoke/fcec0733db556be5.json` | data=2 |
| `results/runs/us_states/0643777ad54eeabb.json` | data=2 |
| `results/runs/us_states/4562ca7de9977b74.json` | data=2 |
| `results/runs/us_states/bd95d37a2633a73f.json` | data=2 |
| `tools/queue_4.txt` | data=2 |
| `tools/queue_5.txt` | data=2 |
