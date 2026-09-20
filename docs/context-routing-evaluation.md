# Frozen A/B/C evaluation and release gate

The offline tests are synthetic regression checks. Do not call their pass rate a
retrieval benchmark. No live Jev or native-agent result is bundled with this PR.
The scorer represents missing arms as `not_run`, partial observations as `partial`,
and unmeasured input tokens or end-to-end outcomes as null.

## Freeze first

Choose owner-reviewed, de-identified tasks from real sessions. Include issue pickup,
parallel writers, investigation, merge/deployment, ambiguous acknowledgements, stale
sources, conflicting causes, manual-only skills, scope changes, oversized material,
non-Latin text, provider outage and a task needing no additional context.

Store private fixtures locally, never in these public repositories. Pin the corpus
revision and registry digest. Label required IDs, forbidden/superseded IDs, relevant
conflict pairs and desired task outcome. Label before tuning. Split by incident/task
family, not paraphrase, and keep each family entirely in train or test. The validator
rejects family leakage, duplicate IDs, missing provenance and contradictory labels.

One case (illustrative schema, not benchmark evidence):

```json
{
  "id": "deployment-conflict-heldout-01",
  "family": "incident-family-01",
  "split": "test",
  "source_revision": "actual-frozen-corpus-revision",
  "label_provenance": "owner-reviewed against the recorded incident evidence",
  "required_ids": ["memory:claim-a", "memory:claim-b"],
  "forbidden_ids": ["memory:retired-procedure"],
  "conflict_pairs": [["memory:claim-a", "memory:claim-b"]],
  "budget_bytes": 16000,
  "state": {
    "session_id": "unique-replay-session",
    "as_of": "2026-09-20",
    "scope": {"project": "example"},
    "goal": "Investigate the deployment failure"
  }
}
```

Use a JSON array of cases. The CLI does not invent corpus source revisions; freeze and
verify them in the host harness. Source hashes are still verified at every replay.

## Compare three arms, not two

**A-native:** existing native selection under the same task, repository revision,
installed catalogue and model. Capture actual selected references and provider usage
from a real run. Do not substitute all installed skills as the native selection.

**B-local:** deterministic eligibility + local retrieval + relationships + budget.

**C-Jev:** the identical B pipeline with the optional provider. Explicitly approved
public descriptions/task capsules only. Report how many cases actually reached Jev;
a privacy fallback is not a successful Jev call. Pin model and prompt/schema revision.

```sh
python "$ENGINE/context_router_eval.py" replay --cases private-cases.json \
  --registry frozen-registry.json --roots private-roots.json > B-local.json
# Explicit paid/egress opt-in only after reviewing the public capsule fields:
python "$ENGINE/context_router_eval.py" replay --cases private-cases.json \
  --registry frozen-registry.json --roots private-roots.json --jev > C-jev.json
python "$ENGINE/context_router_eval.py" score --cases private-cases.json \
  --observations A-native.json --observations B-local.json \
  --observations C-jev.json > comparison.json
```

An observation contains case_id, arm, source_revision, selected_ids and optionally
candidate_ids, status, latency_ms, actual input_tokens, cached_input_tokens,
boolean task_success and provider metadata. Native observations must be captured, not
authored to match labels. Use a host adapter to measure actual post-routing prompts,
cache hits and task outcomes for B/C too; the standalone replay cannot measure those.

## Inspect failures before the average

Report candidate recall separately from final required coverage. Inspect forbidden
loads, half-loaded conflicts, entire conflict omission, blocked tasks and missing
observations. A system that blocks every task is not successful merely because it
loads no forbidden record. The scorer exposes blocked count and coverage separately.

Measure catalogue cost, incremental loaded-body cost and accumulated conversation cost
independently. Bundle bytes are an exact size measurement, **not billed token savings**.
Capture main-model uncached/cached tokens, Jev input usage, actual request count and
end-to-end task outcome. Missing/failed response usage is unknown, not zero. Include
provider/API cost, added latency and any main-model cache loss in the comparison.

Evaluate both macOS installed layout and checkout layout. For ATC, retain the existing
full plugin as the control; never enable full and lean copies together. Test hook
resume/install paths, source refresh, off switch, host skill permissions and forked
contexts. An advisory that merely adds a recommendation may save no catalogue tokens.

## Owner-reviewed activation criteria

Set quality/latency targets before running the held-out set. Require no manual-only
bypass, no removed mandatory guard, no half-conflict, no automatic memory mutation and
no unapproved outbound content. Require acceptable held-out required coverage and task
success, not just reduced context. Review false negatives individually. Calibrate
provider thresholds only on training families; report held-out performance without
retuning. Compare C against B, not only against an unfiltered catalogue.

Do not ship active routing or a lean plugin until the owner signs off on the measured
report and rollback. Rollback is remove the optional advisory/stop passing active mode,
set CONTEXT_ROUTER_DISABLE=1, and use the unchanged full plugin/native retrieval path.
Source memories, existing hooks and global settings have not been rewritten.

Outstanding evidence at PR creation: actual native A/B/C host runs, live Jev
calibration, measured billed-token/cache effects, macOS installed-host integration,
and subscription-value impact. These are release gates, not silently checked boxes.
