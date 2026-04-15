# memory-hygiene
[![GitHub release](https://img.shields.io/github/v/release/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/releases) [![Claude Code](https://img.shields.io/badge/Claude_Code-skill-orange)](https://claude.com/claude-code) [![license](https://img.shields.io/github/license/wan-huiyan/memory-hygiene)](LICENSE) [![last commit](https://img.shields.io/github/last-commit/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/commits)

Audit and optimize Claude Code's persistent memory system — axioms, phase templates, MEMORY.md, lessons, memory files, and ADRs — using a research-backed tiered architecture with promotion/demotion lifecycle and agency-aware staleness detection.

## The Problem

Claude Code's memory system has two failure modes that compound over time:

1. **Truncation**: MEMORY.md exceeding ~200 lines is silently truncated — context lost without warning.
2. **Lost in the Middle**: Even within the context window, LLMs show >30% accuracy degradation for information in the middle of long contexts ([Liu et al. 2023](https://arxiv.org/abs/2307.03172)). A critical lesson at line 617 of a 1400-line file is effectively invisible.

This means **bulk-loading large files into context is counterproductive** — it wastes tokens AND buries the important rules. The solution is a tiered architecture:

```
T0:   Axioms    (≤12 items, always loaded)     — Universal + Role behavioral overrides
T0:   CLAUDE.md (~70 lines, always loaded)     — workflow rules, retrieval strategy
T1:   MEMORY.md (~40-80 lines, always loaded)  — index pointers
T1.5: .claude/rules/ (auto on file match)      — phase-specific rules with paths: globs
T2:   Topic files (~50 lines each, on demand)  — per-topic context
T3:   Archives  (unlimited, grep only)         — lessons, handoffs, sessions
```

v3.0 adds **phase templates** (`~/.claude/templates/phase_*.md`) — reusable rule sets that auto-activate when you touch matching files. Rules that are only relevant during specific project phases (data sourcing, deliverables, code review) don't waste attention in every session — they load precisely when needed.

Without regular maintenance, the system also accumulates: duplicate lesson numbers, orphaned memory files, stale references to renamed code, ADR numbering conflicts, and lessons that should be promoted to axioms but remain buried in archives.

## Quick Start

```
You: my lessons file is 1400 lines and critical rules keep getting ignored

Claude: [Reads axioms.md, CLAUDE.md, MEMORY.md, lessons, topic files, ADRs]
        [Checks tiered loading, axioms health, staleness, duplicates]
        [Produces structured audit report grouped by severity]

        ## Memory Hygiene Audit

        ### Critical
        - axioms.md missing — no behavioral overrides loaded at session start
        - CLAUDE.md says "read lessons.md" (bulk-load anti-pattern)

        ### Axioms
        - 6 lessons in T3 qualify for axioms promotion (override default behavior)
        - CLAUDE.md retrieval strategy: needs update (grep, not bulk-read)

        ### Tiering
        - 3 items at wrong tier (lesson #68 at line 617 → promote to T0)
        - lessons.md: 1,406 lines (archive only, never bulk-read)

        ### Staleness
        - 2 memory files reference functions that no longer exist

        ### Duplicates
        - Global lessons: 5 number collisions

        ### Recommendations
        - Create axioms.md with 15-20 behavioral overrides from lessons.md
        - Update CLAUDE.md checklist: load axioms.md, grep lessons.md
        - Merge 5 lesson pairs, suffix 5 number collisions

        Want me to proceed with all fixes?

You: yes, go ahead

Claude: [Creates axioms.md, updates CLAUDE.md, fixes duplicates, verifies]
        Done. axioms.md: 52 lines (18 behavioral overrides). CLAUDE.md: updated
        to grep-not-read strategy. No duplicate lesson numbers remain.
```

## Installation

**Claude Code:**
```bash
# Plugin install (recommended)
/plugin marketplace add wan-huiyan/memory-hygiene
/plugin install memory-hygiene@wan-huiyan-memory-hygiene

# Git clone (always works)
git clone https://github.com/wan-huiyan/memory-hygiene.git ~/.claude/skills/memory-hygiene
```

**Cursor (2.4+):**
```bash
# Per-project rule (most reliable)
mkdir -p .cursor/rules
# Copy SKILL.md content into .cursor/rules/memory-hygiene.mdc with alwaysApply: true

# Manual global install
git clone https://github.com/wan-huiyan/memory-hygiene.git ~/.cursor/skills/memory-hygiene
```

## What You Get

- **Axiom management** — classifies each axiom as Universal/Role/Phase, enforces 12-item Cowan cap, flags demotion and merge candidates
- **Phase template system** — audits `~/.claude/templates/` and `.claude/rules/`, creates missing templates, migrates Phase axioms to path-scoped rules
- **Promotion/demotion lifecycle** — two-incident rule for promotion (Google SRE), three demotion triggers (dormant/caught by tooling/subsumable)
- **Agency-aware staleness** — detects user work pattern from `user_role.md`; measures staleness across project portfolio (not just current project) for consultants/agency workers
- **CLAUDE.md retrieval strategy audit** — flags "read lessons.md" as an anti-pattern, recommends grep-based retrieval
- **Tiered loading audit** — checks content lives at the right tier (T0/T1/T1.5/T2/T3)
- **Structured audit report** grouped by severity (critical / axioms / phase templates / tiering / staleness / duplicates / ADR best practices)
- **MEMORY.md slimming** — extracts inline content to topic files, rewrites as a ~40-80 line index
- **Staleness detection** — finds broken references, relative dates, codebase contradictions, conflicting lessons
- **Session compression** — flags old verbose session files for compression, suggests archive splits
- **Lesson deduplication** — finds number collisions within and across files, merges overlapping content
- **ADR best practices** — numbering, bidirectional links, Confirmation sections, index file, gap stubs
- **Cross-project scope review** — suggests promoting frequently-reused project lessons to global (with user approval)
- **Writing quality gate** — three-question check before creating new memory files

## How It Works

| Phase | What happens |
|-------|-------------|
| **Discover** | Reads all persistent state in parallel: axioms.md, CLAUDE.md, MEMORY.md, topic files, lessons, ADRs. Checks tiered loading, axioms health, staleness, duplicates, ADR practices. |
| **Report** | Presents findings grouped by severity with specific fix recommendations |
| **Approve** | User reviews the report and decides which fixes to apply |
| **Execute** | Applies approved changes — creates axioms, updates CLAUDE.md strategy, extracts, merges, compresses |
| **Verify** | Confirms axioms.md exists and is <60 lines, MEMORY.md under 200 lines, no duplicates, all files indexed |

## What It Audits

| Target | Checks |
|--------|--------|
| **axioms.md** | Exists, line count (<60), staleness, lessons that should be promoted from T3 |
| **CLAUDE.md** | Retrieval strategy (grep vs bulk-read), references axioms.md |
| **MEMORY.md** | Line count, inline content, tiered loading violations |
| **Memory files** | Orphans, invalid frontmatter, broken references, relative dates, codebase contradictions |
| **Project lessons** | Duplicate numbers, content overlap with global lessons, contradictions |
| **Global lessons** | Duplicate numbers, content overlap with project lessons, axiom promotion candidates |
| **Session files** | Age + size for compression, overlapping coverage, archive size |
| **ADRs** | Duplicate numbers, internal mismatches, missing bidirectional links, missing Confirmation, index file, gap stubs |

## The Tiered Architecture

| Tier | File | Budget | When loaded | Contains |
|------|------|--------|-------------|----------|
| **T0** | `axioms.md` | **≤12 items** (Cowan cap) | Every session | Universal + Role behavioral overrides |
| **T0** | `CLAUDE.md` | ~70 lines | Every session | Workflow rules, retrieval strategy |
| **T1** | `MEMORY.md` | ~40-80 lines (hard limit: 200 / 25KB) | Every session | One-line pointers to topic files |
| **T1.5** | `.claude/rules/phase-*.md` | ~5 rules per file | **Auto on file match** | Phase-specific rules with `paths:` YAML frontmatter |
| **T2** | `feedback_*.md`, `reference_*.md` | ~50 lines each | On demand | Workflow reminders, key references |
| **T3** | `lessons.md`, `sessions_archive.md`, `handoffs/` | Unlimited | **grep only** | Full history, all lessons, session logs |

### Axiom Classification (three categories)

| Category | Definition | Location | Example |
|----------|-----------|----------|---------|
| **Universal** | Applies regardless of project or phase | `axioms.md` (always) | "Never fabricate data", "Bash PATH is stripped" |
| **Role** | Applies to all projects for this user's role | `axioms.md` (until role changes) | "No jargon in client materials" (agency DS) |
| **Phase** | Only relevant during specific project phases | **Phase templates** (auto on file match) | "Current-vs-planned boundary" (data sourcing) |

### Promotion/Demotion Lifecycle

```
lessons.md (T3, grep only)
    ↓ Fires in 2+ sessions without being queried (two-incident rule)
axioms.md (T0, ≤12 items)  ←── Promotion criteria: default wrong + silent failure + recent
    ↓ Dormant 20+ sessions OR caught by tooling OR subsumable
    ├── DEMOTE → back to lessons.md (T3)
    └── PHASE  → ~/.claude/templates/phase_*.md → .claude/rules/ (T1.5)
```

**Capacity enforcement**: Hard cap of 12 items (Cowan 2001: 3-4 chunks × 3 items/chunk). Every new promotion past 12 requires a demotion or merge.

**Agency-aware staleness**: For consultants/agency workers who cycle through projects, staleness is measured across the user's portfolio (calendar time), not within one project (session count). A rule dormant in THIS project may fire immediately in the next client engagement.

### Phase Templates

Global templates at `~/.claude/templates/` — reusable across all client projects:

| Template | Key rules | Auto-trigger paths |
|----------|-----------|-------------------|
| `phase_onboarding.md` | "Building on, not replacing"; learn terminology | Manual `@import` |
| `phase_data_sourcing.md` | Current-vs-planned; provenance; spot-check | `data/**`, `scripts/fetch_*` |
| `phase_analysis.md` | Permutation before reporting; effect sizes | `webapp/ci/**`, `scripts/submit_*` |
| `phase_deliverables.md` | No jargon; probability framing; consistency | `deliverables/**`, `docs/client_*` |
| `phase_code_review.md` | Fix one + grep siblings; functional tests | All code files during review |

**New project setup:**
```bash
# Option A: Path-scoped (automatic)
cp ~/.claude/templates/phase_*.md new-project/.claude/rules/
# Edit paths: in each file to match project structure

# Option B: @import (manual swap)
# In project CLAUDE.md:
@~/.claude/templates/phase_data_sourcing.md
```

## Comparison

| | Without skill | With memory-hygiene v3.0 |
|---|---|---|
| Critical lessons ignored | Buried at line 617 of 1400-line file | Promoted to axioms (≤12, always loaded) or phase templates (auto on file match) |
| Phase-specific rules | Either always loaded (wastes attention) or demoted (gets missed) | Auto-activate via `.claude/rules/` path globs — zero attention cost when irrelevant |
| Axiom growth | Unbounded — grows until attention degrades | 12-item Cowan cap with structured promotion/demotion lifecycle |
| Agency/multi-project | Rules dormant in one project get wrongly demoted | Staleness measured across portfolio, Phase rules preserved for next engagement |
| CLAUDE.md strategy | "Read lessons.md" — wastes tokens, buries signal | "Load axioms, grep archives" — high-signal context |
| MEMORY.md bloat | Notice truncation warning, manually restructure | Extracts content to topic files, rewrites index |
| Stale memories | Never noticed — wrong recommendations silently | Detects broken references, code contradictions |
| Time to clean up | 30-60 minutes of tedious manual work | 5 minutes (review report + approve) |

## Limitations

- Does not validate the *content quality* of memories or lessons — only structural issues and staleness
- Does not automatically determine whether a cross-file duplicate should live in global vs project (asks the user)
- Does not renumber all lessons sequentially (that would break external references) — only fixes collisions
- Axioms promotion candidates are flagged but require user approval — never auto-promotes
- Stale memory files are flagged but never auto-deleted — user must confirm
- Codebase contradiction detection requires package.json/requirements.txt or similar manifests

## File Format Conventions

- **axioms.md**: Short behavioral overrides grouped by theme. Each rule references the source lesson number. Target ~50 lines.
- **MEMORY.md**: No frontmatter. One-line index entries under semantic sections. Target ~40 lines.
- **Memory files**: YAML frontmatter with `name`, `description`, `type` (user/feedback/project/reference)
- **Lessons**: `### N. Title` with `**Pattern:**` and `**Rule:**` sections
- **ADRs**: `NNNN-kebab-case.md` with `# ADR-NNNN: Title`, Status/Context/Decision sections

<details>
<summary>Quality Checklist</summary>

The skill guarantees:
- [ ] axioms.md exists, line count reported, promotion candidates identified
- [ ] CLAUDE.md retrieval strategy audited (grep vs bulk-read)
- [ ] MEMORY.md line count reported and compared against 200-line limit
- [ ] All `.md` files in the memory directory checked for MEMORY.md index reference
- [ ] Tiered loading checked — content flagged if at wrong tier (T0/T1/T2/T3)
- [ ] Staleness scan: broken references, relative dates, codebase contradictions
- [ ] All lesson `### N.` headings extracted and checked for number collisions
- [ ] Cross-file comparison between global and project lessons
- [ ] Session files checked for compression candidates
- [ ] ADR filename prefixes checked for uniqueness
- [ ] ADR bidirectional links verified
- [ ] ADR index file suggested when >10 ADRs
- [ ] User approval obtained before any destructive changes
- [ ] Post-fix verification confirming all issues resolved

</details>

## Inspired By

### Academic foundations (v3.0)

The tiered architecture, phase templates, and promotion/demotion lifecycle are grounded in:

- **Liu et al. (2024)** ["Lost in the Middle"](https://arxiv.org/abs/2307.03172) — ~20pp accuracy drop for mid-context info (TACL, Stanford/Meta AI). Motivates small T0.
- **EMNLP 2025** ["Context Length Alone Hurts"](https://arxiv.org/abs/2510.05381) — Performance degrades even with perfect retrieval. Confirms the problem persists in 2025.
- **Chroma (2025)** ["Context Rot"](https://research.trychroma.com/context-rot) — 18 production models all degrade with context length. Breaking point is unpredictable.
- **Cowan (2001)** "The Magical Number 4" — Working memory is ~4 chunks → 12-item axiom cap (3 items × 4 chunks).
- **Sweller (1988)** Cognitive Load Theory — Extraneous load competes with task-relevant processing.
- **Lewis et al. (2020)** [RAG](https://arxiv.org/abs/2005.11401) — Selective retrieval outperforms preloading. T3 grep = lightweight RAG.
- **Lunney & Lueder (2017)** [Google SRE Postmortems](https://www.usenix.org/publications/login/spring2017/lunney) — Two-incident rule for runbook promotion; "would it recur silently?" demotion test.
- **Fiedler et al. (2018)** [Intentional Forgetting](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.00051/full) — Demotion = removing retrieval cues, not deletion.
- **Markus (2001)** "Toward a Theory of Knowledge Reuse" — Push vs pull: pure push risks overload. Pull surfaces knowledge at moment of need.
- **Nygard (2011)** [ADRs](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — "No one reads large documents."

### AI agent memory systems (v2.0)

- [OpenViking](https://github.com/volcengine/OpenViking) (ByteDance) — L0/L1/L2 tiered context loading, filesystem paradigm, auto-compression
- [MADR 4.0](https://adr.github.io/madr/) — Confirmation section, structured pros/cons, YAML frontmatter, status lifecycle
- [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill) — Three-question quality gate, codebase contradiction detection
- [Cog](https://github.com/marciopuga/cog) — Hot/warm/glacier memory tiers, /housekeeping and /reflect skills
- [Cursor Memory Bank](https://github.com/vanzan01/cursor-memory-bank) — Stability-axis organization pattern
- [MemOS](https://arxiv.org/abs/2507.03724) (Jul 2025) — Three-tier memory hierarchy formalization
- [Zep/Graphiti](https://arxiv.org/abs/2501.13956) (Jan 2025) — Temporal knowledge graph, contradiction invalidation

See [docs/research-best-practices.md](docs/research-best-practices.md) for the full research synthesis and [docs/openviking-assessment.md](docs/openviking-assessment.md) for the detailed OpenViking comparison.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.0.0 | 2026-04-15 | Phase template system (T1.5 path-scoped rules, `~/.claude/templates/`), three-category axiom classification (Universal/Role/Phase), 12-item Cowan cap with structured promotion/demotion lifecycle, agency-aware staleness detection, 2025 research updates (EMNLP, Chroma Context Rot) |
| 2.1.0 | 2026-04-10 | Axioms tier (T0 behavioral overrides), promotion criteria, CLAUDE.md retrieval strategy audit, "Lost in the Middle" awareness, academic foundations |
| 2.0.0 | 2026-03-31 | Tiered loading audit, session compression, staleness detection, ADR best practices, writing quality gate, cross-project scope review |
| 1.0.0 | 2026-03-31 | Initial release — audit + fix workflow for MEMORY.md, lessons, ADRs |

## License

MIT
