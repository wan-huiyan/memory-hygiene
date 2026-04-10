# memory-hygiene
[![GitHub release](https://img.shields.io/github/v/release/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/releases) [![Claude Code](https://img.shields.io/badge/Claude_Code-skill-orange)](https://claude.com/claude-code) [![license](https://img.shields.io/github/license/wan-huiyan/memory-hygiene)](LICENSE) [![last commit](https://img.shields.io/github/last-commit/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/commits)

Audit and optimize Claude Code's persistent memory system — axioms, MEMORY.md, lessons, memory files, and ADRs — using a research-backed tiered architecture.

## The Problem

Claude Code's memory system has two failure modes that compound over time:

1. **Truncation**: MEMORY.md exceeding ~200 lines is silently truncated — context lost without warning.
2. **Lost in the Middle**: Even within the context window, LLMs show >30% accuracy degradation for information in the middle of long contexts ([Liu et al. 2023](https://arxiv.org/abs/2307.03172)). A critical lesson at line 617 of a 1400-line file is effectively invisible.

This means **bulk-loading large files into context is counterproductive** — it wastes tokens AND buries the important rules. The solution is a tiered architecture:

```
T0: Axioms    (~50 lines, always loaded)  — behavioral overrides
T0: CLAUDE.md (~70 lines, always loaded)  — workflow rules
T1: MEMORY.md (~40 lines, always loaded)  — index pointers
T2: Topic files (~50 lines each, on demand) — per-topic context
T3: Archives  (unlimited, grep only)      — lessons, handoffs, sessions
```

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

- **Axioms tier audit** — checks if `axioms.md` exists, flags lessons that qualify for promotion (behavioral overrides that contradict default model behavior)
- **CLAUDE.md retrieval strategy audit** — flags "read lessons.md" as an anti-pattern, recommends grep-based retrieval
- **Tiered loading audit** — checks content lives at the right tier (T0 axioms / T1 index / T2 topic / T3 archive)
- **Structured audit report** grouped by severity (critical / axioms / tiering / staleness / duplicates / ADR best practices)
- **MEMORY.md slimming** — extracts inline content to topic files, rewrites as a ~40-line index
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
| **T0** | `axioms.md` | ~50 lines | Every session | Behavioral overrides that contradict default model behavior |
| **T0** | `CLAUDE.md` | ~70 lines | Every session | Workflow rules, retrieval strategy |
| **T1** | `MEMORY.md` | ~40 lines | Every session | One-line pointers to topic files |
| **T2** | `feedback_*.md`, `reference_*.md` | ~50 lines each | On demand | Workflow reminders, key references |
| **T3** | `lessons.md`, `sessions_archive.md`, `handoffs/` | Unlimited | **grep only** | Full history, all lessons, session logs |

**Axioms promotion criteria**: A lesson qualifies for T0 if you'd get it wrong by default without the lesson. Examples:
- "Session history is retrievable from JSONL files" (contradicts trained-in belief)
- "Bash tool PATH is stripped" (contradicts assumption that `which` works)
- "Background agents can't write" (contradicts expectation of full tool access)

If it's just a good practice you'd likely follow anyway, it stays in T3.

## Comparison

| | Without skill | With memory-hygiene v2.1 |
|---|---|---|
| Critical lessons ignored | Buried at line 617 of 1400-line file — "Lost in the Middle" | Promoted to axioms.md (52 lines, always loaded, front-positioned) |
| CLAUDE.md strategy | "Read lessons.md" — wastes tokens, buries signal | "Load axioms, grep archives" — high-signal context |
| Finding duplicates | Manually read 100+ lessons across 2 files | Automated cross-file scan with specific pairs listed |
| MEMORY.md bloat | Notice truncation warning, manually restructure | Extracts content to topic files, rewrites index |
| Stale memories | Never noticed — wrong recommendations silently | Detects broken references, code contradictions |
| ADR conflicts | Discover when referencing the wrong ADR | Detects all collisions, checks cross-links |
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

### Academic foundations (v2.1)

The tiered architecture and axioms promotion system are grounded in:

- **Liu et al. (2023)** ["Lost in the Middle"](https://arxiv.org/abs/2307.03172) — >30% accuracy drop for info in the middle of long LLM contexts. Directly motivates keeping axioms short and front-loaded.
- **Miller (1956)** "The Magical Number Seven" — Working memory holds 7±2 chunks. Motivates the ~50-line T0 budget.
- **Cowan (2001)** "The Magical Number 4" — True focus-of-attention is ~4 chunks. Strengthens case for ruthlessly small T0.
- **Sweller (1994)** Cognitive Load Theory — Bulk-loading irrelevant material = extraneous cognitive load.
- **Lewis et al. (2020)** [RAG](https://arxiv.org/abs/2005.11401) — Retrieval + parametric outperforms pure parametric. T3 grep = lightweight deterministic RAG.
- **Xu et al. (2024)** ["RAG or Long-Context LLMs?"](https://arxiv.org/abs/2407.16833) — Hybrid approach matches long-context at fraction of token cost.
- **Nonaka & Takeuchi (1995)** SECI model — T0 axioms = internalized knowledge; T3 archive = externalized knowledge.
- **Walsh & Ungson (1991)** Organizational Memory — T0 = automatic retrieval; T3 = controlled retrieval.
- **Nygard (2011)** [ADRs](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — "No one reads large documents." Axioms = ADRs for AI behavior.

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
| 2.1.0 | 2026-04-10 | Axioms tier (T0 behavioral overrides), promotion criteria, CLAUDE.md retrieval strategy audit, "Lost in the Middle" awareness, academic foundations |
| 2.0.0 | 2026-03-31 | Tiered loading audit, session compression, staleness detection, ADR best practices, writing quality gate, cross-project scope review |
| 1.0.0 | 2026-03-31 | Initial release — audit + fix workflow for MEMORY.md, lessons, ADRs |

## License

MIT
