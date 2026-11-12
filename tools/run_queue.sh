#!/bin/zsh
# Run heavy jobs one at a time, because the machine has one fanless GPU.
# Usage: tools/run_queue.sh <job-args-file>
# Each line of the file holds arguments for the retrieval experiment. Blank lines and # comments are skipped.
# A line may name a data file as $OBL_DATA/...; the script replaces only that placeholder.
set -u
cd "${0:A:h:h}" || exit 2
export OBL_DATA=${OBL_DATA:-$PWD/data_local}
PY=$HOME/venvs/open-book-law/bin/python
LOG=logs/queue.log
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  print "$(date '+%F %T') START $line" >> $LOG
  args=${line//\$OBL_DATA/$OBL_DATA}
  caffeinate -i -s $PY -I -m ${=args} >> logs/queue-output.log 2>&1
  code=$?
  print "$(date '+%F %T') END code=$code $line" >> $LOG
  if [[ ! -d $PWD/open_book_law ]]; then
    print "$(date '+%F %T') DRIVE MISSING" >> $LOG
    exit 3
  fi
done < "$1"
print "$(date '+%F %T') QUEUE DONE $1" >> $LOG
