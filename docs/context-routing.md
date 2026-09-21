# Opt-in shared context routing (draft v0.1.0)

This adds **ordinary Python tooling, not another model-loaded skill**. The canonical
engine lives in `plugins/memory-hygiene/scripts/context_router.py`; Agent Traffic
Control consumes that engine through a version/hash-pinned adapter. Jev is an
optional provider, not a requirement and not an authority over memory validity.
Python 3.10 or later, standard library only. Nothing installs itself.

## Ownership and invariants

Memory hygiene owns the reviewed registry, scope, lifecycle, provenance, dependencies,
supersession, conflicts and human-approved corrections. ATC owns workflow state and
its existing permission/claim/isolation/shipping safeguards. The host owns the actual
outgoing context and skill invocation. A provider may rank eligible optional records;
it cannot authorize execution, demote a guard, rewrite a source, or approve an edge.

The path is: explicit inventory -> deterministic eligibility -> local retrieval ->
expand approved relationships -> protect required/conflicting evidence -> optional
Jev relevance judgments -> whole-bundle budget packing -> canonical source references.

Existing T0/T1/phase rules and the current memory-hygiene audit/approve/execute process
remain unchanged. Do not replace mandatory host instructions with this optional tool.
No existing skill frontmatter, plugin manifest, release version, installed settings or
resume-gate hook changes in this draft. A release/version bump belongs to reviewed
activation, not to this experimental tools-only PR.

## First run: entirely local and read-only

Run from a checkout or use the scripts directory of an explicitly selected plugin
version. There is no hidden search for whichever plugin-cache copy happens to exist.
The engine ships within the memory-hygiene plugin's scripts directory.

```sh
ENGINE=/absolute/path/to/memory-hygiene/plugins/memory-hygiene/scripts
python "$ENGINE/context_router.py" index \
  --root /absolute/path/to/approved-memory-root --namespace project-memory \
  --include '*.md' --metadata /absolute/path/to/reviewed-metadata.json > registry.json
python "$ENGINE/context_router.py" route \
  --root /absolute/path/to/approved-memory-root --registry registry.json \
  --state state.json > shadow-decision.json
python "$ENGINE/context_router.py" audit \
  --root /absolute/path/to/approved-memory-root --registry registry.json > audit-proposals.json
```

Omit `--metadata` on the first census. Registry and reports can contain private terms,
paths and knowledge: keep them outside public repositories, with private permissions
(e.g. set `umask 077` before redirecting). Neither registry nor reports are uploaded.
Use narrow includes, not your entire home directory. The index excludes common build
and VCS directories, rejects symlinked sources, and reports zero matching files as an
error rather than a clean audit. YAML frontmatter support is deliberately limited to
scalar discovery fields; ambiguous invocation controls fail closed. Complex lifecycle
metadata goes in JSON. UTF-8 BOM/CRLF invocation controls are recognized.

### Trusted state example

```json
{
  "session_id": "a-unique-host-session",
  "as_of": "2026-09-20",
  "goal": "Investigate the deployment failure",
  "latest_message": "yes please",
  "phase": "investigate",
  "next_action": "read",
  "worktree": "/absolute/path/to/this-session-worktree",
  "scope": {"project": "example", "environment": "staging"},
  "evidence": ["The latest check failed at the upload step"],
  "required_ids": [],
  "explicit_ids": [],
  "previous_ids": []
}
```

The host supplies and updates date, active goal, phase, next action and observations.
An acknowledgement does not erase the active task. Conversely, clear the goal when a
task ends; this library does not infer task boundaries or mutate session state.
`explicit_ids` means an actual explicit user selection, **not** a provider suggestion
or text extracted from a prompt. It cannot bypass source validity or scope.

### Reviewed metadata example

Keys are paths relative to the indexed root. Preserve IDs explicitly during renames.

```json
{
  "current-deployment.md": {
    "id": "project-memory:deploy-current",
    "summary": "Current staging deployment decision",
    "scope": {"project": ["example"], "environment": ["staging"]},
    "supersedes": ["project-memory:old-deployment.md"],
    "reviewed": true,
    "relationship_evidence": "Owner-approved decision recorded in the source",
    "verification": "checked against the recorded source revision"
  }
}
```

Supported lifecycle states are active, reference, disputed, superseded and archived.
Invocation policy is separately automatic or manual-only. Verification is separate
from both. Indexing an old file does not make its claim verified. No automatic ageing,
demotion, promotion, deletion or 'newest timestamp wins' rule exists. Dates are strict
ISO days, compared by code; expiry is inclusive. Scope dimensions are exact and missing
scope is not a wildcard. Dormant agency/client knowledge is not obsolete by default.

Relationships require reviewed metadata and a provenance explanation. New proposals
from the audit never become approved edges automatically. A stale record can lead to
its approved replacement even when the replacement does not share the query's words.
Cross-scope/future replacements do not retire current rules. Dangling edges, dependency
cycles and ambiguous/mixed chains fail visibly. Missing required/conflicting evidence
blocks active bundle emission rather than exposing an incomplete procedure.

## One budget across skills and memories

Export the ATC registry with its adapter, then combine it with the memory registry:

```sh
python "$ENGINE/context_router.py" combine \
  --registry atc-registry.json --registry memory-registry.json > combined.json
python "$ENGINE/context_router.py" route --registry combined.json \
  --roots roots.json --state state.json --budget-bytes 16000 > decision.json
```

`roots.json` explicitly maps each original namespace to an approved local root. It is
kept outside the index; no machine-specific absolute roots are embedded in a shared
registry. Duplicate namespaces, extra/missing root mappings and nested combined indexes
are refused. Cross-store dependencies/conflicts can be added through reviewed JSON via
`combine --relationships`. Combine uses the same identity, scope and lifecycle rules.

The source files remain canonical. Inventory changes and content-hash changes require
reindexing. **Rebuild after reviewed sidecar metadata changes too**: a JSON registry is
an immutable approval snapshot, not a live watcher of a separate sidecar. Deploy new
snapshots atomically; do not let agents edit a shared index in place. Keep user/client
stores separate until explicitly combining their approved roots and scopes.

## Modes, context lifetime and host integration

- **off**: no source or network reads; `CONTEXT_ROUTER_DISABLE=1` also disables routing.
- **shadow (default)**: selection IDs, source hashes, reasons and metrics only; no body
  injection, catalogue suppression or host configuration changes.
- **active (explicit)**: returns a reference bundle to a caller that controls context.
  It still cannot unload old conversation tokens, invoke a skill or authorize tools.

Budgets are **exact UTF-8 bytes of the rendered bundle including its framing**, not
claimed tokenizer counts. Procedures are indivisible; dependencies travel with them.
Protected overflow is reported and emits no active context. Attach a host tokenizer
and reserve space for the rest of the prompt before using any token-based claim; this
prototype deliberately offers no guessed hard token limit. `add_on_rebuild`, `retain`
and `retire_on_rebuild` describe a future host reconstruction, not edits to conversation
history. On blocked results, previous context is not recommended for retirement.
Do not remove user instructions, unresolved evidence or original records during
compaction. Re-read canonical records when rebuilding after a state transition.

A prompt hook is not a hook before every model call. The ATC adapter provides an opt-in
UserPromptSubmit **advisory**; it neither suppresses installed plugin catalogue entries
nor replaces the host's normal skill loader, tool restrictions or forked contexts.
A real per-call context builder should call this API at meaningful state transitions
and rebuild its own outgoing request. That integration is host-owned and not supplied
for arbitrary LLM products here. No catalogue or billed-token savings are claimed.

For in-process integrations use `Session(session_id)`, never one global shared Session.
The bounded in-memory cache includes registry contents, source versions, full trusted
state, scope, worktree, provider/model identity and budget. A narrow acknowledgement
normalization allows reuse only while the other state stays unchanged. Errors are not
cached. Separate CLI/hook processes deliberately have no shared disk cache; they do
not magically reuse an in-memory Session. The registry may be shared read-only; mutable
session state must not be shared across parallel sessions.

## Optional Jev: two independent consent gates

`--jev` explicitly enables the provider. A candidate additionally requires a reviewed
`public_summary` plus `egress_approved: true`. Ranking also requires `public_task` in
trusted state: write this as a deliberately sanitized task capsule, not a copied
transcript. No raw source body, path, ID, goal, evidence, or scope field is forwarded.
Opaque candidate keys map replies back locally. A defence-in-depth credential/email
screen checks complete approved content before any size handling; it is not a PII
classifier or a substitute for consent. The hook adapter itself has no outbound mode.

Set `TYPESAFE_API_KEY` locally; never place it in a repository, state JSON or PR. The
provider uses the documented `POST /v1/systemone` Noul schema and pinned `jev-1.13.0`.

The pin is required, not stylistic. Verified against the live API on 2026-09-21:
requesting `jev-1.13.0` returns `jev-1.13.0`, and requesting the alias `jev-latest`
*also* returns `jev-1.13.0` — the API echoes the resolved version, never the alias.
Because the provider asserts `response["model"] == self.model`, a provider permitted
to send `jev-latest` would raise `unexpected_model` on every live call. The
constructor's version regex is what prevents that. `tests/context_routing/` replays
the recorded responses, so this stops being an assumption the suite cannot check.

It makes at most one rank call, with at most 32 approved candidates, a 3-second socket
timeout, a 48,000-byte encoded payload cap and bounded response reads. TypeSafe
documents no byte, timeout or question-count limits; these are our own bounds,
deliberately stricter than the API. A full 32-candidate rank measured ~0.83 s against
the 3.0 s timeout on 2026-09-21 — one observation, not a latency guarantee. No redirects or
retries. No clipping that could conceal a warning. An optional semantic audit makes
at most five pair judgments per invocation, only on approved summaries, and requires
fresh source hashes. These are **proposals**, not truth determinations.

### Two verified limitations of the optional transport

Both were confirmed by running the code on 2026-09-21. Neither leaks anything and
neither blocks merge, because the transport is opt-in and both fail toward local
retrieval — but both are silent, which is the part worth knowing.

**Every HTTP failure arrives as the single word `transport_failure`.** A 401 (bad
key), a 422 (the body names the offending field), a 429 (rate limited) and a socket
timeout are indistinguishable to the operator; `raise ... from None` drops the
original traceback too. Confirmed live with a deliberately invalid key. This is
deliberate about not logging response bodies, and it does leak neither the key nor
the body — but it also means a misconfigured key and a throttled account look
identical. Diagnosing either currently requires editing the provider.

**The credential screen blocks ordinary sentences about credentials.** `screen_public`
is a regex guard, not a classifier, and the email pattern also matches SSH clone URLs.
Measured: `Authenticate with a Bearer token in the Authorization header.`,
`Clone with git@github.com:owner/repo.git before running.`, `Rotate the api_key: see
the vault runbook.` and `Never store a password = value in the repository.` are all
refused, while `Procedure for rotating database credentials in staging.` passes. The
refusal is per-request, so one such summary drops the whole ranking call to local
retrieval — and security-adjacent memories are exactly the ones most likely to trip it.
Erring toward refusal is the right default for an egress guard; the cost is reduced
Jev coverage, not exposure.

A strongly negative optional-group score can remove that whole group; uncertain or
unjudged groups retain local retrieval. The 0.25 negative threshold is an experimental
starting value, **not a calibrated correctness probability**. Required and conflict
records never depend on a provider score. Missing key, rate limits, malformed/partial
answers, unexpected model, oversized payload or timeout fall back to deterministic
retrieval. Missing usage remains null/unknown; a sent failed request may cost money.
A cache hit records no new provider attempt and does not reuse old token usage as new
spend. No provider response or exception body is written to a log.

## Evaluation and rollout

See [the evaluation protocol](context-routing-evaluation.md). The shipped offline
regressions exercise invariants, not real-world selection accuracy. Native-agent runs,
live Jev calibration, main-model cache effects, installed-host behaviour and subscription
value still require a frozen, owner-reviewed trial. Keep shadow mode until that trial
supports active use. ATC includes a scratch-only lean preview builder; it does not
install or change the full plugin, and its effect on native catalogue tokens is unmeasured.

Repository inspection also found README wording at v3.4 while the actual skill
is v3.5. This draft treats the actual canonical skill/source hash as authoritative; it
does not invent a new release version or rewrite historical documentation.

## Recommendation coverage

| Recommendation | Implementation / explicit gate |
|---|---|
| Shared engine, no extra loaded skill | This canonical module; ATC digest-pinned adapter |
| Validity separate from relevance | Reviewed lifecycle/scope/edges before provider |
| Local shortlist before paid model | Unicode-aware lexical retrieval; exact eligibility |
| Preserve dependencies and contradictions | Whole-group closure, protected evidence, visible overflow |
| Stale/superseded handling | Source census + hashes; contextual approved successor links |
| Maintenance and causal contradictions | Changed-record pair proposals; optional semantic comparison; human evidence review |
| One context budget | Combined explicit roots; exact rendered-byte budget |
| Per-turn task continuity | Trusted goal/phase/action/evidence; acknowledgement normalization |
| State/version-aware reuse | Session-local bounded cache, complete input key |
| Context accumulation | Rebuild deltas, not a false claim to erase loaded history |
| Privacy and fallback | Approved public capsule only; bounded optional transport; unknown usage preserved |
| Native selection baseline | External observation import; missing A/C arms remain not_run |
| Lean catalogue trial | ATC scratch builder; no install, promotion or measured savings claim |
| Production activation | Deliberately gated on actual host trials and owner review |

## Sources verified 2026-09-20, re-checked 2026-09-21

- TypeSafe API contract: https://docs.typesafe.ai/api
- Skill suggestion cookbook: https://docs.typesafe.ai/cookbooks/skill_suggestion
- Passage classification: https://docs.typesafe.ai/cookbooks/classifying_rag_passages
- Model limits: https://docs.typesafe.ai/model-jaggedness/jev-1.13
- Claude skills/invocation controls: https://code.claude.com/docs/en/skills
- Claude hook lifecycle: https://code.claude.com/docs/en/hooks
- Recent community fixes that informed the regressions:
  https://github.com/kerpopule/hermes-jev-skills/commit/b44bc8d5a08d46d82f09a537c3446b51d762a221
  https://github.com/lomeshdutta/skill-router/commit/328a44576780a85a6aaddd21f924d711898e6712

Implementation prepared by ChatGPT; as written, it performed no live provider request,
native-agent benchmark or automatic activation.

Jev research owned by Claude from 2026-09-21. Re-checked on that date: every URL above
resolves and supports what it is cited for, including both community commits. Real
authenticated calls were then made against the live API, which is what produced the
version-pin finding above and the recorded fixtures under `tests/context_routing/`.
The measured-versus-still-open split lives in one table in
[the evaluation protocol](context-routing-evaluation.md#jev-gate-what-is-now-measured-and-what-is-still-open);
it is the single place to look before enabling `--jev`. Native-agent benchmarking and
automatic activation remain not performed.
