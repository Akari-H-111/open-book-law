#!/bin/zsh
# Run an OpenAI Codex worker on a folder outside the real repositories. Codex applies its own OS sandbox:
# it writes only inside the folder and has no network, but it can read the disk, so each brief forbids private
# paths and the conductor greps the trace afterwards.
# Usage: codex_worker.sh <task> <folder> <brief-file> <model> <sandbox: workspace-write|read-only>
set -u
task=$1; work=$2; brief=$3; model=$4; mode=$5
log=$HOME/open-book-workers/$task.codex.jsonl
print "START $task $model $(date '+%F %T')" > $log.status
PATH="$HOME/venvs/open-book-law/bin:$PATH" codex exec -C "$work" -s "$mode" --skip-git-repo-check --ephemeral -m "$model" \
  -c model_reasoning_effort=high -c 'sandbox_workspace_write.network_access=false' --json \
  -o "$HOME/open-book-workers/$task.report.md" "$(cat $brief)" > $log 2>&1 < /dev/null
code=$?
print "END code=$code $(date '+%F %T')" >> $log.status
print "worker $task exit $code"
print "private-path mentions in the trace: $(grep -cE 'moex/.*/Q_|questions\.jsonl|barexam_qa|goodlaw/|\.ssh|Documents/' $log)"
