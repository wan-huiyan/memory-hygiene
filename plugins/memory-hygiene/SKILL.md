---
name: memory-hygiene
description: "Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, and ADRs. Use this skill when: (1) the user asks to clean up, audit, or review their memory/lessons/ADRs, (2) MEMORY.md is approaching or exceeding the 200-line limit, (3) lesson files have grown large and may contain duplicates, (4) you notice ADR numbering conflicts, (5) memory files seem stale or contradicted by current code, or (6) the user says things like 'my memory is getting messy', 'clean up my lessons', 'deduplicate', 'review ADRs', 'memory audit'. Also proactively suggest running this after 10+ sessions on a project, or when MEMORY.md triggers a truncation warning."
---

# Memory Hygiene v3.3 — Audit & Cleanup

This skill audits Claude Code's persistent knowledge stores (axioms, MEMORY.md — both auto-memory and in-repo, memory topic files, lessons, phase templates, ADRs, and the project `docs/` taxonomy) for structural problems that degrade future session quality. It produces a structured report, gets user approval, then executes fixes.

v3.3 adds **label-table integrity audit** (§1i) and **project `docs/` taxonomy audit** (§1j). The 7-bucket taxonomy that `session-handoff` dispatches to is now defined here as source-of-truth — previously `session-handoff` referenced "memory-hygiene v3.1" for this but the definition lived nowhere. §1i catches fabricated code→label tables in `lessons.md` / `feedback_*.md` / `reference_*.md` that bypass the author-side gate `session-handoff` runs in its Phase 0.

v3.2 adds **in-repo `MEMORY.md` detection** (§1a2) — the A/B counterfactual harness (n=3, 2026-04-21) showed that in-repo `MEMORY.md` files (e.g., project-root `MEMORY.md` or `docs/MEMORY.md`) survive a `CLAUDE_CONFIG_DIR` clean env and drive measurable success on tasks that the `~/.claude/projects/*/memory/MEMORY.md` auto-memory file cannot. v3.1's §1a scanned only the auto-memory MEMORY.md, making the in-repo counterpart invisible to memory hygiene. v3.2 scans both and reports them as separate tiers in the audit output (T1 auto-memory and T1-repo).

v3.1 added **feedback lifecycle detection** (§1c2) — classifying each `feedback_*.md` file as Incorporated / Pending / Dormant / Superseded based on whether its rule has been promoted to axioms/lessons/templates — and emits a `feedback_incorporation_rate` metric for downstream consumers like `ecosystem-audit`.

v3.0 added phase template management, three-category axiom classification (Universal/Role/Phase), capacity ceiling enforcement, agency-aware staleness detection, and path-scoped rule auditing. Backed by research from cognitive science (Cowan 2001), LLM research (Liu et al. 2024 TACL, EMNLP 2025, Chroma Context Rot 2025), KM theory (Markus 2001), and SRE practice (Google SRE post-mortem framework). Full sources in `~/Documents/memory_hygiene_guide.md`.

## Why this matters

Claude Code loads MEMORY.md and CLAUDE.md at the start of every conversation. Two failure modes degrade session quality:

1. **Truncation**: MEMORY.md exceeding ~200 lines / 25KB is silently truncated — context lost without warning.
2. **Lost in the Middle** (Liu et al. 2024): Even within the context window, LLMs show ~20pp accuracy degradation for information positioned in the middle of long contexts due to U-shaped positional attention bias. A critical lesson at line 617 of a 1400-line file is effectively invisible — not because it was truncated, but because attention drops off.

This means bulk-loading large files (lessons.md, session archives) into context is worse than useless — it wastes tokens AND buries the important rules. The solution is a tiered architecture where only high-signal behavioral overrides occupy always-loaded context, and everything else is retrieved on demand via grep.

## When to run

- **On demand:** User explicitly asks for a memory cleanup, audit, or review
- **Proactively suggest** when you notice any of these signals:
  - MEMORY.md truncation warning in the system prompt
  - MEMORY.md has 150+ lines of inline content (not just index pointers)
  - A lessons file has 80+ lessons
  - You spot duplicate lesson numbers while reading lessons.md
  - Multiple ADR files share the same number prefix
  - A memory file references a function/file/library that no longer exists in the codebase

## The audit-then-fix workflow

### Phase 1: Discover

Read all persistent state files. Use parallel reads where possible.

#### 1a. MEMORY.md (auto-memory — T1)

Read the full auto-memory index at `~/.claude/projects/<project>/memory/MEMORY.md`. Note total line count and whether it contains inline content (session logs, architecture sections, decision tables) that should live in topic files.

#### 1a2. In-repo `MEMORY.md` (T1-repo) — NEW in v3.2

**Why this sub-check exists.** The A/B counterfactual harness (2026-04-21, n=3) showed that on Task 2 (schuh CausalPy regression), both clean and normal environments succeeded because the schuh repo has its own `MEMORY.md` at the project root with a prominent pointer to `docs/findings/causalpy_v04_wrapper_investigation.md`. This in-repo file survived the `CLAUDE_CONFIG_DIR=/tmp/...` clean env and carried the success. v3.1's §1a could not see it — it only knew about `~/.claude/projects/<project>/memory/MEMORY.md`.

The in-repo MEMORY.md is a distinct tier because it lives with the code, is version-controlled, and is visible to every session that `cd`s into the project (including clean-env and colleague-checkout sessions). The auto-memory MEMORY.md is user-local and disappears when `~/.claude/` is wiped.

**What to scan.** For the current project's working directory:

1. **Discover**: glob for any file named `MEMORY.md` (case-sensitive) under the project root.
2. **Exclude**: paths under `~/.claude/` (those are T1 auto-memory, not T1-repo), `.git/`, `node_modules/`, `__pycache__/`, `cache/`, `.venv/`, `venv/`.
3. **Include**: all remaining matches, regardless of depth (root `MEMORY.md`, `docs/MEMORY.md`, subproject `MEMORY.md` all count).
4. **Report each** with its relative path so the user can eyeball false positives (e.g., a vendored sub-project's `MEMORY.md`).

**Checks (same structural rules as §1a):**
- Line count ≤200 (hard limit 25KB) — truncation is the same risk whether in-repo or auto-memory.
- Entries are one-line pointers, not inline content (session logs, architecture sections, decision tables → extract to topic files).
- Links inside the index resolve: if an entry says `[foo](docs/foo.md)`, verify `docs/foo.md` exists.
- No frontmatter on `MEMORY.md` itself (it's an index, not a memory file).
- Linked target files have frontmatter (name / description / type) when they are memory-style topic files.

**Classification tier in reports.** Call it **T1-repo** to complement **T1** auto-memory. Example report header:

```
### Critical (breaks functionality)
- T1 (auto-memory) MEMORY.md: N lines — OK / truncating
- T1-repo MEMORY.md at <relative path>: N lines — OK / truncating / missing index links
- N in-repo MEMORY.md files found (list paths)
```

**If both tiers exist.** Flag any rule that is duplicated verbatim between the auto-memory MEMORY.md and an in-repo MEMORY.md. The two serve different audiences (T1 is user-private; T1-repo is teammate-visible), but a verbatim copy usually means the user meant to keep it in one place and forgot to delete the other. Ask, don't auto-merge.

**If neither exists.** The auto-memory MEMORY.md is created by Claude Code; its absence is odd but not a hygiene failure. The in-repo MEMORY.md is optional — its absence is a missed opportunity but not a defect. Do not auto-create either.

**Edge case — monorepo.** A monorepo may legitimately have multiple in-repo `MEMORY.md` files (one per sub-project). Report all, scope each linked-file check to the containing sub-project.

#### 1b. Tiered loading check

Claude Code's memory should follow a tiered architecture. The key insight (backed by Liu et al. 2024 "Lost in the Middle") is that bulk-loading large files into context is counterproductive — information in the middle of long contexts is effectively ignored even when not truncated. Check that content lives at the right tier:

| Tier | What | Budget | Loaded when | Contains |
|------|------|--------|-------------|----------|
| **T0: Axioms** | `axioms.md` | **10-12 items** (Cowan cap) | Every session start | Behavioral overrides: Universal + Role categories only |
| **T0: Config** | `CLAUDE.md` | ~70 lines, always loaded | Every session start | Workflow rules, retrieval strategy |
| **T1: Index (auto-memory)** | `~/.claude/projects/<project>/memory/MEMORY.md` | ~40-80 lines (hard limit: 200 / 25KB) | Every session start (auto-injected) | One-line pointers to topic files in auto-memory |
| **T1-repo: Index (in-repo)** | `<project>/MEMORY.md` or `<project>/docs/MEMORY.md` (any in-repo `MEMORY.md`) | ~40-80 lines (hard limit: 200 / 25KB) | Every session that `cd`s into project; survives `CLAUDE_CONFIG_DIR` clean env | One-line pointers to in-repo topic/findings/runbook files |
| **T1.5: Phase rules** | `.claude/rules/phase-*.md` | ~5 rules per file | **Auto-loads when matching files are touched** | Phase-specific rules with `paths:` YAML frontmatter |
| **T2: Topic files** | feedback_*.md, reference_*.md | ~50 lines each | Loaded on demand | Workflow reminders, key references |
| **T3: Archives** | lessons.md, sessions_archive.md, handoffs/ | Unlimited | **grep only, never bulk-read** | Full history, all lessons, session logs |

**Global phase templates** live at `~/.claude/templates/phase_*.md` — reusable across projects. Copy into a project's `.claude/rules/` with `paths:` frontmatter to auto-activate.

#### Axiom classification (three categories)

| Category | Definition | Stays in axioms.md? | Example |
|----------|-----------|---------------------|---------|
| **Universal** | Applies regardless of project or phase | Yes — always | "Never fabricate data", "Bash PATH is stripped" |
| **Role** | Applies to all projects for this user's role | Yes — until role changes | "No jargon in client materials" (agency DS) |
| **Phase** | Only relevant during specific project phases | **No — move to phase templates** | "Current-vs-planned boundary" (data sourcing) |

#### Axiom promotion criteria (ALL three must hold)

1. **Default wrong** — A fresh Claude session would get this wrong without the lesson
2. **Silent failure** — No test, linter, or CI check catches it
3. **Recent or structural** — Fires regularly OR is structurally guaranteed to recur across projects

#### Axiom demotion triggers (ANY one sufficient)

1. **Dormant** — Not relevant in 20+ sessions (measured across ALL user projects for agency workers, not just the current one)
2. **Caught by tooling** — A test, CI check, or structural change now catches it
3. **Subsumable** — Can be merged with a related axiom (chunking to stay under cap)

#### Axiom capacity enforcement

- **Hard cap: 12 items** (Cowan 2001: 3-4 chunks × 3 items/chunk)
- Every new promotion past 12 requires a demotion
- Two-incident rule (Google SRE): a lesson that surfaces in 2+ sessions without being queried should be promoted

#### Phase detection for staleness

When auditing axiom staleness, detect the user's work pattern from `user_role.md`:
- **Single long project** → measure staleness within the project (session count)
- **Agency / multi-client** → measure staleness across the user's portfolio (calendar time). A rule dormant in THIS project for 30 sessions may fire immediately in the NEXT client engagement.

Classify dormant axioms as:
- **KEEP** — Universal or Role, still relevant
- **DEMOTE** — Truly irrelevant, move to T3 lessons.md
- **PHASE** — Phase-specific, move to `~/.claude/templates/phase_*.md` and project `.claude/rules/`

**CLAUDE.md retrieval strategy audit**: Check that the session start checklist says:
- Load `axioms.md` (not bulk-read `lessons.md`)
- Read project `MEMORY.md` index
- grep T3 archives for keywords relevant to the current task
- grep before claiming something is impossible

Flag if CLAUDE.md still says "read lessons.md" — that's the anti-pattern this tier system replaces.

Flag content at the wrong tier:
- A behavioral override buried in lessons.md line 600+ → should be promoted to T0 (axioms.md)
- A 500-line entry in a topic file → should be T3 (archive)
- A critical workflow reminder buried in sessions_archive → should be promoted to T1 (MEMORY.md pointer) or T2 (its own topic file)
- Inline session logs in MEMORY.md → should be extracted to T3
- CLAUDE.md saying "read lessons.md" → should be "grep lessons.md"

#### 1b2. Phase templates and path-scoped rules

Check for the existence and correctness of phase-specific rules:

1. **Global templates**: Glob `~/.claude/templates/phase_*.md`. List available templates.
2. **Project path-scoped rules**: Glob `.claude/rules/phase-*.md` (or `.claude/rules/*.md` with `paths:` frontmatter). For each:
   - Does the `paths:` glob actually match files in the current project? (dead globs = unused rules)
   - Is the content consistent with the global template it was copied from?
3. **Axiom-to-template migration candidates**: For each axiom in `axioms.md`, classify as Universal/Role/Phase. Flag Phase axioms for migration to templates.
4. **Axiom capacity check**: Count items in `axioms.md`. If >12, flag as over Cowan cap and identify merge/demotion candidates.

#### 1c. Memory topic files
Glob `~/.claude/projects/<current-project>/memory/*.md` (excluding MEMORY.md and lessons.md). For each file, read the frontmatter (name, description, type). Check:
- Is it referenced from MEMORY.md? (orphan check)
- Is its `type` field valid? (must be: user, feedback, project, reference)
- Does its content overlap substantially with another memory file?

#### 1c2. Feedback lifecycle (incorporation status)

Memory files with `type: feedback` are meant to capture a rule or insight that should eventually be **promoted** (to `axioms.md` or `lessons.md`) or **encoded** into a phase template. Until that happens, they are loose notes competing for attention with already-promoted rules. This sub-check classifies every `feedback_*.md` file by where its rule currently lives.

**For each `feedback_*.md` file** in `~/.claude/projects/<project>/memory/`:

1. **Extract the core rule.** Parse the body for a `**Rule:**` section (per the file-format convention) or, if absent, take the first bolded sentence or the first sentence after the `description:` frontmatter.
2. **Extract key identifiers** from the rule: proper nouns, file/skill names, unique noun phrases (≥ 2 content words). Drop stopwords.
3. **Search the promotion surfaces:**
   - `~/.claude/axioms.md`
   - `~/.claude/lessons.md` and `~/.claude/projects/<project>/memory/lessons.md`
   - `~/.claude/templates/phase_*.md` and the project's `.claude/rules/*.md`
4. **Classify:**

| Status | Criterion | Action |
|---|---|---|
| **Incorporated** | ≥ 1 identifier found verbatim in a promotion surface | Keep feedback file as provenance; OK |
| **Pending** | Written within last 30 days, no match yet | Allow ripening |
| **Dormant** | > 30 days old, no match, file unchanged in 30+ days | Candidate: demote to lessons.md or delete |
| **Superseded** | Another feedback file with overlapping identifiers was written later and contradicts this one | Flag conflict; ask user which rule wins |

5. **Compute `feedback_incorporation_rate`** = `incorporated_count / (incorporated + dormant + superseded)`. Exclude Pending from the denominator — those haven't had time to be incorporated yet.

**Report signals (surface in Phase 2):**
- Total feedback files; breakdown by status
- Dormant files (>30 days, unreferenced) — list with age and core rule
- Superseded pairs — list both files side-by-side for user resolution
- Incorporation rate (excluding Pending)

**Why this matters:** feedback files that never get promoted become a hidden tier of rules that aren't in axioms (not always-loaded), aren't in lessons (not grep-findable under the standard retrieval pattern), and aren't in templates (not phase-activated). They're effectively invisible after the session that created them — the same "Lost in the Middle" (Liu et al. 2024) logic that motivates the whole tiered architecture.

**Phase 4 fixes for this sub-check:**
- **Dormant** → with user approval, move the rule to `lessons.md` (T3) under the appropriate category, then delete the feedback file OR keep it with a `status: archived` frontmatter addition.
- **Superseded** → present both rules side-by-side, ask the user which wins, then merge or delete the loser.
- **Pending** → no action; re-check on next audit.

#### 1d. Staleness detection (inspired by [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill) and [Zep](https://arxiv.org/abs/2501.13956))

Beyond simple age checks, look for these staleness signals:
- **Broken references**: Memory mentions a file path, function name, or ADR number that no longer exists in the codebase. Grep the project for referenced identifiers.
- **Relative dates**: Flag phrases like "last week", "recently", "yesterday", "a few days ago" that should be absolute dates. Auto Dream handles this but only on its trigger schedule.
- **Codebase contradictions**: Memory says "uses library X" but `package.json`/`requirements.txt` says otherwise. Memory says "function Y exists in file Z" but it's been renamed or removed.
- **Contradicted lessons**: A project lesson says "always do X" but a global lesson (written later) says "don't do X" — flag the conflict for resolution.

#### 1e. Project lessons
Read `~/.claude/projects/<current-project>/memory/lessons.md`. Extract all lesson numbers and titles. Check for:
- Duplicate numbers (same `### N.` appearing twice)
- Non-sequential numbering (gaps are fine; repeats are not)
- Lessons that substantially duplicate a global lesson

#### 1f. Global lessons
Read `~/.claude/lessons.md`. Same duplicate/numbering checks. Also cross-reference with project lessons to find content that exists in both places.

#### 1g. Session compression check (inspired by [OpenViking](https://github.com/volcengine/OpenViking) auto-compression and [Cog](https://github.com/marciopuga/cog) glacier pattern)

- Detect session files >30 days old AND >50 lines AND not referenced from MEMORY.md → flag for compression (keep key outcomes, remove commit hashes, file lists, resolved deferred items)
- Detect overlapping session files (multiple sessions covering the same subsystem) → suggest merging into a consolidated summary
- When sessions_archive.md exceeds 200 lines → suggest splitting into recent (last 5 sessions) + older

#### 1h. ADRs (enhanced, inspired by [MADR 4.0](https://adr.github.io/madr/))

Glob `docs/decisions/*.md` (or wherever the project keeps ADRs). Check:
- **Duplicate numbers**: Two files with same `NNNN-` prefix
- **Internal mismatch**: Number inside the file not matching the filename
- **Copy/paste duplicates**: Files with identical or near-identical content
- **Missing bidirectional links**: If ADR-B says "Supersedes ADR-A", does ADR-A say "Superseded by ADR-B"?
- **Missing Confirmation section**: MADR 4.0 recommends "how do we verify this was implemented?"
- **Suggest index file**: When >10 ADRs exist, suggest creating `docs/decisions/README.md` with a sortable table (ID, Title, Status, Domain, Date)
- **Gap stubs**: If a number is missing in the sequence (e.g., ADR-0014 doesn't exist), suggest a stub with `Status: Skipped`
- **PR back-links**: ADRs should reference the implementing PR in a `## Links` section

#### 1i. Label-table integrity (NEW in v3.3)

**Why.** Handoff docs and lessons sometimes contain code → human-label tables (Salesforce status codes, HTTP statuses, enum descriptions). When these labels are fabricated by a predecessor session, downstream sessions treat them as authoritative. `session-handoff` Phase 0 gates this at the handoff-doc author side via `scripts/label_audit.py`; this sub-check catches fabricated labels that already landed in `lessons.md`, `feedback_*.md`, or `reference_*.md` before the gate existed, or via in-memory batch edits that bypassed the hook.

**Scan targets:**
- `~/.claude/lessons.md`
- `~/.claude/projects/<project>/memory/lessons.md`
- `~/.claude/projects/<project>/memory/feedback_*.md`
- `~/.claude/projects/<project>/memory/reference_*.md`

**Detect.** Any markdown table whose first column is a short code (≤4 chars, ALL-CAPS or numeric) and second column is a sentence-style description, where the row lacks an inline tag (`[verified: <path>:<line>]` or `[HYPOTHESIS]`).

**Tool.** Invoke `~/.claude/skills/session-handoff/scripts/label_audit.py` against each scan target. If the skill is absent, log "label_audit not installed" and continue (graceful degrade — same pattern session-handoff uses for the reverse-lint call).

**Never auto-tag.** Surface candidates with file:line and let the user verify against the authoritative source (axioms.md § Authoritative Labels). Tagging a guess as `[verified: ...]` is worse than leaving it untagged.

#### 1j. Project `docs/` taxonomy audit (NEW in v3.3)

**Why.** `session-handoff` dispatches output across a canonical 7-bucket `docs/` taxonomy. Without a periodic audit, projects accumulate loose files at `docs/*`, non-canonical subdirs, or singular/plural duplicates (`handoff/` + `handoffs/`). This sub-check is the source-of-truth definition that `session-handoff` references.

**The canonical 7 buckets:**

| # | Bucket | Contains |
|---|--------|----------|
| 1 | `docs/decisions/` | ADRs (`NNNN-kebab-case.md`) |
| 2 | `docs/runbooks/` | Rerun / retrain / operational procedures |
| 3 | `docs/analysis/` | Findings, diagnostics, discoveries, exploratory write-ups |
| 4 | `docs/references/` | Schemas, data dictionaries, project-convention docs |
| 5 | `docs/reviews/` | Review-panel output, peer review, audits |
| 6 | `docs/handoffs/` | Session handoffs + next-session prompts |
| 7 | `docs/deliverables/` | External-facing artifacts (client drafts, PDFs, decks) — add a `.provenance.md` sibling if generated |

**Reserved top-level file:** only `docs/README.md`.
**Permitted 8th directory:** `docs/plans/` for forward-looking artifacts (`future_sessions_plan.md`). Flag only if it contains backward-looking content that belongs in `analysis/` or `handoffs/`.
**Exclude entirely:** `__pycache__/`, `.py` scripts (belong in `scripts/`), `.DS_Store`.

**Checks:**
- **Loose files at `docs/*`** — anything other than `README.md` directly under `docs/`
- **Non-canonical subdirs** — e.g., `docs/findings/` → should be `docs/analysis/`; `docs/handoff/` → `docs/handoffs/`
- **Plural/singular duplicates** — `handoff/` + `handoffs/`, `decision/` + `decisions/`
- **Bucket-typed content in the wrong place** — an ADR-style file in `docs/analysis/`, a review report in `docs/findings/`

**Migration support.** If `docs/` has substantially drifted, offer a `--migrate` flag that proposes (does not execute) a move plan:

```
docs/findings/X.md        → docs/analysis/X.md
docs/handoff/sN.md        → docs/handoffs/sN.md
docs/foo_at_root.md       → docs/<inferred-bucket>/foo.md
```

User approves moves one at a time. Use `git mv` to preserve history. Never auto-rename. After moves, update any handoff doc, plan, or skill that hard-codes the old path (run `doc-freshness-reverse-lint` on the migration commit to catch references).

Keeping this taxonomy aligned with `session-handoff`'s dispatch means a session's output lands where the next session's audit expects to find it.

### Phase 2: Report

Present findings as a structured audit report. Group by severity:

```
## Memory Hygiene Audit

### Critical (breaks functionality)
- T1 (auto-memory) MEMORY.md is N lines (limit: ~200) — truncation is active
- T1-repo MEMORY.md at <relative path> is N lines — truncation/missing links
- N in-repo MEMORY.md files found (list paths; flag any under suspicious dirs)
- N orphaned memory files not indexed in MEMORY.md
- axioms.md missing or not referenced from CLAUDE.md session start checklist
- CLAUDE.md says "read lessons.md" instead of "grep lessons.md" (bulk-load anti-pattern)

### Staleness
- N memory files with broken references (list specific references)
- N relative dates that should be absolute
- N codebase contradictions (memory says X, code says Y)
- N contradicted lessons between global and project

### Duplicates
- Global lessons: N number collisions (list them)
- Project lessons: N number collisions (list them)
- Cross-file: N lessons duplicated between global and project (list them)
- ADRs: N number collisions (list them)

### Tiering
- N items at wrong tier (list with current/recommended tier)
- N lessons in lessons.md that qualify for axioms promotion (behavioral overrides)
- N session files flagged for compression
- sessions_archive.md: N lines (suggest split if >200)

### Axioms (target: 10-12 items, Cowan cap)
- axioms.md: exists/missing, N items (target: ≤12)
- Classification: N Universal / N Role / N Phase
- N Phase axioms that should migrate to `~/.claude/templates/phase_*.md`
- N axioms flagged for demotion (dormant / caught by tooling / subsumable)
- N merge candidates to reach capacity cap
- CLAUDE.md retrieval strategy: correct/needs update

### Phase Templates
- `~/.claude/templates/`: N template files found
- `.claude/rules/`: N path-scoped rule files, N with dead `paths:` globs
- N axioms that should be Phase templates instead of always-loaded
- Suggestion: create missing templates for common project phases

### Feedback Lifecycle (§1c2)
- N feedback files total: N Incorporated / N Pending / N Dormant / N Superseded
- Incorporation rate (excluding Pending): X%
- Dormant files (list with age and core rule)
- Superseded pairs (list for user resolution)

### ADR Best Practices
- N missing bidirectional links
- N ADRs without Confirmation section
- Index file: exists/missing (with N total ADRs)
- N sequence gaps without stubs

### Label-Table Integrity (§1i)
- N candidate fabricated-label rows across lessons / feedback / references
- Files affected with line refs (do not propose auto-tags)
- `label_audit.py` available: yes / no

### Project `docs/` Taxonomy (§1j)
- N loose files at `docs/*` (list)
- N non-canonical subdirs (list with suggested target bucket)
- N plural/singular duplicates
- N items of bucket-typed content in the wrong bucket
- Migration plan ready / not needed

### Recommendations
- For each issue: what to do, files affected, estimated impact
```

For cross-file duplicates (global vs project lessons), the decision of where to keep the lesson matters:
- **Keep in global** if the lesson applies to any project using the same tools/methods
- **Keep in project** if hyper-specific to this project's data, configuration, or codebase
- **Always ask the user** when unsure — a lesson appearing in only one project today doesn't mean it's project-specific. Consider the user's role: a data scientist doing causal inference across clients should keep causal inference lessons global even if they only appear in one project so far.

### Phase 3: Get approval

After presenting the report, ask the user which fixes to proceed with. Respect their decisions — they may want to keep some "duplicates" that serve different audiences, or skip renumbering if they reference lesson numbers in external docs.

### Phase 4: Execute fixes

Apply approved changes. For each fix type:

**MEMORY.md bloat:**
- Extract inline content into dedicated topic files with proper frontmatter
- Rewrite MEMORY.md as a concise index (~40 lines) with one-line entries
- Group entries under semantic sections (Workflow, Development, Analysis, References, History)

**Orphaned memory files:**
- Add missing files to MEMORY.md under the appropriate section
- Or, if clearly stale/superseded, confirm deletion with the user

**Stale memory files:**
- Update broken references to current names
- Convert relative dates to absolute dates
- Flag codebase contradictions for user resolution — never auto-delete
- Present contradicted lessons side-by-side for the user to resolve

**Lesson deduplication:**
- For number collisions within a file: suffix the duplicate (e.g., `### 41b.`) or merge if content overlaps
- For cross-file duplicates: keep the better-written version in the appropriate location, remove the other
- When merging, preserve unique details from both versions
- Do NOT renumber all lessons sequentially — that would break external references. Only fix collisions.

**Session compression:**
- Compress flagged session files: keep key outcomes, remove commit hashes, resolved deferred items, detailed file lists
- Merge overlapping sessions into a consolidated summary
- Split oversized archives into recent + older

**ADR fixes:**
- Keep the first file at each duplicate number; give subsequent files the next available number
- Update the ADR number in the file's title line to match the new filename
- Add bidirectional links where missing (Supersedes/Superseded by)
- Delete obvious duplicates (same content, different filenames) after user confirmation
- Create index file if >10 ADRs and none exists
- Create gap stubs if the user approves

**Axiom management:**
- For items classified as DEMOTE: move to `lessons.md` (T3), update search keywords, remove from `axioms.md`
- For items classified as PHASE: move to `~/.claude/templates/phase_*.md` (create template if it doesn't exist), add to project `.claude/rules/` with appropriate `paths:` glob, remove from `axioms.md`
- For merge candidates: combine related axioms into a single more general rule, preserving the key insight from each
- After changes: verify axiom count is ≤12, verify all Phase items have matching path-scoped rules

**Phase template management:**
- If `~/.claude/templates/` doesn't exist: create it and populate with standard phase templates (onboarding, data sourcing, analysis, deliverables, code review)
- If project `.claude/rules/` is empty: suggest copying relevant templates with `paths:` frontmatter matching the project's directory structure
- If path-scoped rules have dead globs (no matching files): update globs or suggest removal
- For new projects: suggest `@import` of the most relevant phase template in project CLAUDE.md

**Label-table tagging (§1i):**
- For each flagged row: present the row + ask the user for the authoritative source (axioms.md § Authoritative Labels has the criteria).
- If confirmed: add `[verified: <repo-relative-path>:<line>]` after the description.
- If unverifiable: add `[HYPOTHESIS]` so downstream sessions know to re-probe.
- Never auto-tag — tagging a guess as `verified` is worse than leaving it untagged.

**Taxonomy migration (§1j):**
- Surface the proposed move plan (from `--migrate` dry-run). Execute moves with `git mv` so history is preserved. Run one bucket at a time.
- After each move, run `doc-freshness-reverse-lint` on the migration commit to catch references in handoff docs, plans, or skills that hard-code the old path.
- Verify `session-handoff` would dispatch the same content to the new location (the canonical taxonomy is defined in §1j).

**Cross-project scope review** (inspired by [OpenViking](https://github.com/volcengine/OpenViking) hierarchical context):
- **Promotion**: If a project lesson appears in 3+ projects, suggest moving to global
- **Scope review**: Flag global lessons that currently appear in only one project — but always ask the user before suggesting any move. Present context: "This lesson currently appears only in [project]. Given your role, should it stay global for future projects?" Never auto-demote.

### Phase 5: Verify

After executing fixes:
- Confirm MEMORY.md line count is under 200
- Confirm all memory files are indexed
- Confirm no duplicate lesson numbers remain
- Confirm all ADR numbers are unique
- Check no new broken references were introduced by the fixes
- Present a summary table: before/after counts

## Writing guidelines (quality gate)

Inspired by [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill)'s three-question quality gate. Before writing any new memory file, apply these checks:

1. **Would forgetting this cause a bug or repeated mistake?** If no, it probably doesn't need to be a memory.
2. **Is this project-specific and not derivable from code or git history?** Code patterns, architecture, and file paths can be re-discovered by reading the codebase. Only store things that would be lost.
3. **Does it already exist in another memory file?** Check before writing. If partial overlap, merge with the existing entry rather than creating a duplicate.

## File format conventions

### MEMORY.md
- No frontmatter. Just a markdown title + grouped sections of one-line links.
- Each entry: `- [Display name](filename.md) — brief description under ~150 chars`
- Target: ~40 lines total

### Memory topic files
```yaml
---
name: Short descriptive name
description: One sentence explaining what this memory captures and when it's relevant
type: user|feedback|project|reference
---

Body content in markdown. For feedback/project types, structure as:
- Lead with the rule/fact
- **Why:** explanation
- **How to apply:** guidance
```

### Lessons files
```markdown
### N. Title (optional session reference like S42)
**Pattern:** What happened / what was observed
**Rule:** The corrective behavior going forward
```

### ADRs
- Filename: `NNNN-kebab-case-title.md` (zero-padded 4 digits)
- Title line: `# ADR-NNNN: Title` (number matches filename)
- Required sections: Status, Context, Decision
- Recommended: Confirmation ("how do we verify this was implemented?")
- Optional: Alternatives Considered, Consequences, Revert Criteria, Links (implementing PR)
- Bidirectional links: If superseding another ADR, update both files
