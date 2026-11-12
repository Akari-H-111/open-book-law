#!/bin/zsh
# Run a free-model worker on an exported copy of a repository, inside an OS sandbox.
#
# The worker sees a copy of the listed paths with no git history. It cannot read private folders or exam
# questions, it can write only inside its copy and temp folders, and nothing returns to the real repository
# until the conductor reviews the diff.
#
# Usage: free_worker.sh <task> <repo> <brief-file> <model> <path>...
#   task        short name, used for the working folder
#   repo        repository to export from
#   brief-file  the task text
#   model       for example opencode/deepseek-v4.1-flash-free#max
#   path...     repository paths to export
# Optional: READ_DATA=<folder> lets the worker read one data folder. Exam question files stay blocked.
# Optional: PRIVATE_ROOT=<folder> is blocked for reading. By default it is two levels above the repository,
# the folder that holds all projects and downloads.
set -u
task=$1; repo=$2; brief=$3; model=$4; shift 4
H=$HOME
private_root=${PRIVATE_ROOT:-${repo:A:h:h}}
work=$H/open-book-workers/$task
log=$H/open-book-workers/$task.log
[[ -e $work ]] && { print "already exists: $work"; exit 2; }
mkdir -p $work
git -C $repo archive HEAD -- "$@" | tar -x -C $work
cat > $work/opencode.json <<'EOF'
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "*": "allow",
    "external_directory": "deny",
    "webfetch": "deny",
    "websearch": "deny",
    "bash": {
      "*": "allow",
      "git push*": "deny",
      "git remote*": "deny",
      "curl *": "deny",
      "wget *": "deny",
      "sudo *": "deny",
      "ssh *": "deny"
    }
  }
}
EOF
git -C $work init -q -b main
git -C $work add -A
git -C $work -c user.name=baseline -c user.email=baseline@local commit -q -m "Baseline export"
git -C $work config user.name "free-worker"
git -C $work config user.email "free-worker@local"

profile=$H/open-book-workers/$task.sb
data_rule=""
if [[ -n "${READ_DATA:-}" ]]; then
  data_rule="(allow file-read-data (subpath \"$READ_DATA\"))"
fi
cat > $profile <<EOF
(version 1)
(allow default)
(deny file-read-data (subpath "$private_root"))
(deny file-read-data (subpath "$H/Documents"))
(allow file-read-data (subpath "$H/Documents/agent-rules"))
(deny file-read-data (subpath "$H/Downloads"))
(deny file-read-data (subpath "$H/Desktop"))
(deny file-read-data (subpath "$H/Pictures"))
(deny file-read-data (subpath "$H/.ssh"))
(deny file-read-data (subpath "$H/.claude"))
(allow file-read-data (literal "$H/.claude"))
(deny file-read-data (subpath "$H/.codex"))
(deny file-read-data (subpath "$H/.aws"))
(deny file-read-data (subpath "$H/.config/gh"))
(deny file-read-data (subpath "$H/.cache/huggingface"))
(deny file-read-data (subpath "$H/Library/Keychains"))
(deny file-read-data (subpath "$H/Library/Application Support"))
(deny file-read-data (subpath "$H/Library/Mail"))
(deny file-read-data (subpath "$H/Library/Messages"))
$data_rule
(deny file-read-data (regex #"/moex/.*/Q_[^/]*\$"))
(deny file-read-data (regex #"/derived/questions\.jsonl\$"))
(deny file-read-data (regex #"/barexam_qa/"))
(deny file-read-data (regex #"/derived/goodlaw/"))
(deny file-write*)
(allow file-write* (subpath "$work"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/private/var/folders"))
(allow file-write* (subpath "$H/.local/share/opencode"))
(allow file-write* (subpath "$H/.local/state/opencode"))
(allow file-write* (subpath "$H/.cache/opencode"))
(allow file-write* (subpath "$H/.config/opencode"))
(allow file-write* (subpath "$H/.opencode"))
(allow file-write* (subpath "$H/agent-clis/kilo"))
(allow file-write* (subpath "$H/Library/Caches"))
(allow file-write* (literal "/dev/null"))
(allow file-write* (literal "/dev/tty"))
EOF

cd $work || exit 2
print "$(date '+%F %T') START $task $model" > $log
# HOME points inside the copy, so the worker has its own empty OpenCode state and config.
mkdir -p $work/.home
print ".home/\nopencode.json" >> $work/.git/info/exclude
# A model name that starts with "kilo/" runs on Kilo CLI, for tasks with public data only. Its free routes may log.
if [[ $model == kilo/* ]]; then
  cp $work/opencode.json $work/kilo.json
  print "kilo.json" >> $work/.git/info/exclude
  runner=($H/agent-clis/kilo/node_modules/.bin/kilo run --auto -m "$model" --format json --title "$task")
else
  runner=(opencode run --standalone --auto -m "$model" --format json --title "$task")
fi
HOME=$work/.home OPENCODE_DISABLE_CLAUDE_CODE=1 OPENCODE_DISABLE_EXTERNAL_SKILLS=1 KILO_DISABLE_CLAUDE_CODE=1 \
  PATH="$H/venvs/open-book-law/bin:$H/.opencode/bin:$PATH" sandbox-exec -f $profile \
  $runner "$(cat $brief)" >> $log 2>&1 < /dev/null
code=$?
print "$(date '+%F %T') END $task code=$code" >> $log
print "worker $task exit $code"
grep -q 'provider.quota' $log && print "QUOTA: this free model hit its usage limit"
git -C $work log --oneline | head -20
git -C $work diff --stat HEAD~0 2>/dev/null | tail -3
