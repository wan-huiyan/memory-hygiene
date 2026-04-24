#!/usr/bin/env bash
# replay_incident.sh — Check out a pre-fix SHA in a fresh worktree, run the
# project's test command, and emit a JSON result record.
#
# Exits 0 on successful data collection regardless of whether the tests
# passed or failed — the failure signal IS the data we want. Exit nonzero
# only on infrastructure error (could not create worktree, etc).
#
# Usage:
#   replay_incident.sh \
#       --project <path-to-project> \
#       --incident-id <slug> \
#       --pre-fix-sha <sha> \
#       --test-command "<shell command>" \
#       [--timeout <seconds>] \
#       [--output <output.json>]
#
# The test-command runs with `bash -c` inside the worktree directory. The
# caller is responsible for including any required env vars (e.g.
# "PYTHONPATH=. pytest tests/").
#
# Worktrees are created under $TMPDIR/test-effectiveness-auditor/ and ALWAYS
# removed on exit, even on failure.

set -u
set -o pipefail

PROJECT=""
INCIDENT_ID=""
PRE_FIX_SHA=""
TEST_COMMAND=""
TIMEOUT=1200  # 20 min default
OUTPUT=""

while (( "$#" )); do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --incident-id) INCIDENT_ID="$2"; shift 2 ;;
    --pre-fix-sha) PRE_FIX_SHA="$2"; shift 2 ;;
    --test-command) TEST_COMMAND="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

for v in PROJECT INCIDENT_ID PRE_FIX_SHA TEST_COMMAND; do
  if [[ -z "${!v}" ]]; then echo "missing required arg: $v" >&2; exit 2; fi
done

WT_ROOT="${TMPDIR:-/tmp}/test-effectiveness-auditor"
mkdir -p "$WT_ROOT"
WT="$WT_ROOT/${INCIDENT_ID}-$$"

cleanup() {
  git -C "$PROJECT" worktree remove -f "$WT" 2>/dev/null || rm -rf "$WT"
}
trap cleanup EXIT INT TERM

if ! git -C "$PROJECT" worktree add -f --detach "$WT" "$PRE_FIX_SHA" >/dev/null 2>&1; then
  echo "{\"incident_id\":\"$INCIDENT_ID\",\"status\":\"worktree_failed\",\"pre_fix_sha\":\"$PRE_FIX_SHA\"}" \
       ${OUTPUT:+> "$OUTPUT"}
  exit 0
fi

# Use perl to timebox — macOS `timeout(1)` is not universally installed.
START_TS=$(date +%s)
LOG_TMP="$(mktemp -t te-auditor.XXXXXX)"
(
  cd "$WT" || exit 127
  # Run with a soft timeout via perl alarm wrapper so we work on macOS w/o coreutils.
  perl -e '
    use POSIX ":sys_wait_h";
    my $cmd = $ARGV[0];
    my $timeout = $ARGV[1] || 1200;
    my $pid = fork();
    if ($pid == 0) { exec("bash", "-c", $cmd); exit 127; }
    my $start = time();
    while (1) {
      my $rc = waitpid($pid, WNOHANG);
      if ($rc == $pid) { exit($? >> 8); }
      if (time() - $start > $timeout) { kill "TERM", $pid; sleep 3; kill "KILL", $pid; exit 124; }
      sleep 2;
    }
  ' "$TEST_COMMAND" "$TIMEOUT"
) >"$LOG_TMP" 2>&1
EXIT_CODE=$?
END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

if [[ $EXIT_CODE -eq 124 ]]; then
  STATUS="timeout"
elif [[ $EXIT_CODE -eq 0 ]]; then
  STATUS="all_passed"
else
  STATUS="some_failed"
fi

# Extract failed test names (pytest format) — best-effort, won't cover every framework.
FAILED_TESTS=$(grep -E "^FAILED |^ERROR " "$LOG_TMP" 2>/dev/null \
  | sed -E 's/^(FAILED|ERROR) ([^ ]+).*/\2/' \
  | sort -u \
  | head -200 \
  | python3 -c 'import sys, json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
if [[ -z "$FAILED_TESTS" ]]; then FAILED_TESTS="[]"; fi

# Summary line parse (pytest). Tolerant of other frameworks by falling through.
SUMMARY=$(grep -E "passed|failed|error|skipped" "$LOG_TMP" 2>/dev/null | tail -1 | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')
if [[ -z "$SUMMARY" ]]; then SUMMARY='""'; fi

LOG_TAIL=$(tail -40 "$LOG_TMP" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

RESULT=$(cat <<JSON
{
  "incident_id": "$INCIDENT_ID",
  "pre_fix_sha": "$PRE_FIX_SHA",
  "status": "$STATUS",
  "exit_code": $EXIT_CODE,
  "duration_seconds": $DURATION,
  "failed_tests": $FAILED_TESTS,
  "summary_line": $SUMMARY,
  "log_tail": $LOG_TAIL
}
JSON
)

if [[ -n "$OUTPUT" ]]; then
  echo "$RESULT" > "$OUTPUT"
else
  echo "$RESULT"
fi

rm -f "$LOG_TMP"
exit 0
