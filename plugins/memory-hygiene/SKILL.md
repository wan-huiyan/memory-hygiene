---
name: memory-hygiene
description: "Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, ADRs, and project docs/ directories. Use this skill when: (1) the user asks to clean up, audit, or review their memory/lessons/ADRs, (2) MEMORY.md is approaching or exceeding the 200-line limit, (3) lesson files have grown large and may contain duplicates, (4) you notice ADR numbering conflicts, (5) memory files seem stale or contradicted by current code, (6) the user says things like 'my memory is getting messy', 'clean up my lessons', 'deduplicate', 'review ADRs', 'memory audit', or (7) a project's docs/ directory has drifted — loose files at docs/*.md, duplicate folders (e.g. handoff/ AND handoffs/), subdirs outside a canonical taxonomy, or staleness. Also proactively suggest running this after 10+ sessions on a project, or when MEMORY.md triggers a truncation warning."
---

# Memory Hygiene v3.1 — Audit & Cleanup

This skill audits Claude Code's persistent knowledge stores (axioms, MEMORY.md, memory topic files, lessons, phase templates, and ADRs) for structural problems that degrade future session quality. It produces a structured report, gets user approval, then executes fixes.

v3.0 adds phase template management, three-category axiom classification (Universal/Role/Phase), capacity ceiling enforcement, agency-aware staleness detection, and path-scoped rule auditing. Backed by research from cognitive science (Cowan 2001), LLM research (Liu et al. 2024 TACL, EMNLP 2025, Chroma Context Rot 2025), KM theory (Markus 2001), and SRE practice (Google SRE post-mortem framework). Full sources in `~/Documents/memory_hygiene_guide.md`.

v3.1 adds a peer workflow — **docs/ taxonomy audit** — that applies the same audit → report → approve → migrate → verify discipline to a project's `docs/` directory. Memory hygiene keeps Claude's context clean; docs hygiene keeps the human-readable project knowledge base navigable. Both degrade over time without active curation.

## Why this matters

Claude Code loads MEMORY.md and CLAUDE.md at the start of every conversation. Two failure modes degrade session quality:

1. **Truncation**: MEMORY.md exceeding ~200 lines / 25KB is silently truncated — context lost without warning.
2. **Lost in the Middle** (Liu et al. 2023): Even within the context window, LLMs show >30% accuracy degradation for information positioned in the middle of long contexts due to U-shaped positional attention bias. A critical lesson at line 617 of a 1400-line file is effectively invisible — not because it was truncated, but because attention drops off.

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
  - A project's `docs/` has 20+ loose `.md` files directly at `docs/*.md`
  - A project's `docs/` has subdirs outside the canonical 7-bucket taxonomy (see docs workflow below)
  - A project's `docs/` has singular/plural folder duplicates (e.g. `handoff/` AND `handoffs/`)
  - A project's `docs/` contains `__pycache__/`, `.py` scripts, or other non-doc artifacts

## The audit-then-fix workflow

### Phase 1: Discover

Read all persistent state files. Use parallel reads where possible.

#### 1a. MEMORY.md
Read the full index. Note total line count and whether it contains inline content (session logs, architecture sections, decision tables) that should live in topic files.

#### 1b. Tiered loading check

Claude Code's memory should follow a tiered architecture. The key insight (backed by Liu et al. 2023 "Lost in the Middle") is that bulk-loading large files into context is counterproductive — information in the middle of long contexts is effectively ignored even when not truncated. Check that content lives at the right tier:

| Tier | What | Budget | Loaded when | Contains |
|------|------|--------|-------------|----------|
| **T0: Axioms** | `axioms.md` | **10-12 items** (Cowan cap) | Every session start | Behavioral overrides: Universal + Role categories only |
| **T0: Config** | `CLAUDE.md` | ~70 lines, always loaded | Every session start | Workflow rules, retrieval strategy |
| **T1: Index** | `MEMORY.md` | ~40-80 lines (hard limit: 200 / 25KB) | Every session start | One-line pointers to topic files |
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

### Phase 2: Report

Present findings as a structured audit report. Group by severity:

```
## Memory Hygiene Audit

### Critical (breaks functionality)
- MEMORY.md is N lines (limit: ~200) — truncation is active
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

### ADR Best Practices
- N missing bidirectional links
- N ADRs without Confirmation section
- Index file: exists/missing (with N total ADRs)
- N sequence gaps without stubs

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

---

# docs/ taxonomy audit workflow (v3.1)

A peer workflow to memory-hygiene. Applies the same audit → report → approve → migrate → verify discipline to a project's `docs/` directory. Produces a human-readable audit report; **never moves files automatically**. A separate `--migrate` pass generates a feature branch with bulk `git mv` commands for human review.

## When to run the docs workflow

Trigger on any of:
- `docs/` has 20+ loose `.md` files directly at `docs/*.md`
- Subdirs exist outside the 7-bucket canonical taxonomy
- Singular/plural folder duplicates (`handoff/` AND `handoffs/`, `review/` AND `reviews/`)
- `__pycache__/`, `.py`, `.DS_Store`, or other non-doc artifacts in `docs/`
- User says "my docs is a mess", "audit docs", "reorganize docs"

## The 7-bucket canonical taxonomy

Every file in `docs/` belongs in exactly one of these buckets. Subdirs outside this list are violations. Top-level `.md` files (other than `README.md`) are violations.

| # | Bucket | Contains | Common absorbs |
|---|--------|----------|----------------|
| 1 | `decisions/` | Go/no-go, architecture choices, ADRs, tradeoffs | `go_no_go*.json`, `v5_vs_v4_*.md`, `architecture/`, `design/`, `NNNN-*.md` |
| 2 | `runbooks/` | Operational how-tos, retrain procedures, rerun guides, QA | `retrain_requests/`, `rerun-guide.md`, `qa/`, `validation/` |
| 3 | `analysis/` | Exploratory analyses, findings, investigations, diagnostics | `analysis_*.md`, `findings/`, `diagnostics/`, `discovery_*.md`, `overnight/`, `brainstorm_*.md` |
| 4 | `references/` | Schemas, dictionaries, API refs, project conventions | `data_dictionary.md`, `bq_*.md`, `sf_*.md`, `snowflake_*.md`, `*_reference.md`, status-code docs |
| 5 | `reviews/` | Review-panel reports, peer reviews, audits | `review_*.md`, `next_*.md`, `audits/`, `*_audit_report.md` |
| 6 | `handoffs/` | Session handoffs, plans, next-steps, tickets, issues | `handoff/`, `handoffs/`, `plans/`, `tickets/`, `issues/`, `next_step_*.md`, `session_*_handoff.md` |
| 7 | `deliverables/` | External-facing artifacts, client drafts, published outputs | `client_drafts/`, `delivery/`, `site/`, `*.pdf`, `*.pptx`, `*.xlsx`, published `.html` |

**Reserved top-level file**: only `docs/README.md` (index). No other loose files.

**Exclude from `docs/` entirely**: `__pycache__/` (add to `.gitignore`), `.py` scripts (move to `scripts/`), `.DS_Store`.

## Phase 1: Survey

Walk the target `docs/` directory. For every file and subdir, classify it.

### 1a. Inventory
- Glob all files under `docs/` recursively. Record full path, extension, size, mtime.
- List all subdirs at depth 1. Flag any not in the 7-bucket list.
- List all loose files at `docs/*.{md,json,pdf,pptx,xlsx,html}`. Flag them.

### 1b. Classification heuristic

Apply in order — first match wins:

1. **Filename regex** (fastest, most reliable):
   - `^\d{4}-.*\.md$` → `decisions/` (ADR convention)
   - `^go_no_go` | `^v\d+_vs_v\d+` → `decisions/`
   - `^analysis_` | `^discovery_` | `^brainstorm_` → `analysis/`
   - `^review_` | `_audit(_report)?\.md$` | `^next_(stage_|step_)` → `reviews/`
   - `^session[_-]?\d+.*handoff` | `_handoff\.md$` | `_prompt\.md$` | `^plan_` → `handoffs/`
   - `^retrain_` | `^rerun` | `^(run|qa|validate)_` | `.*_guide\.md$` → `runbooks/`
   - `^(bq|snowflake|data|schema)_` | `_dictionary\.md$` | `_reference\.md$` → `references/`
   - `\.(pdf|pptx|xlsx|docx)$` or `^client_` → `deliverables/` (unless filename matches a reference pattern like `*_dictionary.xlsx`)

2. **Subdir hint**: If the file is already inside a subdir (e.g. `architecture/foo.md`), map the subdir to its bucket via the "Common absorbs" column, then propose the new path preserving the filename.

3. **Content peek** (fallback — read first 50 lines):
   - `## Status` + `## Decision` headers → `decisions/`
   - `## Findings` or `## Methodology` → `analysis/`
   - "handoff", "next session", "resume work" language → `handoffs/`
   - "retrain", "rerun", "how to run" → `runbooks/`
   - Tables of schemas/fields/columns with no narrative → `references/`
   - Mostly prose addressed to an external reader → `deliverables/`

4. **Unclassifiable**: mark as `UNKNOWN` and surface to the user in the report.

### 1c. Violation detection

Flag:
- **Loose files**: any non-`README.md` file at `docs/*` depth 1
- **Non-canonical subdirs**: subdirs not in the 7-bucket list (e.g. `site/`, `tickets/`, `validation/`)
- **Singular/plural duplicates**: pairs like `handoff/` + `handoffs/`, `review/` + `reviews/`, `plan/` + `plans/`
- **Non-doc artifacts**: `__pycache__/`, `.py`, `.DS_Store`, `.pyc`, `.ipynb_checkpoints/`
- **Case duplicates**: `Handoffs/` alongside `handoffs/`
- **Version ladders**: multiple files like `foo_v2.md`, `foo_v25.md`, `foo_v26.md` — propose keeping latest in bucket, archiving earlier to `<bucket>/archive/`

### 1d. Staleness detection

For each `.md` file, compute staleness signals:
- **Age**: mtime older than 90 days
- **Orphan**: no inbound markdown-link references from `docs/README.md` or any other `.md` file in the project (grep `](.*<filename>)`)
- **Superseded**: a file `foo_vN.md` exists with N > this file's version suffix
- **Reference rot**: file mentions a function/file path (regex `\w+/[\w/]+\.py`) that no longer exists in the project — grep to verify

Flag as "candidate stale" if 2+ signals hit. **Never auto-delete**. User reviews.

### 1e. Cross-cutting checks

- `analysis_principles.md` (or similar read-me-first normative doc): propose `references/` as primary home. Surface short normative rules as candidates for promotion to `~/.claude/projects/<slug>/memory/lessons.md` in the recommendations section.
- Binary deliverables without a companion `.provenance.md`: flag per data-integrity norms.

## Phase 2: Report

Write the audit report to `~/Documents/<project-name>_docs_audit.md`. Structure:

```
# docs/ Taxonomy Audit — <project-name>
Generated: <date>
Source: <abs-path-to-docs>

## Summary
- Total files: N
- Loose files at docs/*: N
- Non-canonical subdirs: N
- Singular/plural duplicate pairs: N
- Non-doc artifacts: N
- Candidate stale files: N
- Unclassifiable (UNKNOWN): N

## Proposed migration table
| Current path | Proposed path | Bucket | Confidence | Reason |
|---|---|---|---|---|
| docs/analysis_foo.md | docs/analysis/analysis_foo.md | analysis | high | filename regex |
| ... |

## Violations
### Loose files at docs/* (N)
- list

### Non-canonical subdirs (N)
- `docs/site/` → propose `deliverables/site/` (or delete if stale)

### Duplicate folders (N)
- `docs/handoff/` + `docs/handoffs/` → merge into `handoffs/`

### Non-doc artifacts (N)
- `docs/__pycache__/` → delete, add to `.gitignore`

## Candidate stale files (N)
| Path | Age | Orphan? | Superseded by | Reference rot |
|---|---|---|---|---|

## Unclassifiable (N)
Files needing manual bucket assignment. Content snippet included.

## Recommendations
- (e.g.) Extract short normative rules from `references/analysis_principles.md` into `~/.claude/projects/<slug>/memory/lessons.md` as a follow-up.
- (e.g.) Version ladder `foo_v2/v25/v26.md` → keep latest, archive rest.
- (e.g.) Create `docs/README.md` index once migration completes.

## Next step
Run the migrate pass: user reviews this report, then invokes the skill with `--migrate` to generate a feature branch with `git mv` commands.
```

## Phase 3: Approve

Present the report path to the user. Wait for explicit approval before generating migration commands. User may:
- Edit the report to change proposed destinations
- Reject specific moves
- Mark stale candidates for archive vs delete vs keep
- Resolve UNKNOWN entries

## Phase 4: Migrate (via `--migrate` flag)

**This phase never runs on `main`.** It operates on a dedicated branch and produces a PR for human review.

1. **Create branch**: `chore/docs-taxonomy-<YYYY-MM-DD>` from the project's default branch.
2. **Generate `git mv` commands** from the (approved) migration table. Create missing target dirs with `mkdir -p` first.
3. **Apply moves** on the branch. Commit in logical groups (one commit per bucket is readable).
4. **Markdown-link rewrite pass**: grep all `.md` files in the project for references to old paths (`](old/path)`, `[[old/path]]`). Rewrite to new paths. Commit as "fix: rewrite internal links after docs taxonomy migration."
5. **Handle non-doc artifacts**: delete `__pycache__/`, add ignore entries, move `.py` scripts to `scripts/` (or wherever the project keeps them — ask if unclear).
6. **Generate `docs/README.md`** index: one section per bucket, one-line entries per file with the first `# heading` as the display name.
7. **Surface branch + summary**: report N files moved, M links rewritten, K artifacts cleaned. Leave the branch pushed; user opens the PR.

**Never**:
- Squash-merge into `main` automatically
- Force-push
- Run on a dirty working tree (abort if `git status` is not clean)
- Move files across repository boundaries

## Phase 5: Verify

After the migration branch is created:
- Confirm zero loose `.md` at `docs/*` (except `README.md`)
- Confirm zero subdirs outside the 7-bucket list
- Confirm zero non-doc artifacts
- Run `grep -rn '](' docs/` and scan for broken relative links (link target does not exist)
- Run `git log --oneline <branch>` and confirm commits are cleanly separated by bucket
- Present a before/after counts table to the user

## Heuristic confidence tiers

When labeling rows in the migration table:
- **high**: filename regex matched a strong pattern (ADR numbering, `review_*`, `analysis_*`, `_handoff.md`)
- **medium**: subdir-hint match OR content-peek matched a strong header
- **low**: content-peek was ambiguous; user should double-check
- **unknown**: no heuristic fired; surface to user

Rows at `low`/`unknown` confidence block the `--migrate` pass until the user resolves them in the report.
