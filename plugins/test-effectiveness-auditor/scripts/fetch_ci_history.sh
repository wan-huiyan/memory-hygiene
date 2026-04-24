#!/usr/bin/env bash
# fetch_ci_history.sh — Pull CI run history for Method 2 analysis.
#
# Tries GitHub Actions first (via gh), falls back to Cloud Build (via gcloud)
# if a --gcp-project is supplied. Emits JSON to stdout.
#
# Usage:
#   fetch_ci_history.sh --repo <owner/repo> [--months 6]
#   fetch_ci_history.sh --gcp-project <project-id> [--months 6]
#
# Exits 0 with {"ci_history_available": false, "reason": "..."} if neither
# source returns data — that is itself a useful finding for the report.

set -u
set -o pipefail

REPO=""
GCP_PROJECT=""
MONTHS=6

while (( "$#" )); do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --gcp-project) GCP_PROJECT="$2"; shift 2 ;;
    --months) MONTHS="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Compute the ISO date MONTHS ago (portable between BSD and GNU date).
if date -u -v-1d >/dev/null 2>&1; then
  SINCE=$(date -u -v-"${MONTHS}"m +%Y-%m-%dT%H:%M:%SZ)
else
  SINCE=$(date -u -d "${MONTHS} months ago" +%Y-%m-%dT%H:%M:%SZ)
fi

if [[ -n "$REPO" ]]; then
  # GitHub Actions path
  if ! command -v gh >/dev/null 2>&1; then
    echo '{"ci_history_available": false, "reason": "gh CLI not installed"}'
    exit 0
  fi
  # Paginate up to 500 runs, filter client-side by date & conclusion.
  RUNS=$(gh api "repos/$REPO/actions/runs?per_page=100" --paginate 2>/dev/null \
    | python3 -c "
import json, sys
since = '$SINCE'
try:
    pages = sys.stdin.read().strip()
    # gh --paginate concatenates JSON objects; split them.
    objs = []
    depth = 0
    start = 0
    for i, ch in enumerate(pages):
        if ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try: objs.append(json.loads(pages[start:i+1]))
                except Exception: pass
    runs = []
    for o in objs: runs.extend(o.get('workflow_runs', []))
except Exception as e:
    print(json.dumps({'ci_history_available': False, 'reason': f'parse error: {e}'}))
    sys.exit(0)

if not runs:
    print(json.dumps({'ci_history_available': False, 'reason': 'no GitHub Actions runs found'}))
    sys.exit(0)

filtered = [r for r in runs if r.get('created_at', '') >= since]
out = {
    'ci_history_available': True,
    'source': 'github_actions',
    'total_runs': len(filtered),
    'since': since,
    'runs': [
        {
            'id': r.get('id'),
            'name': r.get('name'),
            'conclusion': r.get('conclusion'),
            'event': r.get('event'),
            'created_at': r.get('created_at'),
            'head_sha': r.get('head_sha'),
            'html_url': r.get('html_url'),
            'pull_requests': [pr.get('number') for pr in r.get('pull_requests', [])],
        }
        for r in filtered
    ],
}
print(json.dumps(out, indent=2))
")
  echo "$RUNS"
  exit 0
fi

if [[ -n "$GCP_PROJECT" ]]; then
  if ! command -v gcloud >/dev/null 2>&1; then
    echo '{"ci_history_available": false, "reason": "gcloud CLI not installed"}'
    exit 0
  fi
  BUILDS=$(gcloud builds list --project="$GCP_PROJECT" --limit=500 --format=json 2>/dev/null || echo "[]")
  echo "$BUILDS" | python3 -c "
import json, sys
since = '$SINCE'
builds = json.load(sys.stdin)
filtered = [b for b in builds if b.get('createTime', '') >= since]
if not filtered:
    print(json.dumps({'ci_history_available': False, 'reason': 'no Cloud Build entries in window'}))
    sys.exit(0)
out = {
    'ci_history_available': True,
    'source': 'cloud_build',
    'total_runs': len(filtered),
    'since': since,
    'runs': [
        {
            'id': b.get('id'),
            'status': b.get('status'),
            'created_at': b.get('createTime'),
            'trigger_id': b.get('buildTriggerId'),
            'log_url': b.get('logUrl'),
        }
        for b in filtered
    ],
}
print(json.dumps(out, indent=2))
"
  exit 0
fi

echo '{"ci_history_available": false, "reason": "no --repo or --gcp-project supplied"}'
exit 0
