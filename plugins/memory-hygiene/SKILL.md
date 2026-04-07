---
name: memory-hygiene
description: "Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, and ADRs. Use this skill when: (1) the user asks to clean up, audit, or review their memory/lessons/ADRs, (2) MEMORY.md is approaching or exceeding the 200-line limit, (3) lesson files have grown large and may contain duplicates, (4) you notice ADR numbering conflicts, (5) memory files seem stale or contradicted by current code, or (6) the user says things like 'my memory is getting messy', 'clean up my lessons', 'deduplicate', 'review ADRs', 'memory audit'. Also proactively suggest running this after 10+ sessions on a project, or when MEMORY.md triggers a truncation warning."
---

# Memory Hygiene v2.0 — Audit & Cleanup

This skill audits Claude Code's persistent knowledge stores (MEMORY.md, memory topic files, lessons, and ADRs) for structural problems that degrade future session quality. It produces a structured report, gets user approval, then executes fixes.

v2.0 adds tiered loading awareness, session compression, staleness detection, ADR best practices checks, a memory quality gate, and cross-project scope review — informed by research into [OpenViking](https://github.com/volcengine/OpenViking), [MADR 4.0](https://adr.github.io/madr/), [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill), and [Cog](https://github.com/marciopuga/cog). See `docs/research-best-practices.md` for full sources.

## Why this matters

Claude Code loads MEMORY.md at the start of every conversation. When it exceeds ~200 lines / 25KB, content is silently truncated — the system loses context without warning. Duplicate lessons waste context window space and can give contradictory guidance. Stale memories that contradict current code lead to wrong recommendations. These problems compound over time.

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

#### 1a. MEMORY.md
Read the full index. Note total line count and whether it contains inline content (session logs, architecture sections, decision tables) that should live in topic files.

#### 1b. Tiered loading check (inspired by [OpenViking](https://github.com/volcengine/OpenViking) L0/L1/L2)

Claude Code's memory is implicitly tiered. Check that content lives at the right tier:

| Tier | What | Budget | Contains |
|------|------|--------|----------|
| **L0: Index** | MEMORY.md | ~40 lines, always loaded | One-line pointers only |
| **L1: Topic files** | feedback_*.md, reference_*.md | ~50 lines each, loaded on demand | Workflow reminders, key references |
| **L2: Archives** | sessions_archive.md, lessons.md | Unlimited, loaded only when explicitly needed | Full history, all lessons |

Flag content at the wrong tier:
- A 500-line entry in a topic file → should be L2 (archive)
- A critical workflow reminder buried in sessions_archive → should be promoted to L0 (MEMORY.md pointer) or L1 (its own topic file)
- Inline session logs in MEMORY.md → should be extracted to L2

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
- N session files flagged for compression
- sessions_archive.md: N lines (suggest split if >200)

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
