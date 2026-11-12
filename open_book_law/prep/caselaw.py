"""Download the U.S. Reports volumes of the Caselaw Access Project and read cases straight from the zips."""

import gzip
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
import zipfile
from collections import Counter

from open_book_law.paths import DATA_ROOT, DERIVED_DIR
from open_book_law.prep.citations import normalize
from open_book_law.prep.overruled import (
    PAIRS_JSONL,
    parse_table,
    resolve_pair,
    table_path,
    update_audit,
    write_jsonl,
)
from open_book_law.us.authority import build_file

CAP_DIR = DATA_ROOT / "cap_us"
CORNELL_DIR = DATA_ROOT / "cornell_scotus"
CASES_GZ = DERIVED_DIR / "scotus_cases.jsonl.gz"
EXTRA_GZ = DERIVED_DIR / "scotus_cases_extra.jsonl.gz"
PASSAGES_GZ = DERIVED_DIR / "scotus_passages.jsonl.gz"
BASE = "https://static.case.law/us"
CORNELL_BASE = "https://www.law.cornell.edu/supremecourt/text"
CORNELL_TYPES = {"OPINION": "majority", "CONCUR": "concurrence", "DISSENT": "dissent"}
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
# The table gives no docket for these two. I checked each page's title against the table's name.
DOCKET_FOR_CITE = {"597 U.S. 215": "19-1392", "603 U.S. 369": "22-451"}
PASSAGE_WORDS = 150
UA = "open-book-law research (python urllib)"
SLEEP = 0.6
RETRIES = 4
RETRY_WAIT = 20


def fetch(url):
    """Fetch one URL after the polite delay, and retry on network errors."""
    for attempt in range(RETRIES):
        time.sleep(SLEEP + RETRY_WAIT * attempt)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except OSError:
            if attempt == RETRIES - 1:
                raise


def read_manifest(directory):
    path = directory / "manifest.jsonl"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return {row["url"]: row for row in rows}


def store(directory, name, url, body):
    """Write one file by renaming a finished copy, and then record it in the manifest."""
    part = directory / f"{name}.part"
    part.write_bytes(body)
    part.rename(directory / name)
    row = {"url": url, "file": name, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
    with open(directory / "manifest.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def download_volumes():
    """Resumable: a URL that the manifest lists is not requested again."""
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    done = read_manifest(CAP_DIR)
    url = f"{BASE}/VolumesMetadata.json"
    if url not in done:
        store(CAP_DIR, "VolumesMetadata.json", url, fetch(url))
    volumes = json.loads((CAP_DIR / "VolumesMetadata.json").read_text(encoding="utf-8"))
    for volume in sorted(v["volume_folder"] for v in volumes):
        url = f"{BASE}/{volume}.zip"
        if url not in done:
            store(CAP_DIR, f"{volume}.zip", url, fetch(url))
            print(volume, flush=True)


def official_cite(citations):
    for citation in citations:
        if citation["type"] == "official":
            return normalize(citation["cite"])
    return None


def case_from_json(record):
    """Keep the fields that this project uses from one CAP case file."""
    body = record["casebody"]
    return {
        "id": str(record["id"]),
        "name": record["name_abbreviation"],
        "date": record["decision_date"],
        "cite": official_cite(record["citations"]),
        "docket": record.get("docket_number") or None,
        "head_matter": body.get("head_matter") or "",
        "opinions": [
            {"type": o.get("type") or "unknown", "author": o.get("author"), "text": o.get("text") or ""}
            for o in body.get("opinions") or []
        ],
        "cites_to": [
            {
                "cite": c.get("cite"),
                "reporter": c.get("reporter"),
                "opinion_index": c.get("opinion_index"),
                "case_ids": [str(i) for i in c.get("case_ids") or []],
                "paths": c.get("case_paths") or [],
            }
            for c in record.get("cites_to") or []
        ],
        "source": "cap",
    }


def iter_zip_cases(path):
    """Read every case file of one volume from inside its zip. Nothing is unpacked to disk."""
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith("json/") and name.endswith(".json"):
                yield case_from_json(json.loads(archive.read(name)))


def iter_cases(path=None):
    """Stream cases from the built gzip file."""
    with gzip.open(path or CASES_GZ, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def all_cases():
    yield from iter_cases(CASES_GZ)
    if EXTRA_GZ.exists():
        yield from iter_cases(EXTRA_GZ)


def word_count(case):
    return sum(len(o["text"].split()) for o in case["opinions"])


def merge_paragraphs(text, target_words):
    merged, current, words = [], [], 0
    for paragraph in text.split("\n"):
        size = len(paragraph.split())
        if size:
            if current and words + size > target_words:
                merged.append("\n".join(current))
                current, words = [], 0
            current.append(paragraph)
            words += size
    if current:
        merged.append("\n".join(current))
    return merged


def split_passages(case, target_words=PASSAGE_WORDS):
    """Merge paragraphs of each opinion up to the target. A longer paragraph stays whole."""
    passages = []
    for index, opinion in enumerate(case["opinions"]):
        for position, text in enumerate(merge_paragraphs(opinion["text"], target_words)):
            passages.append(
                {
                    "id": f"{case['id']}:{index}:{position}",
                    "case_id": case["id"],
                    "opinion_index": index,
                    "opinion_type": opinion["type"],
                    "position": position,
                    "text": text,
                }
            )
    return passages


def write_gzip_jsonl(path, rows):
    """Write through a temporary name, so that a dropped drive cannot leave a short file."""
    part = path.with_name(path.name + ".part")
    with open(part, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode())
    part.rename(path)


def build_cases():
    """Volume zips go in numeric order, so that the output does not depend on the directory listing."""
    zips = sorted(CAP_DIR.glob("*.zip"), key=lambda p: int(p.stem))
    write_gzip_jsonl(CASES_GZ, (case for path in zips for case in iter_zip_cases(path)))


def strip_tags(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ").strip()


def paragraphs_from_html(fragment):
    """Paragraph text of one opinion. Court nameplates and rules are layout, so they are left out."""
    kept = []
    for attributes, body in re.findall(r"<p\b([^>]*)>(.*?)</p>", fragment, re.S):
        if not re.search(r"scusnameplate|noticeopinions|\brule\b|notice ", attributes):
            text = strip_tags(body)
            if text:
                kept.append(text)
    return kept


def parse_long_date(text):
    """'June 24, 2022' or 'Apr. 20, 2020' to '2022-06-24'."""
    month, day, year = re.fullmatch(r"([A-Z][a-z]+)\.? (\d+), (\d{4})", text).groups()
    return f"{year}-{MONTHS[month[:3]]:02d}-{int(day):02d}"


def case_from_cornell(page, docket, cite):
    """Parse one Cornell LII page. Sections start at anchors like writing-19-1392_OPINION_4.

    Return None if the page does not have that layout, because the caller must list the decision as missing.
    """
    marks = list(re.finditer(rf'id="writing-{re.escape(docket)}_([A-Z]+)(?:_\d+)?"', page))
    if not marks:
        return None
    head, opinions = "", []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else page.find('id="tab_default_2"')
        text = "\n".join(paragraphs_from_html(page[mark.start() : end]))
        if mark[1] == "SYLLABUS":
            head = text
        else:
            opinion_type = CORNELL_TYPES.get(mark[1], mark[1].lower())
            opinions.append({"type": opinion_type, "author": None, "text": text})
    title = re.search(r"<title>(.*?) \|", page, re.S)
    decided = re.search(r"Decided ([A-Z][a-z]+\.? \d+, \d{4})", page)
    name = " ".join(w.capitalize() for w in strip_tags(title[1]).split()).replace(" V. ", " v. ")
    return {
        "id": f"cornell:{docket}",
        "name": name,
        "date": parse_long_date(decided[1]),
        "cite": cite,
        "docket": docket,
        "head_matter": head,
        "opinions": opinions,
        "cites_to": [],
        "source": f"{CORNELL_BASE}/{docket}",
    }


def fetch_extra(wanted):
    """Fetch decisions that CAP lacks. `wanted` maps docket to citation or None. Return cases and failures."""
    CORNELL_DIR.mkdir(parents=True, exist_ok=True)
    done = read_manifest(CORNELL_DIR)
    cases, missing = [], []
    for docket, cite in sorted(wanted.items()):
        url, name = f"{CORNELL_BASE}/{docket}", f"{docket}.html"
        try:
            if url not in done:
                store(CORNELL_DIR, name, url, fetch(url))
        except OSError as error:
            missing.append({"docket": docket, "cite": cite, "reason": f"fetch failed: {error}"})
            continue
        page = (CORNELL_DIR / name).read_text(encoding="utf-8", errors="replace")
        case = case_from_cornell(page, docket, cite)
        if case is None or not word_count(case):
            reason = "page has no opinion sections that we can parse"
            missing.append({"docket": docket, "cite": cite, "reason": reason})
        else:
            cases.append(case)
    return cases, missing


def light_case(case):
    """The fields needed to match decisions and to build the graph, without the text."""
    ids = {i for cited in case["cites_to"] for i in cited["case_ids"]}
    return {k: case[k] for k in ("id", "cite", "name", "date", "docket")} | {
        "cites_to": [{"case_ids": sorted(ids)}],
        "cites_ids": frozenset(ids),
        "words": word_count(case),
    }


def make_index(cases):
    index = {"cases": {}, "by_cite": {}, "by_year": {}, "by_docket": {}}
    for case in cases:
        index["cases"][case["id"]] = case
        index["by_cite"].setdefault(case["cite"], []).append(case)
        if case["date"]:
            index["by_year"].setdefault(int(case["date"][:4]), []).append(case)
        if case["id"].startswith("cornell:"):
            index["by_docket"][case["docket"]] = case["id"]
    return index


def missing_decisions(pairs):
    """Dockets to fetch for overruling decisions that CAP lacks. Cited ones need `DOCKET_FOR_CITE`."""
    wanted = {}
    for pair in pairs:
        if pair["new_id"] is None and pair["new_docket"]:
            wanted[pair["new_docket"]] = None
        elif pair["new_id"] is None and pair["new_cite"] in DOCKET_FOR_CITE:
            wanted[DOCKET_FOR_CITE[pair["new_cite"]]] = pair["new_cite"]
    return wanted


def coverage(pairs, index):
    """Count the pairs that have text on both sides, and list where the table and the cases disagree."""
    cases = index["cases"]
    has_text = {i for i, case in cases.items() if case["words"]}
    both = [p for p in pairs if p["new_id"] in has_text and p["old_id"] in has_text]
    lacking, other_name, year_gaps, cite_gaps = [], [], [], []
    for p in pairs:
        for s in ("new", "old"):
            case_id, name, cite, year = (p[f"{s}_{field}"] for field in ("id", "name", "cite", "year"))
            found_by = p[f"{s}_found_by"]
            where = {"pair_id": p["pair_id"], "side": s}
            if case_id not in has_text:
                reason = found_by if not case_id else "case has no opinion text"
                lacking.append(where | {"name": name, "cite": cite, "year": year, "reason": reason})
            if found_by == "cite_other_name":
                other_name.append(where | {"table": name, "cap": cases[case_id]["name"]})
            if case_id and (cases[case_id]["date"] or "")[:4] != str(year):
                year_gaps.append(
                    where | {"name": name, "table_year": year, "case_date": cases[case_id]["date"]}
                )
            if cite and case_id and normalize(cite) != p[f"{s}_canonical"]:
                cite_gaps.append(where | {"table": cite, "case": p[f"{s}_canonical"]})
    found_by = Counter(p[f"{s}_found_by"] for p in pairs for s in ("new", "old"))
    return {
        "pairs": len(pairs),
        "pairs_with_both_texts": len(both),
        "pairs_with_both_texts_but_one_under_300_words": sum(
            min(cases[p["new_id"]]["words"], cases[p["old_id"]]["words"]) < 300 for p in both
        ),
        "pairs_lacking_a_text": len({row["pair_id"] for row in lacking}),
        "found_by": dict(sorted(found_by.items())),
        "decisions_lacking_text": lacking,
        "matched_by_citation_with_another_name": other_name,
        "table_year_differs_from_case_date": year_gaps,
        "table_cite_differs_from_case": cite_gaps,
    }


def write_passages(cases):
    """Write every passage and return totals. `cases` is a stream, so the text never all sits in memory."""
    totals = Counter()

    def rows():
        for case in cases:
            totals["cases"] += 1
            totals[f"cases_from_{'cap' if case['source'] == 'cap' else 'cornell'}"] += 1
            totals["cases_without_text"] += not word_count(case)
            for passage in split_passages(case):
                totals["passages"] += 1
                totals[f"passages_{passage['opinion_type']}"] += 1
                yield passage

    write_gzip_jsonl(PASSAGES_GZ, rows())
    return dict(sorted(totals.items()))


def link_table():
    """Match the table to the cases, fetch what CAP lacks, and write the pairs, passages and graph."""
    pairs = parse_table(table_path())[1]
    index = make_index(light_case(case) for case in iter_cases(CASES_GZ))
    first_pass = [resolve_pair(p, index) for p in pairs]
    extra, missing = fetch_extra(missing_decisions(first_pass))
    write_gzip_jsonl(EXTRA_GZ, extra)
    index = make_index(light_case(case) for case in all_cases())
    resolved = [resolve_pair(p, index) for p in pairs]
    write_jsonl(PAIRS_JSONL, resolved)
    report = coverage(resolved, index)
    update_audit("coverage", report | {"not_fetched": missing, "fetched": [c["id"] for c in extra]})
    update_audit("passages", write_passages(all_cases()))
    update_audit("graph", build_file(list(index["cases"].values()), resolved))
    print({k: v for k, v in report.items() if isinstance(v, int)})


def main(step):
    {"download": download_volumes, "build": build_cases, "link": link_table}[step]()


if __name__ == "__main__":
    main(sys.argv[1])
