#!/bin/zsh
# Run one implementation worker with the least permissions that its brief needs.
# Usage: tools/run_worker.sh <brief-name>   (reads docs/worker_briefs/<brief-name>.md)
set -u
cd "${0:A:h:h}" || exit 2
name=$1
V=$HOME/venvs/open-book-law/bin
DATA=${OBL_DATA:-$PWD/data_local}
DATA=${DATA:A}
claude -p "$(cat docs/worker_briefs/$name.md)" \
  --model "${WORKER_MODEL:-claude-opus-5-5}" --effort "${WORKER_EFFORT:-medium}" \
  --tools "Bash,Read,Edit,Write" \
  --permission-mode dontAsk --permission-prompts none --strict-mcp-config \
  --add-dir "$DATA" \
  --allowedTools "Read" "Edit" "Write" \
    "Bash($V/*)" "Bash(~/venvs/open-book-law/bin/*)" "Bash(make *)" \
    "Bash(git add *)" "Bash(git commit *)" "Bash(git status*)" "Bash(git diff*)" "Bash(git log*)" "Bash(git show*)" \
    "Bash(git rev-parse*)" "Bash(git -C $DATA/*)" \
    "Bash(pdftotext *)" "Bash(pdfinfo *)" "Bash(pdftoppm *)" "Bash(ls *)" "Bash(cat *)" "Bash(head *)" "Bash(tail *)" \
    "Bash(sed -n *)" "Bash(grep *)" "Bash(wc *)" "Bash(find *)" "Bash(mkdir *)" "Bash(sort *)" "Bash(awk *)" "Bash(du *)" "Bash(cut *)" "Bash(uniq *)" \
  --disallowedTools "WebFetch" "WebSearch" "Bash(git push*)" "Bash(git remote*)" "Bash(curl*)" "Bash(wget*)" "Bash(sudo*)" "Bash(rm *)" \
  --output-format stream-json --verbose > logs/$name.jsonl 2> logs/$name.err
print "worker $name exit $?"
