# memory-hygiene
[![GitHub release](https://img.shields.io/github/v/release/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/releases) [![Claude Code](https://img.shields.io/badge/Claude_Code-skill-orange)](https://claude.com/claude-code) [![license](https://img.shields.io/github/license/wan-huiyan/memory-hygiene)](LICENSE) [![last commit](https://img.shields.io/github/last-commit/wan-huiyan/memory-hygiene)](https://github.com/wan-huiyan/memory-hygiene/commits)

Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, and ADRs.

## The Problem

Claude Code's auto-memory system accumulates cruft over time:

- **MEMORY.md bloats past 200 lines** and gets silently truncated, losing context
- **Lesson numbers collide** when multiple sessions add lessons concurrently
- **ADR numbers duplicate** when decisions are recorded without checking existing files
- **Memory files become orphaned** — they exist on disk but aren't indexed, so future sessions never see them
- **Stale memories contradict current code** — "uses library X" when the codebase moved to Y
- **Cross-file duplicates** waste context window space and can give contradictory guidance

These problems are tedious to find manually and compound with every session.

## Quick Start

```
You: my memory files are getting messy, can you clean them up?

Claude: [Reads MEMORY.md, all memory files, lessons, and ADRs]
        [Checks tiered loading, staleness, duplicates, ADR best practices]
        [Produces structured audit report grouped by severity]

        ## Memory Hygiene Audit

        ### Critical
        - MEMORY.md is 482 lines (limit: ~200) — truncation is active
        - 3 orphaned memory files not indexed

        ### Staleness
        - 2 memory files reference functions that no longer exist
        - 1 lesson contradicts a newer global lesson

        ### Duplicates
        - Global lessons: 5 number collisions
        - ADRs: 6 number collisions

        ### ADR Best Practices
        - 4 ADRs missing bidirectional supersedes links
        - No index file (22 ADRs — recommend creating one)

        ### Recommendations
        - Extract session logs to sessions_archive.md (saves ~300 lines)
        - Merge 5 lesson pairs, suffix 5 number collisions
        - Renumber 7 ADR files, add cross-links

        Want me to proceed with all fixes?

You: yes, go ahead

Claude: [Executes fixes, verifies results]
        Done. MEMORY.md: 482 → 40 lines. All files indexed. No duplicate numbers.
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

- **Structured audit report** grouped by severity (critical / staleness / duplicates / tiering / ADR best practices)
- **MEMORY.md slimming** — extracts inline content to topic files, rewrites as a ~40-line index
- **Tiered loading audit** — checks content lives at the right tier (L0 index / L1 topic / L2 archive)
- **Staleness detection** — finds broken references, relative dates, codebase contradictions, conflicting lessons
- **Session compression** — flags old verbose session files for compression, suggests archive splits
- **Lesson deduplication** — finds number collisions within and across files, merges overlapping content
- **ADR best practices** — numbering, bidirectional links, Confirmation sections, index file, gap stubs
- **Cross-project scope review** — suggests promoting frequently-reused project lessons to global (with user approval)
- **Writing quality gate** — three-question check before creating new memory files

## How It Works

| Phase | What happens |
|-------|-------------|
| **Discover** | Reads all persistent state in parallel: MEMORY.md, topic files, lessons, ADRs. Checks tiered loading, staleness, duplicates, ADR practices. |
| **Report** | Presents findings grouped by severity with specific fix recommendations |
| **Approve** | User reviews the report and decides which fixes to apply |
| **Execute** | Applies approved changes — extracts, merges, renames, compresses, indexes |
| **Verify** | Confirms MEMORY.md under 200 lines, no duplicates, all files indexed, no new broken references |

## What It Audits

| Target | Checks |
|--------|--------|
| **MEMORY.md** | Line count, inline content, tiered loading violations |
| **Memory files** | Orphans, invalid frontmatter, broken references, relative dates, codebase contradictions |
| **Project lessons** | Duplicate numbers, content overlap with global lessons, contradictions |
| **Global lessons** | Duplicate numbers, content overlap with project lessons |
| **Session files** | Age + size for compression, overlapping coverage, archive size |
| **ADRs** | Duplicate numbers, internal mismatches, missing bidirectional links, missing Confirmation, index file, gap stubs |

## Comparison

| | Without skill | With memory-hygiene |
|---|---|---|
| Finding duplicates | Manually read 100+ lessons across 2 files | Automated cross-file scan with specific pairs listed |
| MEMORY.md bloat | Notice truncation warning, manually restructure | Extracts content to topic files, rewrites index |
| Stale memories | Never noticed — wrong recommendations silently | Detects broken references, code contradictions |
| ADR conflicts | Discover when referencing the wrong ADR | Detects all collisions, checks cross-links |
| Session files | Accumulate forever, growing memory directory | Flagged for compression when old + verbose |
| Time to clean up | 30-60 minutes of tedious manual work | 5 minutes (review report + approve) |

## Limitations

- Does not validate the *content quality* of memories or lessons — only structural issues and staleness
- Does not automatically determine whether a cross-file duplicate should live in global vs project (asks the user, considering their role)
- Does not renumber all lessons sequentially (that would break external references) — only fixes collisions
- ADR gap-filling is not automatic (suggests stubs, user decides)
- Stale memory files are flagged but never auto-deleted — user must confirm
- Codebase contradiction detection requires the project to have package.json/requirements.txt or similar manifests
- Session compression preserves key outcomes but may lose details the user considers important — always asks first

## File Format Conventions

The skill follows Claude Code's auto-memory conventions:

- **MEMORY.md**: No frontmatter. One-line index entries under semantic sections. Target ~40 lines.
- **Memory files**: YAML frontmatter with `name`, `description`, `type` (user/feedback/project/reference)
- **Lessons**: `### N. Title` with `**Pattern:**` and `**Rule:**` sections
- **ADRs**: `NNNN-kebab-case.md` with `# ADR-NNNN: Title`, Status/Context/Decision sections. Recommended: Confirmation section, bidirectional supersedes links, PR back-links.

<details>
<summary>Quality Checklist</summary>

The skill guarantees:
- [ ] MEMORY.md line count reported and compared against 200-line limit
- [ ] All `.md` files in the memory directory checked for MEMORY.md index reference
- [ ] Tiered loading checked — content flagged if at wrong tier (L0/L1/L2)
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
| 2.1.0 | 2026-04-10 | Axioms tier (T0 behavioral overrides), promotion criteria, CLAUDE.md retrieval strategy audit, "Lost in the Middle" awareness, academic foundations (Liu et al. 2023, Miller, Cowan, Sweller, Lewis et al., Nonaka & Takeuchi, Walsh & Ungson, Nygard) |
| 2.0.0 | 2026-03-31 | Tiered loading audit, session compression, staleness detection (broken refs, codebase contradictions, relative dates), ADR best practices (bidirectional links, Confirmation, index file), writing quality gate, cross-project scope review |
| 1.0.0 | 2026-03-31 | Initial release — audit + fix workflow for MEMORY.md, lessons, ADRs |

## License

MIT
