"""The agent's tools. One run loads one library, so search ignores the library name it gets."""

import re

from open_book_law.reader import samples
from open_book_law.retrieval import bm25, dense
from open_book_law.runlog import model_pin
from open_book_law.us import barexam, goodlaw
from open_book_law.us.authority import status

TOP = 3


def make_tools(docids, texts, find, conn):
    """The three tools as plain functions. `find` maps a query to positions in `docids`."""
    position_of = {docid: i for i, docid in enumerate(docids)}

    def describe(docid):
        case_id = goodlaw.case_of(docid)
        found = conn.execute("SELECT name, date, cite FROM cases WHERE id = ?", (case_id,)).fetchone()
        name, date, cite = found or (None, None, None)
        snippet = " ".join(texts[position_of[docid]].split()[:40])
        details = {"case": name, "year": date and date[:4], "citation": cite or case_id}
        return {"passage_id": docid, **details, "snippet": snippet}

    def search(query: str, library: str) -> dict:
        """Return the top 3 passages, each with its id, case name, year, citation and a short snippet."""
        return {"results": [describe(docids[int(i)]) for i in find(query)]}

    def read(passage_id: str) -> dict:
        """Return the text of one passage."""
        if passage_id not in position_of:
            return {"error": "unknown passage_id"}
        return {"text": " ".join(texts[position_of[passage_id]].split()[:400])}

    def check_status(citation: str, as_of_date: str) -> dict:
        """Say whether a decision had been overruled on a date, and by which decision."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of_date):
            return {"error": "as_of_date must look like YYYY-MM-DD"}
        return status(conn, citation, as_of_date)

    return {"search": search, "read": read, "check_status": check_status}


def open_tools(library, retriever):
    """Load a library, which takes minutes on the large ones, and return its tools."""
    rows = samples.iter_passages("scotus") if library == "scotus" else barexam.iter_pool(library)
    docids, texts = zip(*((row["idx"], row["text"]) for row in rows), strict=True)
    if retriever == "bm25":
        index = bm25.build_index(texts)
        find = lambda query: bm25.search(index, query, k=TOP)[0]  # noqa: E731
    else:
        model_id = dense.MODELS[retriever]
        encoder = dense.load_model(model_id, model_pin(model_id)["revision"])
        store = dense.load_store(dense.store_dir(retriever), "scotus" if library == "scotus" else "mbe")
        rows = dense.rows_for_texts(texts, store[1])
        find = lambda query: dense.search_store(dense.encode_queries(*encoder, [query]), store[0], rows, k=TOP)[0][0]  # noqa: E501, E731
    return make_tools(docids, texts, find, goodlaw.connect())
