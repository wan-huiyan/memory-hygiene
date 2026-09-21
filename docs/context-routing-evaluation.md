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

## Jev gate: what is now measured, and what is still open

Updated 2026-09-21. The Jev transport was originally merged with its contract
asserted from documentation only, and every Jev test injected a hand-written
transport shaped to satisfy the validator it was testing. That could only prove
the validator agreed with its author. The rows below separate what real calls
established from what is still assumed.

| Claim | Status | Evidence |
|---|---|---|
| Endpoint, request shape, Noul question/answer shape, integer `usage` | **Verified** | Documented, and matched by real responses |
| `jev-1.13.0` accepted as a request model | **Verified live** | HTTP 200; response echoes `jev-1.13.0` |
| The API echoes the resolved version, never the alias | **Verified live** | Requesting `jev-latest` returns `jev-1.13.0` |
| Refusing aliases is required, not cosmetic | **Verified live** | A provider sending `jev-latest` would fail `unexpected_model` on every call |
| Shipped `JevProvider.rank()` / `.compare()` work end-to-end | **Verified live** | `status: live`, real token usage returned |
| Scores discriminate relevant from irrelevant records | **Weak evidence** | One synthetic set: relevant 0.82/0.77, irrelevant 0.01. Not a benchmark |
| 3.0 s timeout survives the 32-candidate maximum | **Measured once** | ~0.83 s at 32 candidates; ~3.6x headroom, one machine, one day |
| Invalid key leaks neither key nor response body | **Verified live** | 401 surfaces as bare `transport_failure` |
| Missing key costs nothing | **Verified live** | `missing_key`, `attempted=False` |
| Byte caps, timeout bounds, 32-candidate ceiling | **Local choice** | TypeSafe documents no such limits; ours are deliberately stricter |
| 429 / 529 backoff behaviour | **Open** | Not reproducible on demand; zero retries means rate limiting degrades to local fallback |
| 0.25 negative threshold is calibrated | **Open** | Still an experimental starting value; needs held-out calibration |
| Native A/B/C host runs | **Open** | Needs the owner's held-out cases |
| Billed-token, prompt-cache and subscription-value effects | **Open** | Unmeasured; no savings claim is made |
| macOS installed-host integration | **Open** | Unmeasured |

`tests/context_routing/fixtures/jev_live_responses.json` holds verbatim server
responses; `test_live_contract.py` replays them through the shipped provider, so
the offline suite now fails if the response contract moves. Re-capture per
`tests/context_routing/fixtures/README.md`.

The Open rows are release gates, not silently checked boxes.
