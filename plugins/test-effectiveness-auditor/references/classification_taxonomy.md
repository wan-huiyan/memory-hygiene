# Incident classification taxonomy

Classifications produced by Phase 4 of the audit. Apply the first rule that matches, in order.

## `unrunnable`

The test suite did not execute to completion at the pre-fix SHA. Examples:

- Collection-time `ImportError` because a dependency is not installed in the current Python
- `conftest.py` requires an environment variable that isn't set (e.g. service credentials)
- Timeout before the suite produces a summary line
- Tests hit a network service the replay environment can't reach
- Test command was never valid at that SHA (pre-dates the project's test setup)

`unrunnable` is NOT a negative judgment on the test suite — it's a data-quality note. Count these separately and exclude from the catch-rate denominator. A report with 4/8 unrunnable is flagging an environmental gap, not a test-quality gap.

## `caught`

Both conditions true:
1. Suite exited nonzero at the pre-fix SHA
2. At least one failing test name, failing test file path, or failure message textually references the buggy area

"Textually references" means: conservative substring match against any of
- the fix commit's subject line
- the fix commit's modified file paths (component names)
- the write-up's title or key terms (from `docs/findings/*` etc.)

Example: commit `fix: mask_zero_injection in bsts fit`, failed test `tests/test_mask_mode_propagation.py::test_zero_injection_raises` — the token "mask" and "zero_injection" appear in both. Classify `caught`.

Counter-example: suite fails at pre-fix SHA, but the failure is in `test_unrelated_thing.py` with no textual overlap to the fix. Downgrade to `ambiguous` and let a human re-classify.

## `gap_testable`

Suite exited 0 (all green) at the pre-fix SHA, AND the incident is of a kind that unit or integration tests could plausibly express. Indicators:
- Logic errors in a pure function
- Data-transformation bugs (wrong filter, off-by-one, missing NULL handling)
- API contract mismatch between two internal modules
- Assertion missing where an invariant was violated
- Config-handling bugs where the config values themselves are in-repo

These are the actionable entries for the gap backlog.

## `gap_hard`

Suite exited 0, but the bug is fundamentally hard to catch via unit/integration tests. Indicators:
- Upstream data schema change in an external system
- Third-party API contract change or behavior change
- Cloud infra config drift (secret rotation, IAM change, missing VPC route)
- Race condition detectable only under production load
- UI/rendering bug that no assertion in the existing framework captures

These are worth recording but not prioritizing for new unit tests. The right fix is usually a contract test, a monitor, or a schema-drift detector — not a unit test.

Edge case: a bug triggered by external data drift MAY be catchable by a test that pins the data contract (e.g. schema validation on ingest). If that test would be small and low-maintenance, prefer `gap_testable`. If the contract is too fluid or the data source too unstable, prefer `gap_hard`.

## `ambiguous`

Suite failed at pre-fix SHA, but:
- The failures are in unrelated tests (pre-existing flakes, environment issues)
- OR only one test failed but its failure message doesn't textually match the incident
- OR the log shows collection errors mixed with real failures and the signal is unclear

Do not count these as caught or gap. Surface them in the report under "incidents requiring manual review" so a human can decide.

## Method 2 (CI history) sub-classifications

Applied to each PR-blocking CI failure, not to incidents:

### `real_catch`
The CI failure represented a real bug the author was about to merge. Examples:
- Logic test failing for a regression in business logic
- Integration test catching a broken contract between services
- Data test catching a malformed migration

### `author_hygiene`
The failure would have been caught by a local pre-commit or a linter if the author had run it. Examples:
- Black / prettier formatting
- Pyflakes / ESLint warnings
- Type-check errors the IDE would flag

Still valuable (it's a safety net), but these don't speak to "test effectiveness" in the "catches bugs" sense. Report them as a separate bucket.

### `flake`
Re-run of the same SHA passed without code change. These are test-suite quality debt — they erode signal over time. Report the rate separately.

### `infra`
Failure caused by CI runner, base image, secret rotation, external service outage. Not a code problem, not a test problem. Report separately.

## Reporting convention

In the audit report, present Method 1 counts and rate:
- **Effective catch rate** = `caught / (caught + gap_testable + gap_hard + ambiguous)`
- Exclude `unrunnable` from the denominator; report `unrunnable` count separately

For Method 2:
- **Effective CI catch rate** = `real_catch / (real_catch + author_hygiene + flake + infra)`
- Report each bucket as raw count AND percent; the composition matters as much as the total rate
