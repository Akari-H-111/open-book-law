# Reproduction of the retrieval baselines

This page compares our retrieval results with the published values of Zheng et al. 2025, "A Reasoning-Focused Legal Retrieval Benchmark". The rules are in section 5 of `docs/PREREGISTRATION.md`.

All values are percentages. The script `open_book_law/experiments/us_verdicts.py` writes the tables below from run files, so nobody edits them by hand. A target shows `pending` until its run exists.

<!-- AUTO:BEGIN -->
| Target | Dataset | Retriever | Metric | Published | Ours | Difference | Limit | Metric verdict | Target verdict |
|---|---|---|---|---:|---:|---:|---:|---|---|
| R1a | mbe | bm25 | R@10 | 0.75 | 0.67 | -0.08 | 1 | reproduced | reproduced |
| R1a | mbe | bm25 | R@100 | 2.26 | 2.43 | +0.17 | 2 | reproduced | reproduced |
| R1a | mbe | bm25 | R@1000 | 8.79 | 7.95 | -0.84 | 3 | reproduced | reproduced |
| R1b | mbe | e5-small | R@10 | 0.59 | 0.92 | +0.33 | 1 | reproduced | partly reproduced |
| R1b | mbe | e5-small | R@100 | 2.68 | 4.10 | +1.42 | 2 | reproduced | partly reproduced |
| R1b | mbe | e5-small | R@1000 | 9.29 | 12.80 | +3.51 | 3 | partly reproduced | partly reproduced |
| R1c | mbe | e5-base | R@10 | 0.84 | 0.75 | -0.09 | 1 | reproduced | reproduced |
| R1c | mbe | e5-base | R@100 | 3.51 | 4.44 | +0.93 | 2 | reproduced | reproduced |
| R1c | mbe | e5-base | R@1000 | 11.21 | 11.88 | +0.67 | 3 | reproduced | reproduced |
| R1d | mbe | e5-large | R@10 | 0.92 | pending | pending | 1 | pending | pending |
| R1d | mbe | e5-large | R@100 | 4.27 | pending | pending | 2 | pending | pending |
| R1d | mbe | e5-large | R@1000 | 12.30 | pending | pending | 3 | pending | pending |
| R2a | housing | bm25 | R@10 | 40.81 | 37.22 | -3.59 | 2 | partly reproduced | partly reproduced |
| R2a | housing | bm25 | R@100 | 62.41 | 59.35 | -3.06 | 3 | partly reproduced | partly reproduced |
| R2a | housing | bm25 | R@1000 | 76.19 | 75.02 | -1.17 | 3 | reproduced | partly reproduced |
| R2b | housing | e5-small | R@10 | 34.35 | 34.66 | +0.31 | 2 | reproduced | reproduced |
| R2b | housing | e5-small | R@100 | 64.42 | 63.52 | -0.90 | 3 | reproduced | reproduced |
| R2b | housing | e5-small | R@1000 | 81.63 | 81.19 | -0.44 | 3 | reproduced | reproduced |
| R2c | housing | e5-base | R@10 | 45.75 | 45.92 | +0.17 | 2 | reproduced | partly reproduced (on sampled states) |
| R2c | housing | e5-base | R@100 | 74.61 | 73.17 | -1.44 | 3 | reproduced | partly reproduced (on sampled states) |
| R2c | housing | e5-base | R@1000 | 86.65 | 89.72 | +3.07 | 3 | partly reproduced | partly reproduced (on sampled states) |
| R2d | housing | e5-large | R@10 | 50.58 | pending | pending | 2 | pending | pending |
| R2d | housing | e5-large | R@100 | 78.83 | pending | pending | 3 | pending | pending |
| R2d | housing | e5-large | R@1000 | 87.73 | pending | pending | 3 | pending | pending |

Values for comparison only. No verdict depends on them. `hit@1` and `mrr@10` count the first gold
passage. `all@k` means that every gold statute was found, the paper's lower bound on housing.

| Target | Metric | Published | Ours | Difference |
|---|---|---:|---:|---:|
| R1a | hit@1 | 0.25 | 0.25 | +0.00 |
| R1a | mrr@10 | 0.37 | 0.37 | -0.00 |
| R1b | hit@1 | 0.08 | 0.00 | -0.08 |
| R1b | mrr@10 | 0.18 | 0.21 | +0.03 |
| R1c | hit@1 | 0.25 | 0.00 | -0.25 |
| R1c | mrr@10 | 0.39 | 0.20 | -0.19 |
| R2a | hit@1 | 14.72 | 13.77 | -0.95 |
| R2a | mrr@10 | 21.99 | 20.46 | -1.53 |
| R2a | all@10 | 18.31 | 15.99 | -2.32 |
| R2a | all@100 | 39.89 | 36.17 | -3.72 |
| R2a | all@1000 | 59.68 | 55.54 | -4.14 |
| R2b | hit@1 | 8.97 | 9.12 | +0.15 |
| R2b | mrr@10 | 15.95 | 16.16 | +0.21 |
| R2b | all@10 | 13.32 | 13.57 | +0.25 |
| R2b | all@100 | 37.57 | 37.33 | -0.24 |
| R2b | all@1000 | 66.32 | 65.97 | -0.35 |
| R2c | hit@1 | 13.56 | 15.56 | +2.00 |
| R2c | mrr@10 | 22.38 | 24.04 | +1.66 |
| R2c | all@10 | 20.30 | 19.58 | -0.72 |
| R2c | all@100 | 51.61 | 50.49 | -1.12 |
| R2c | all@1000 | 75.53 | 81.41 | +5.88 |

Diagnostics. These runs use settings that the preregistration did not fix. They change no verdict.

| Target | Run | Tokenizer | R@10 | R@100 | R@1000 | Comparison-only metrics |
|---|---|---|---:|---:|---:|---|
| R1a | `062d8d251c0b1d7c` | porter | 0.75 | 2.34 | 8.45 | hit@1 0.25, mrr@10 0.36 |
| R2a | `65cb3b18226d7b1c` | porter | 40.73 | 62.51 | 76.27 | hit@1 15.13, mrr@10 22.31, all@10 18.14, all@100 40.00, all@1000 59.71 |

Runs on the sampled states of Amendment 2.

| Run | Retriever | States | R@10 | R@100 | R@1000 |
|---|---|---|---:|---:|---:|
| `4562ca7de9977b74` | bm25 | connecticut, delaware, idaho, kansas, louisiana, new jersey, oregon, rhode island, washington, wyoming | 40.07 | 63.10 | 79.15 |
| `bd95d37a2633a73f` | e5-small | connecticut, delaware, idaho, kansas, louisiana, new jersey, oregon, rhode island, washington, wyoming | 33.17 | 64.37 | 85.85 |
| `0643777ad54eeabb` | e5-base | connecticut, delaware, idaho, kansas, louisiana, new jersey, oregon, rhode island, washington, wyoming | 45.92 | 73.17 | 89.72 |

Reader targets. Accuracy in percent, with limits of 3 and 5 points.

| Target | Dataset | Published | Ours | Difference | Questions | Verdict | Note |
|---|---|---:|---:|---:|---:|---|---|
| R3a | housing | 58.81 | 66.00 | +7.19 | 2000 | diverged | On the sample of 2,000 questions from Amendment 2. Weights are 4-bit. The prompt is ours. |
| R3b | housing | 75.27 | 72.40 | -2.87 | 2000 | reproduced | On the sample of 2,000 questions from Amendment 2. Weights are 4-bit. The prompt is ours. |
| R3c | housing | 68.22 | 68.15 | -0.07 | 2000 | reproduced | On the sample of 2,000 questions from Amendment 2. Weights are 4-bit. The prompt is ours. |
| R4 closed | mbe | 37.84 | 45.10 | +7.26 | 1071 | comparison only | Comparison only, with no verdict. The published set includes private questions. |
| R4 gold | mbe | 57.38 | 56.96 | -0.42 | 1071 | comparison only | Comparison only, with no verdict. The published set includes private questions. |
<!-- AUTO:END -->

## What the paper says, and what we assumed

The paper does not state every setting. Each row below says which setting we chose and why. We fixed these choices before the first real run.

| Setting | Our choice | Basis |
|---|---|---|
| Questions on `mbe` | All 1,195 public questions | Table 22 reports the Historical MBE subset separately. The paper's aggregate tables also include private questions that we do not have |
| Query on `mbe` | `prompt` and `question`, joined by a space, with no answer choices | The paper never states this in words. Its examples of a query (Tables 7 and 15) show the facts and the question stem without options |
| Query on `housing` | The `question` field alone | Table 8 shows the query with the jurisdiction in a separate row. The dataset card's sentence with the state name is not used |
| Passage on `housing` | The `text` field alone, with no citation or path | Table 8 shows statute text only |
| Pool on `housing` | Statutes of the question's jurisdiction | Section 5.2 of the paper says this. Our 51 pools run from 10,676 to 155,974 statutes, the range that the paper gives |
| Gold on `housing` | The distinct `statute_idx` values of a question | The paper says that a question has at most 10 gold passages. Some question records list up to 15 entries, but they never hold more than 10 distinct statutes |
| Recall on `housing` | At least one gold statute found, the upper bound. Every gold statute found, the lower bound | Section 5.2 and Tables 24 and 25 |
| Text of question `mbe_1121` | The text in `qa.csv` | `validation.csv` has an empty `question` for this row |

## Known protocol differences

- **BM25 tokenizer.** The preregistered tokenizer is lowercase word tokens, with no stemming or stopwords. The paper does not name its BM25 tool or its tokenizer.
- **BM25 parameters.** We use k1 = 0.9 and b = 0.4, as the preregistration fixes them. The paper does not state its values.
- **Repeated query words.** A word that appears twice in a query counts twice. We understand that Lucene's bag-of-words queries do the same, but we did not test this.
- **Ties.** Equal scores are broken by a fixed random order, because the pool file lists the gold passages first and file order would favour them.
- **E5 settings.** We truncate at 512 tokens, as the model configuration sets. The paper does not state its truncation length. We store vectors as float16 to save disk space.
- **E5-mistral-7b.** This model is out of scope, as the preregistration explains, so we have no result for it.

## Divergences

### R2a: BM25 on housing is "partly reproduced"

Our R@10 and R@100 are about 3 points below the published values. R@1000 is within its limit.

**Most likely cause: the tokenizer.** We think that the paper used stemming and stopword removal, as Lucene's English analyzer does.

**Test that we ran.** We reran BM25 with the diagnostic tokenizer `porter`. It lowercases text, drops possessives, removes Lucene's English stopwords and applies the Porter stemmer. Nothing else changed: the parameters, query and pool are the same. The diagnostics table shows run `65cb3b18226d7b1c`. Its results are within 0.2 points of the published value at R@10, R@100 and R@1000, and on the lower bound at the same three depths. It differs by 0.41 points on `hit@1` and by 0.32 points on `mrr@10`. This supports the cause, but it does not prove it, because we did not run Lucene itself.

The verdict stays "partly reproduced", because the preregistered tokenizer decides it. The `porter` run is a diagnostic.

**A consequence for later work.** The preregistered `bm25` is weaker on housing than the paper's BM25. Any later comparison against `bm25` on housing should keep this in mind.

### R3a: `llama8` closed book on housing has "diverged"

Our accuracy is 66.00 on the sample of 2,000 questions. The paper reports 58.81. Our number is higher.

**Checks that need no model, post hoc.** They use only the stored closed-book run `0a3bd283a1dd357b`.

- The model puts a mean of 0.94 of its next-token probability on the two labels. Only 1 of 2,000 questions has less than 0.5. So the model almost always starts with "Yes" or "No", and an unparsed answer cannot explain the gap.
- The model answers "Yes" on 36.4% of questions, and 35.8% of the gold answers are "Yes". If we lower the bar for "Yes", accuracy falls slowly: it is 61.45 when the model answers "Yes" on 54.5% of questions. A bias toward "Yes" alone would have to be large to reach 58.81.

**Most likely cause: the answer labels.** The paper takes "the maximum likelihood prediction over the answer choice letters" and names Y and N for this dataset (its section 5.4). We score the words "Yes" and "No". In the Llama 3 tokenizer, "Y" and "N" are different tokens from "Yes" and "No", so the two methods can pick different answers.

**Test, written before it runs.** Two diagnostic runs of `llama8`, closed book, on the same 2,000 questions. Nothing else changes.

| Answer form | The prompt asks for | Scored labels |
|---|---|---|
| `yes-no-scored-y-n` | "Yes" or "No" (our prompt) | Y and N |
| `y-n` | "Y" or "N" | Y and N |

Decision rule: the cause is supported if at least one of the two runs is within 3 points of 58.81, the limit for "reproduced". It is partly supported if a run moves at least 3 points from 66.00 toward 58.81 but stays further than 3 points away. Otherwise it is not supported, and we say that the cause is still unknown. Either way, the R3a verdict stays "diverged", because the preregistered form decides it. Other possible causes are not tested here: 4-bit weights, the chat template, and the prompt wording. The paper does not give its prompt.

**Result.** Both runs are in the suite `us_diagnostics`. All three runs use the same 2,000 questions.

| Answer form | Run | Accuracy | Distance to 58.81 | Says "Yes" or "Y" | Mean probability on the two labels |
|---|---|---:|---:|---:|---:|
| `yes-no` (preregistered) | `0a3bd283a1dd357b` | 66.00 | 7.19 | 36.4% | 0.94 |
| `yes-no-scored-y-n` | `3270c3032dcc33a7` | 61.95 | 3.14 | 50.8% | 0.0000037 |
| `y-n` | `375991b9ed5aead2` | 65.15 | 6.34 | 40.5% | 0.9995 |

By the rule above, the cause is **partly supported**. The run `yes-no-scored-y-n` moved 4.05 points toward 58.81, which is more than 3. It is still 3.14 points away, which is just outside the limit. The run `y-n` moved only 0.85 points.

Post hoc, we noticed what explains the first run. When the prompt asks for "Yes" or "No", the model puts almost no probability on the tokens Y and N: the mean is 0.0000037. So the choice between Y and N comes from two tiny probabilities that carry little information, and the model says "Y" on about half of the questions. If the paper asked for "Yes" or "No" but scored Y and N, its accuracy would be lower than ours in this way. This is a possibility. The paper does not give its prompt, so we cannot confirm it.

When the prompt asks for "Y" or "N", the model puts almost all its probability on them, and accuracy is close to our preregistered run. So scoring letters is not a problem by itself. The mismatch between the request and the scored labels is the part that lowers accuracy.

The causes that we did not test remain open: 4-bit weights, the chat template and the prompt wording. The run `375991b9ed5aead2` records a modified working tree. The only modified path is the result file of the first run, which the queue wrote before the second run began. No code changed between the two runs.

### R1a: BM25 on mbe is "reproduced", so it is not a divergence

We list it here because the same diagnostic also ran on this dataset. The diagnostic on `mbe` is run `062d8d251c0b1d7c`. Both tokenizers are within the limits. On this dataset the counts are so small that the two cannot be told apart: 0.08 points at R@10 is one question out of 1,195.

## Data findings that affect these numbers

The full counts are in `results/data_audit/us_audit.json`.

- All 1,195 gold passages are in the pool, and all have the source `mbe`. So the `doctrine`, `cases` and `real` libraries contain no labelled gold passage, apart from one gold text that is also identical to a case law passage. Gold recall cannot measure those libraries.
- One row, `mbe_1355`, has its gold passage in the `source` field. We keep the row and tag its source as malformed. Its query and gold label are not affected.
- 41 gold passages serve more than one question, and 87 questions use them.
- Three jurisdictions have statutes but no questions: Minnesota, Pennsylvania and the US Virgin Islands.
