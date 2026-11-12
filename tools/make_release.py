"""Build the release files in dist/: the site, a full snapshot of the repository, and SHA256SUMS.

Run from the repository root:  python3 -I tools/make_release.py v1.0.0 [--verify]

The files come from git's stored objects for HEAD, not from the working tree. So line-ending settings and
local edits cannot change them. The zip files store their contents without compression and with fixed
dates, sorted names and the file modes recorded in git. Anyone who runs this script on the same commit
gets the same bytes and the same checksums.

Before it writes anything, the script checks that:
  - if the tag already exists, it points to HEAD;
  - no tracked file has local changes;
  - tools/build_site_data.py writes exactly the committed site/data.js;
  - no committed file contains a local machine path, including temporary folders;
  - with --verify, the summary scripts rewrite every summary and results table without a change. This
    step needs NumPy.
Uses only the standard library.
"""

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
STAMP = (1980, 1, 1, 0, 0, 0)
SUMMARY_SCRIPTS = ["us_answers", "us_verdicts", "us_select", "us_hypotheses"]
CHECKED = ["results/summary", "docs/REPRODUCTION.md", "docs/RESULTS.md", "site/data.js"]
LOCAL_PATH = re.compile(rb"/(Users|Volumes)/\w|/private/(tmp|var/folders)/\w|-(Users|Volumes)-\w")


def git(*args, data=None):
    return subprocess.run(["git", *args], cwd=REPO, input=data, capture_output=True, check=True).stdout


def fail(message):
    sys.exit(f"stopped: {message}")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def committed_files(commit):
    """Map each path in the commit to (mode, content), read from git's objects."""
    files = {}
    for entry in git("ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, obj = meta.decode().split()
        if kind != "blob" or mode not in ("100644", "100755"):
            fail(f"{path.decode()} is not a plain file (mode {mode})")
        files[path.decode()] = (mode, git("cat-file", "blob", obj))
    return files


def site_files(files):
    """Every committed file under site/, at the top of the zip, plus the license."""
    entries = {path.removeprefix("site/"): entry for path, entry in files.items() if path.startswith("site/")}
    return entries | {"LICENSE": files["LICENSE"]}


def check_tag(version, commit):
    found = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{version}^{{commit}}"],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    if found and found != commit:
        fail(f"tag {version} points to {found}, not to HEAD {commit}")
    return bool(found)


def check_tree(files):
    if git("status", "--porcelain", "--untracked-files=no").strip():
        fail("the working tree has local changes. Commit or remove them first.")
    subprocess.run([sys.executable, "-I", "tools/build_site_data.py"], cwd=REPO, check=True)
    if (REPO / "site" / "data.js").read_bytes() != files["site/data.js"][1]:
        fail("tools/build_site_data.py writes a different site/data.js. Rebuild and commit it.")
    found = [path for path, (_, data) in files.items() if LOCAL_PATH.search(data)]
    if found:
        fail("local machine paths in: " + ", ".join(found))


def verify_summaries():
    for name in SUMMARY_SCRIPTS:
        subprocess.run([sys.executable, "-m", f"open_book_law.experiments.{name}"], cwd=REPO, check=True,
                       stdout=subprocess.DEVNULL)
    if git("status", "--porcelain", "--untracked-files=no", "--", *CHECKED).strip():
        fail("a summary changed when the scripts ran again. See git diff.")


def write_zip(path, prefix, entries):
    """A zip with stored entries, fixed metadata, sorted names, and a MANIFEST.sha256 of its files.

    `entries` maps the name inside the zip to (git mode, content).
    """
    lines = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for name, (mode, data) in sorted(entries.items()):
            lines.append(f"{sha256(data)}  {name}")
            add(z, f"{prefix}/{name}", data, 0o755 if mode == "100755" else 0o644)
        add(z, f"{prefix}/MANIFEST.sha256", ("\n".join(lines) + "\n").encode(), 0o644)


def add(z, name, data, permissions):
    info = zipfile.ZipInfo(name, STAMP)
    info.create_system = 3
    info.external_attr = (0o100000 | permissions) << 16
    z.writestr(info, data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="for example v1.0.0")
    parser.add_argument("--verify", action="store_true", help="also rerun the summary scripts")
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
        fail("the version must look like v1.0.0")
    commit = git("rev-parse", "HEAD").decode().strip()
    tagged = check_tag(args.version, commit)
    files = committed_files(commit)
    check_tree(files)
    if args.verify:
        verify_summaries()
    assets = {
        f"open-book-site-{args.version}.zip": (f"open-book-site-{args.version}", site_files(files)),
        f"open-book-full-{args.version}.zip": (f"open-book-{args.version}", files),
    }
    DIST.mkdir(exist_ok=True)
    sums = []
    for name, (prefix, entries) in assets.items():
        write_zip(DIST / name, prefix, entries)
        sums.append(f"{sha256((DIST / name).read_bytes())}  {name}")
    (DIST / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"commit {commit}")
    print((DIST / "SHA256SUMS").read_text(encoding="utf-8"), end="")
    print(f"tag {args.version}: " + ("points to HEAD" if tagged else "not created yet"))


if __name__ == "__main__":
    main()
