"""Write and read immutable run files: results/runs/<suite>/<run_id>.json and their rankings.

Amendment 2: the top 100 of a ranking stays in git, next to the run file. The top 1000 goes to the data
folder. Rank files in git from before that rule hold the top 1000, so readers take the deepest file.
"""

import csv
import datetime
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path

from open_book_law.paths import DATA_ROOT, DERIVED_DIR, REPO_ROOT

RUNS_DIR = REPO_ROOT / "results" / "runs"
RANKS_DIR = DERIVED_DIR / "ranks"
GIT_RANK = 100
MAX_RANK = 1000


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 24):
            digest.update(block)
    return digest.hexdigest()


def portable(path):
    """The path as run files store it: `$OBL_DATA/...` for data, relative for the repository.

    The data root is tried as given and with links resolved, because `data_local` may be a link.
    """
    path = Path(path)
    for root, prefix in ((DATA_ROOT, "$OBL_DATA/"), (DATA_ROOT.resolve(), "$OBL_DATA/"), (REPO_ROOT, "")):
        if path.is_relative_to(root):
            return prefix + path.relative_to(root).as_posix()
    return str(path)


def run_id(config):
    text = json.dumps(config, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def model_pin(model_id):
    """The pinned revision and download patterns of a model."""
    with open(REPO_ROOT / "data" / "model_revisions.json", encoding="utf-8") as f:
        return json.load(f)[model_id]


def git_state():
    def git(*args):
        done = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return done.stdout

    dirty_paths = [line[3:] for line in git("status", "--porcelain").splitlines()]
    commit = git("rev-parse", "HEAD").strip()
    return {"commit": commit, "dirty": bool(dirty_paths), "dirty_paths": dirty_paths}


def deep_rank_path(rid, runs_dir):
    ranks_dir = Path(runs_dir) / "ranks" if runs_dir else RANKS_DIR
    return ranks_dir / f"{rid}.tsv.gz"


def write_run(
    suite,
    config,
    data_files,
    model,
    metrics,
    per_query,
    elapsed_seconds,
    throughput,
    rankings=None,
    runs_dir=None,
):
    """Write the run file and return its path. Mode "x" refuses to overwrite an existing file.

    `rankings` maps qid to a list of docids, best first. `per_query` is a list of dicts.
    Neither may hold question or passage text.
    """
    out_dir = Path(runs_dir or RUNS_DIR) / suite
    out_dir.mkdir(parents=True, exist_ok=True)
    rid = run_id(config)
    path = out_dir / f"{rid}.json"
    record = {
        "run_id": rid,
        "suite": suite,
        "git": git_state(),
        "utc_time": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "data_sha256": {portable(p): sha256_file(p) for p in data_files},
        "model": model,
        "config": config,
        "metrics": metrics,
        "elapsed_seconds": elapsed_seconds,
        "throughput": throughput,
        "per_query": per_query,
    }
    text = json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False)
    if path.exists():
        raise FileExistsError(f"{path} exists. Run files are append-only: change --rerun to write a new one.")
    if rankings is not None:
        deep_path = deep_rank_path(rid, runs_dir)
        deep_path.parent.mkdir(parents=True, exist_ok=True)
        write_rank_file(deep_path, rankings, MAX_RANK)
        write_rank_file(out_dir / f"{rid}.rank.tsv.gz", rankings, GIT_RANK)
    with open(path, "x", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


def write_rank_file(path, rankings, depth):
    with open(path, "xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(b"qid\tdocid\trank\n")
        for qid, docids in rankings.items():
            lines = [f"{qid}\t{d}\t{i + 1}\n" for i, d in enumerate(docids[:depth])]
            gz.write("".join(lines).encode())


def find_run(rid, runs_dir=None):
    """Path of a run file, in whichever suite holds it."""
    return next(Path(runs_dir or RUNS_DIR).glob(f"*/{rid}.json"))


def read_rankings(rid, runs_dir=None):
    """Return (dict from qid to docids best first, depth of the deepest ranking), from the deepest file.

    A query that matched nothing has no row in the rank file. The run file still lists the question, so it
    gets an empty ranking here. A question that the run file does not list is missing, and stays missing.
    """
    deep_path = deep_rank_path(rid, runs_dir)
    run_path = find_run(rid, runs_dir)
    path = deep_path if deep_path.exists() else run_path.with_suffix(".rank.tsv.gz")
    rankings = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            rankings.setdefault(row["qid"], []).append(row["docid"])
    with open(run_path, encoding="utf-8") as f:
        for record in json.load(f)["per_query"]:
            rankings.setdefault(record["qid"], [])
    return rankings, max(map(len, rankings.values()), default=0)


def require_questions(questions, rankings, rid):
    """Stop if a ranking run lacks a question. Dropping it silently would change the result."""
    missing = [q["qid"] for q in questions if q["qid"] not in rankings]
    if missing:
        raise SystemExit(f"ranking run {rid} lacks {len(missing)} questions, such as {missing[:3]}")


def load_runs(suite, runs_dir=None):
    """Every run of a suite, earliest first, so that a rerun cannot replace an earlier result."""
    runs = []
    for path in sorted((Path(runs_dir or RUNS_DIR) / suite).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            runs.append(json.load(f))
    return sorted(runs, key=lambda run: (run["utc_time"], run["run_id"]))


def first_match(runs, **settings):
    """The first run whose config has all these settings, or None."""
    for run in runs:
        if all(run["config"].get(key) == value for key, value in settings.items()):
            return run
    return None


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1, sort_keys=True)
        f.write("\n")


def read_partial(path):
    """Records of a stopped run. A last line that a crash cut short is removed, so its question runs again."""
    records = {}
    if path.exists():
        with open(path, "rb+") as f:
            data = f.read()
            if data and not data.endswith(b"\n"):
                f.truncate(data.rfind(b"\n") + 1)
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                records[record["qid"]] = record
    return records


def append_record(file, record):
    """Add one line and force it to the disk, because this drive can drop off the bus."""
    file.write(json.dumps(record, ensure_ascii=False) + "\n")
    file.flush()
    os.fsync(file.fileno())
