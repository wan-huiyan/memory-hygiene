---
name: test-effectiveness-auditor
description: "Quantitatively measure how effective a project's automated tests are at catching real bugs. Use this skill when: (1) the user asks 'how good are our tests?', 'do our tests actually catch bugs?', 'measure test effectiveness', or 'audit our test suite'; (2) a team has anecdotal impressions about test quality but no data; (3) before investing in more tests, to identify which gaps matter most; (4) after an incident slipped through CI, to understand whether the test suite should have caught it; (5) when evaluating whether a CI pipeline is paying for itself. Produces a report at ~/Documents/<project>_test_effectiveness_audit.md with per-incident catch rates, a classified gap list, and targeted recommendations. Read-only relative to project source — does not modify code or auto-write tests."
---

# Test Effectiveness Auditor v1.0

Answers the question: **how helpful are our automated tests at catching bugs?** Not by proxy metrics like coverage percent or test count, but by replaying real bugs that already happened and checking whether the test suite, as it stood just before the fix, actually failed on the buggy commit.

The honest baseline for "are tests worth it" is historical: bugs that made it to production despite the tests are the direct evidence of gaps; CI failures that forced a code change before merge are the direct evidence of catches. Everything else is speculation.

## Why this matters

Most teams measure test health by coverage % (e.g. pytest --cov). Coverage tells you which lines executed, not whether any assertion would have *failed* when the behavior was wrong. A line can be 100% covered by a test that would pass under the bug. This audit inverts the question: take known bugs, rewind to the pre-fix commit, and observe whether the suite catches them.

Two methods, in priority order:

1. **Historical incident replay** (primary signal) — for each documented bug, check out the pre-fix SHA in a worktree, run the suite, observe pass/fail, and classify.
2. **CI history analysis** (secondary signal) — pull CI runs that forced a pre-merge change, classify by whether the failure represented a real logic/data/integration catch vs. noise (lint, formatting, flaky).

Mutation testing, test-layer ablation, and coverage-delta analysis are deliberately NOT in scope for v1. They're higher-cost methods whose ROI depends on first knowing the Method 1/2 baseline.

## When to run

- On demand when the user asks about test quality or effectiveness
- After an incident to triage "tests should have caught this" vs "fundamentally hard to catch"
- Before a test-investment cycle (writing more tests), to target the biggest gaps first
- Proactively suggest after you notice: a team asking "should we write more tests?", a project with `docs/findings/` or `docs/issues/` accumulating, or a manager expressing doubt about CI ROI

## Scope and non-goals

- **Read-only relative to project source.** The skill creates temp worktrees, runs tests, and reads git history. It never edits project code.
- **Never auto-writes tests.** Recommendations are produced as a human-reviewed backlog; the user decides which gaps to close.
- **Idempotent.** Running twice with the same project HEAD and same CI run window produces the same report. Keyed by (project head sha, incident id, CI run id).
- **Conservative on classification.** When the replay is inconclusive (environment error, missing dep, flake), the incident is classified `unrunnable` rather than forced into caught/gap.

## The audit workflow

### Phase 1: Discover

Gather the raw material before doing anything else. Parallel reads where possible.

#### 1a. Canonical test command

The test command is what Method 1 will execute inside a worktree. Check these in order and stop at the first hit:

1. `Makefile` targets named `test`, `ci`, `check` — use the actual shell command the target runs
2. `.github/workflows/*.yml` — find the step that invokes pytest/jest/go test/etc. and extract the exact command
3. `cloudbuild*.yaml` — same treatment
4. `pyproject.toml` `[tool.pytest.ini_options]` addopts or `setup.cfg` `[tool:pytest]`
5. Fallback: `pytest <tests_dir>` where `<tests_dir>` is wherever `test_*.py` files are concentrated

Record the exact command AND any required environment (e.g. `PYTHONPATH=.`, activating a venv, `SCHUH_SKIP_VI_TESTS=1`). If the command needs credentials or external services, note that and downgrade Method 1 scope.

#### 1b. Incident signal sources

For each signal below, list everything it finds:

- `docs/findings/*` — substantive post-mortems
- `docs/issues/*` — bug write-ups
- `docs/diagnostics/*`, `docs/audits/*` — project-specific incident docs
- Root-level `discovery_*.md`, `incident_*.md`, `postmortem_*.md`
- Git log: `git log --oneline --all -i --grep='fix\|bug\|revert\|hotfix\|incident' -n 500`
- GitHub closed issues with the `bug` label (if the project uses GitHub Issues): `gh issue list --state closed --label bug --limit 100 --json number,title,closedAt,url`

De-duplicate: a single incident often has a write-up AND a fix commit AND an issue. Merge into one record.

#### 1c. CI history

- `gh api repos/<owner>/<repo>/actions/runs?per_page=100` — filter to last 6 months
- If no GH Actions: `gcloud builds list --project=<project-id> --limit=200 --format=json` (Cloud Build) — note project ID must be supplied by the user
- If neither: record `ci_history_available=false` in the report; Method 2 degrades to "N/A — project does not run tests in CI" which is itself a finding worth reporting

#### 1d. Cache lookup

Before running anything, check for a cache at `~/Documents/<project>_test_effectiveness_cache.json`. If it exists, load replayed incidents keyed by `(pre_fix_sha, test_command_hash)`. Skip any incident whose (sha, cmd_hash) is already cached; use the cached result. This is what makes the skill idempotent — reruns only re-execute newly discovered incidents or incidents whose test command changed.

### Phase 2: Select incidents to replay

Do NOT replay every git commit matching "fix" — that's hundreds of commits and most are cosmetic (typos, renames, doc fixes). Prioritize as:

1. Every incident with a dedicated write-up in `docs/findings/`, `docs/issues/`, `docs/diagnostics/`, `docs/audits/` — these are high-signal by human selection
2. Every commit matching `revert` or `hotfix` (these almost always indicate production escapes)
3. Commits matching `fix(<critical-component>):` where `<critical-component>` is identified from git blame on the most-changed source files
4. Cap at 10 incidents for a first-pass audit. More is better but has sharply diminishing returns; beyond 10, the report is noise.

For each selected incident, resolve:
- `incident_id`: human-readable slug (e.g. `mask_zero_injection_bug`)
- `fix_commit`: the SHA where the fix landed
- `pre_fix_commit`: `git rev-parse <fix_commit>^` (the commit immediately before)
- `source`: write-up path OR commit message

Present this list to the user for confirmation before spending minutes-to-hours on replay. The user may drop irrelevant incidents (e.g. "this was a doc fix, not a bug") or add ones the heuristics missed.

### Phase 3: Replay each incident

Use a temp worktree so the user's working tree is undisturbed. Pattern borrowed from claude-code-ab-harness:

```bash
WT_ROOT="${TMPDIR:-/tmp}/test-effectiveness-auditor"
mkdir -p "$WT_ROOT"
WT="$WT_ROOT/${INCIDENT_ID}"
git -C "$PROJECT" worktree add -f "$WT" "$PRE_FIX_SHA"
```

Then in `$WT`:

1. Reproduce the environment as minimally as possible. The skill does NOT install dependencies — it assumes the user's existing system env can run the suite. If not, classify as `unrunnable` and move on.
2. Run the canonical test command with a reasonable timeout (default 20 minutes per incident). Capture stdout/stderr and the exit code.
3. Parse the output to extract: total tests, passed, failed, errors, skipped, and the list of failed test names.

Always clean up:
```bash
git -C "$PROJECT" worktree remove -f "$WT" 2>/dev/null || rm -rf "$WT"
```

Record per-incident:
- `exit_code`: 0 / nonzero
- `failed_tests`: list of test names that failed
- `duration_seconds`: how long the suite took
- `ran_to_completion`: did it finish or hit the timeout / setup error

### Phase 4: Classify each incident

Apply these rules in order (first match wins). See `references/classification_taxonomy.md` for full definitions and edge cases.

1. **`unrunnable`** — the suite didn't run to completion at the pre-fix SHA (missing deps, import errors in conftest, external service required, timeout). This is not a suite-quality judgment; it's a data-quality note. Report count separately.

2. **`caught`** — suite exited nonzero AND at least one failing test's name or failure message textually references the buggy area (function name, module, behavior described in the write-up). Use conservative textual matching: substring of the commit message's subject OR a module path appearing in both the fix diff and the failing test file.

3. **`gap_testable`** — suite exited zero (all pass), but the buggy behavior is of a kind that unit or integration tests *could* express (logic error, data transformation, assertion missing, mismatched contract between layers). These are the actionable gaps.

4. **`gap_hard`** — suite exited zero, but the bug is fundamentally hard to catch at unit/integration level (external API contract change, upstream data schema drift, third-party dependency bump, config/secret rotation, flaky infrastructure). Tests may still help at integration or contract-test level, but the cost/value is different.

5. **`ambiguous`** — suite failed but for reasons unrelated to the incident (pre-existing flakes, environmental noise). Needs manual review before conclusions.

For classification between `gap_testable` and `gap_hard`, use your judgment based on the incident write-up. When genuinely unsure, mark `gap_testable` — that errs on the side of treating the gap as actionable.

### Phase 5: CI history analysis (Method 2)

If `ci_history_available=true` in Phase 1:

1. Pull all CI runs in the last 6 months where `conclusion == "failure"` that were attached to PRs later merged (i.e. the failure forced a change, not a PR the author abandoned).
2. For each failed run, fetch the logs or the failing step's summary.
3. Classify each failure as one of:
   - `real_catch` — genuinely prevented a bug (logic error, integration break, data issue)
   - `author_hygiene` — lint, formatting, type error that the author would have caught locally if they'd run the linter before pushing (still worth having, but the skill's claim on "test effectiveness" is weaker)
   - `flake` — the retry passed without code change
   - `infra` — CI image update, secret rotation, external service outage
4. Report the split as `real_catch / (real_catch + author_hygiene + flake + infra)` — this is the "effective catch" rate of CI.

If `ci_history_available=false`, write a single paragraph explaining why Method 2 is N/A for this project and recommend enabling CI tests as a finding.

### Phase 6: Write the report

Write to `~/Documents/<project-name>_test_effectiveness_audit.md`. ALWAYS use this exact template:

```markdown
# Test Effectiveness Audit — <project-name>
_Generated <YYYY-MM-DD> at commit <short-sha>; skill v<version>._

## Summary

- **Incidents replayed:** N (M unrunnable, dropped from rate)
- **Caught by existing tests:** X of (N−M) → **Y%**
- **Testable gaps:** G
- **Hard-to-catch:** H
- **CI effective-catch rate (Method 2):** Z% of PR-blocking CI failures were real catches, or N/A.

Bottom-line: <one-sentence honest read>.

## Method 1 — Incident replay

| # | Incident | Pre-fix SHA | Result | Classification | Notes |
|---|----------|-------------|--------|----------------|-------|
| 1 | mask_zero_injection_bug | abc1234 | 3 tests failed | caught | test_mask_mode_propagation.py pointed straight at the buggy path |
| 2 | ... | ... | all pass | gap_testable | ... |

### Failure mode breakdown
- <brief categorization of the gap incidents — e.g. "2 of 3 testable gaps involved data-transformation edge cases not covered by existing pytest">

## Method 2 — CI history

(If applicable.) Breakdown of last-6-months PR-blocking CI failures:
- Real catches: X (Y%)
- Author hygiene: ...
- Flakes: ...
- Infra: ...

## Gap backlog — what to add

Ordered by estimated impact (highest first). Each entry links to the originating incident.

1. **<gap name>** — affected component, type of test that would close it, pointer to incident
2. ...

## Recommendations

- Highest-leverage test investments
- Any CI-config changes (e.g. run tests in CI if not currently run)
- Flaky tests to stabilize

## Methodology notes

- Incidents replayed: <how selected>
- Classification rules: see references/classification_taxonomy.md
- Environment caveats (e.g. PYTHONPATH=., skipped causalpy tests): <list>
- Timestamp, skill version, cache location: <…>

## Reproducibility

Cache: `~/Documents/<project-name>_test_effectiveness_cache.json`. Rerun this skill to refresh; cached incidents are skipped unless the pre-fix SHA or test command changed.
```

### Phase 7: Present and hand off

- Surface the report path to the user
- Highlight the 2-3 most actionable findings from the gap backlog
- Offer to open the top-priority gap as a ticket / discussion, but do NOT auto-write tests — the user decides

## Using the helper scripts

The skill bundles three scripts; the agent SHOULD use them to avoid reinventing the wheel:

- `scripts/identify_incidents.py` — input: project path; output: JSON of candidate incidents merged from docs/ + git log. Run once at Phase 1b.
- `scripts/replay_incident.sh` — input: project path, incident_id, pre_fix_sha, test_command; output: JSON with exit_code, failed_tests, duration. Handles worktree create + cleanup. Run once per incident in Phase 3.
- `scripts/fetch_ci_history.sh` — input: repo slug OR cloud build project id; output: JSON of CI runs in last 6mo with conclusion + URL. Run once at Phase 1c.

See each script's header comment for full usage.

## Writing guidelines

- Be honest about sample size. A 5-incident audit is a directional signal, not a statistically significant measurement. Say so in the report.
- Be conservative on classification. `unrunnable` and `ambiguous` are not embarrassing — they're honest. Forcing a weak incident into `caught` or `gap` corrupts the measurement.
- Don't conflate "tests ran green at pre-fix commit" with "the test suite is bad". Some bugs are genuinely hard to catch via unit/integration tests; `gap_hard` captures that.
- Don't recommend tests the skill hasn't earned. The gap backlog should only suggest tests where the evidence from replay points at a specific behavior.

## Limitations

- Replay requires a runnable test environment. Projects with heavy external-service dependencies or custom Docker test runners may report high `unrunnable` rates and need Method 2 only.
- Classification uses heuristic textual matching for `caught` — false negatives (tests that WOULD have caught but whose names don't textually match the incident) are possible. The skill is conservative: prefer `gap_testable` on ties and let the human re-classify on review.
- CI history analysis requires gh CLI auth (for GitHub) or gcloud auth + project id (for Cloud Build). If the user can't provide these, Method 2 is skipped.
- Mutation testing, test-layer ablation, coverage-delta, and fault-injection are NOT performed. They're out of scope for v1.

## Version history

- v1.0 (2026-04-24): Initial release. Method 1 (historical replay) + Method 2 (CI history). Idempotent via per-incident cache.
