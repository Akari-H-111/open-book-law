"""Reader and rollout prompts. A change of wording needs a new PROMPT_VERSION, which each run file records.

Rollout prompts are the "Structured Reasoning" rows of Tables 13 and 14 in Zheng et al. 2025.
"""

# v1 left the cue in the user turn, and Qwen3 repeated it. In v2, Qwen3 opened its answer with Markdown bold.
PROMPT_VERSION = "v3"
ANSWER_OPENING = {"qwen3": " **"}
CONTEXT_TOKENS = 2000
LABELS = {"mbe": ("A", "B", "C", "D"), "scotus": ("A", "B", "C", "D"), "housing": ("Yes", "No")}
# Housing answer forms: (the labels that the prompt asks for, the labels that are scored). Only "yes-no" is
# preregistered. The others are diagnostics for R3a, because the paper scored "Y" and "N" (its section 5.4).
HOUSING_FORMS = {
    "yes-no": (("Yes", "No"), ("Yes", "No")),
    "yes-no-scored-y-n": (("Yes", "No"), ("Y", "N")),
    "y-n": (("Y", "N"), ("Y", "N")),
}
ROLLOUT_MBE = (
    "Given a set of facts about a legal scenario in “Question:”, identify the key legal issue that arises "
    "from the facts and provide the applicable legal rule in “Rule:”."
)
ROLLOUT_HOUSING = (
    "Consider the housing statute for {jurisdiction} in the year 2021. The question given in “Question:” is "
    "a legal question about housing and eviction law in {jurisdiction}. Provide the applicable legal rule in "
    "“Rule:”. If you do not know the state law, provide governing rules that address the question under "
    "typical eviction law."
)


def labels(dataset, form="yes-no"):
    return HOUSING_FORMS[form][1] if dataset == "housing" else LABELS[dataset]


def gold_label(dataset, question, form="yes-no"):
    if dataset == "mbe":
        return question["answer"].strip().upper()
    gold = question["answer"].strip()
    if dataset == "housing":
        return dict(zip(LABELS["housing"], labels(dataset, form), strict=True))[gold]
    return gold


def question_text(dataset, question, form="yes-no"):
    """The closed-book prompt. The housing wording is the one that the dataset card suggests."""
    if dataset == "housing":
        yes, no = HOUSING_FORMS[form][0]
        return (
            f"Consider statutory law for {question['state']} in the year 2021. {question['question'].strip()}"
            f'\n\nAnswer "{yes}" or "{no}".\nAnswer:'
        )
    options = "\n".join(f"{letter}. {question[f'choice_{letter.lower()}'].strip()}" for letter in "ABCD")
    return (
        f"{question['query']}\n\n{options}\n\n"
        'Choose the best answer. Answer with one letter: "A", "B", "C" or "D".\nAnswer:'
    )


def with_context(dataset, question, context, form="yes-no"):
    source = "statutes" if dataset == "housing" else "legal passages"
    return (
        f"Read these {source}. They may help with the question that follows.\n\n{context}\n\n"
        f"Question:\n{question_text(dataset, question, form)}"
    )


def rollout_text(dataset, question):
    if dataset == "mbe":
        instruction = ROLLOUT_MBE
    else:
        instruction = ROLLOUT_HOUSING.format(jurisdiction=question["state"])
    return f"{instruction}\n\nQuestion: {question['query']}\nRule:"


def truncate_context(tokenizer, passages, budget=CONTEXT_TOKENS):
    """Join passages in rank order and keep the first `budget` tokens. Returns (context, whether cut)."""
    context = "\n\n".join(passages)
    ids = tokenizer.encode(context, add_special_tokens=False)
    if len(ids) <= budget:
        return context, False
    return tokenizer.decode(ids[:budget]), True


def prompt_ids(tokenizer, text, reader):
    """Token ids of the prompt. The last line, the cue "Answer:" or "Rule:", opens the assistant's turn.

    So the next token is the answer itself. Qwen3 gets an empty thinking block and its bold opening for the
    same reason.
    """
    if not tokenizer.chat_template:
        return tokenizer.encode(text)
    body, _, cue = text.rpartition("\n")
    if cue == "Answer:":
        cue += ANSWER_OPENING.get(reader, "")
    extra = {"enable_thinking": False} if reader == "qwen3" else {}
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": body.rstrip()}], tokenize=False, add_generation_prompt=True, **extra
    )
    return tokenizer.encode(rendered + cue, add_special_tokens=False)
