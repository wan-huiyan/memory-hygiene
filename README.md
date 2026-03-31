# memory-hygiene

Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, and ADRs.

## The Problem

Claude Code's auto-memory system accumulates cruft over time:

- **MEMORY.md bloats past 200 lines** and gets silently truncated, losing context
- **Lesson numbers collide** when multiple sessions add lessons concurrently
- **ADR numbers duplicate** when decisions are recorded without checking existing files
- **Memory files become orphaned** — they exist on disk but aren't indexed, so future sessions never see them
- **Cross-file duplicates** waste context window space and can give contradictory guidance

These problems are tedious to find manually and compound with every session.

## Quick Start

```
You: my memory files are getting messy, can you clean them up?

Claude: [Reads MEMORY.md, all memory files, lessons, and ADRs]
        [Produces structured audit report grouped by severity]

        ## Memory Hygiene Audit

        ### Critical
        - MEMORY.md is 482 lines (limit: ~200) — truncation is active
        - 3 orphaned memory files not indexed

        ### Duplicates
        - Global lessons: 5 number collisions (#41, #42, #65, #66, #68)
        - Project lessons: 5 duplicate pairs
        - ADRs: 6 number collisions

        ### Recommendations
        - Extract session logs to sessions_archive.md (saves ~300 lines)
        - Merge 5 lesson pairs, suffix 5 number collisions
        - Renumber 7 ADR files to fill gaps

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

- **Structured audit report** grouped by severity (critical / duplicates / structural)
- **MEMORY.md slimming** — extracts inline content to topic files, rewrites as a ~40-line index
- **Lesson deduplication** — finds number collisions within and across files, merges overlapping content
- **ADR renumbering** — detects duplicate numbers, renames files and updates internal references
- **Orphan detection** — finds memory files not indexed in MEMORY.md
- **Cross-file duplicate detection** — identifies lessons that exist in both global and project files

## How It Works

| Phase | What happens |
|-------|-------------|
| **Discover** | Reads MEMORY.md, all memory files, both lessons files, and ADR directory in parallel |
| **Report** | Presents findings grouped by severity with specific fix recommendations |
| **Approve** | User reviews the report and decides which fixes to apply |
| **Execute** | Applies approved changes — extracts, merges, renames, indexes |
| **Verify** | Confirms MEMORY.md under 200 lines, no duplicates, all files indexed |

## What It Audits

| Target | Checks |
|--------|--------|
| **MEMORY.md** | Line count, inline content that should be in topic files |
| **Memory files** | Orphans (not indexed), invalid frontmatter type, stale content |
| **Project lessons** | Duplicate numbers, content overlap with global lessons |
| **Global lessons** | Duplicate numbers, content overlap with project lessons |
| **ADRs** | Duplicate file number prefixes, internal number mismatches, copy/paste duplicates |

## Comparison

| | Without skill | With memory-hygiene |
|---|---|---|
| Finding duplicates | Manually read 100+ lessons across 2 files | Automated cross-file scan with specific pairs listed |
| MEMORY.md bloat | Notice truncation warning, manually restructure | Extracts content to topic files, rewrites index |
| ADR conflicts | Discover when referencing the wrong ADR | Detects all collisions, proposes renumbering |
| Orphaned files | Never noticed — invisible to future sessions | Flagged and indexed or removed |
| Time to clean up | 30-60 minutes of tedious manual work | 5 minutes (review report + approve) |

## Limitations

- Does not validate the *content quality* of memories or lessons — only structural issues
- Does not automatically determine whether a cross-file duplicate should live in global vs project (asks the user)
- Does not renumber all lessons sequentially (that would break external references) — only fixes collisions
- ADR gap-filling is not automatic (e.g., if 0014 is deleted, 0015 stays as-is)
- Stale memory files are flagged but never auto-deleted — user must confirm

## File Format Conventions

The skill follows Claude Code's auto-memory conventions:

- **MEMORY.md**: No frontmatter. One-line index entries under semantic sections. Target ~40 lines.
- **Memory files**: YAML frontmatter with `name`, `description`, `type` (user/feedback/project/reference)
- **Lessons**: `### N. Title` with `**Pattern:**` and `**Rule:**` sections
- **ADRs**: `NNNN-kebab-case.md` with `# ADR-NNNN: Title` and Status/Context/Decision sections

<details>
<summary>Quality Checklist</summary>

The skill guarantees:
- [ ] MEMORY.md line count reported and compared against 200-line limit
- [ ] All `.md` files in the memory directory checked for MEMORY.md index reference
- [ ] All lesson `### N.` headings extracted and checked for number collisions
- [ ] Cross-file comparison between global and project lessons
- [ ] ADR filename prefixes checked for uniqueness
- [ ] User approval obtained before any destructive changes
- [ ] Post-fix verification confirming all issues resolved

</details>

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-31 | Initial release — full audit + fix workflow for MEMORY.md, lessons, ADRs |

## License

MIT
