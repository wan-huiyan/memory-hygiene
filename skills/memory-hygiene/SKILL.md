---
name: memory-hygiene
description: "Audit and clean up Claude Code's persistent memory system — MEMORY.md, memory files, lessons, and ADRs. Use this skill when: (1) the user asks to clean up, audit, or review their memory/lessons/ADRs, (2) MEMORY.md is approaching or exceeding the 200-line limit, (3) lesson files have grown large and may contain duplicates, (4) you notice ADR numbering conflicts, or (5) the user says things like 'my memory is getting messy', 'clean up my lessons', 'deduplicate', 'review ADRs', 'memory audit'. Also proactively suggest running this after 10+ sessions on a project, or when MEMORY.md triggers a truncation warning."
---

# Memory Hygiene — Audit & Cleanup

This skill audits Claude Code's persistent knowledge stores (MEMORY.md, memory topic files, lessons, and ADRs) for structural problems that degrade future session quality: bloat, duplicates, orphans, numbering collisions, and stale content. It produces a structured report, gets user approval, then executes fixes.

## Why this matters

Claude Code loads MEMORY.md at the start of every conversation. When it exceeds ~200 lines, it gets truncated — meaning the system silently loses context. Duplicate lessons waste context window space and can give contradictory guidance. ADR number collisions make decisions harder to reference. Orphaned memory files are invisible to future sessions. These problems compound over time and are tedious to find manually.

## When to run

- **On demand:** User explicitly asks for a memory cleanup, audit, or review
- **Proactively suggest** when you notice any of these signals:
  - MEMORY.md truncation warning in the system prompt
  - MEMORY.md has 150+ lines of inline content (not just index pointers)
  - A lessons file has 80+ lessons
  - You spot duplicate lesson numbers while reading lessons.md
  - Multiple ADR files share the same number prefix

## The audit-then-fix workflow

### Phase 1: Discover

Read all persistent state files. Use parallel reads where possible:

1. **MEMORY.md** — Read the full index. Note total line count and whether it contains inline content (session logs, architecture sections, decision tables) that should live in topic files.

2. **Memory topic files** — Glob `~/.claude/projects/<current-project>/memory/*.md` (excluding MEMORY.md and lessons.md). For each file, read the frontmatter (name, description, type). Check:
   - Is it referenced from MEMORY.md? (orphan check)
   - Is its `type` field valid? (must be: user, feedback, project, reference)
   - Does its content overlap substantially with another memory file?

3. **Project lessons** — Read `~/.claude/projects/<current-project>/memory/lessons.md`. Extract all lesson numbers and titles. Check for:
   - Duplicate numbers (same `### N.` appearing twice)
   - Non-sequential numbering (gaps are fine; repeats are not)
   - Lessons that substantially duplicate a global lesson

4. **Global lessons** — Read `~/.claude/lessons.md`. Same duplicate/numbering checks. Also cross-reference with project lessons to find content that exists in both places.

5. **ADRs** — Glob `docs/decisions/*.md` (or wherever the project keeps ADRs). Extract the number prefix from each filename. Check for:
   - Duplicate numbers (two files with same `NNNN-` prefix)
   - Number inside the file not matching the filename
   - Files with identical or near-identical content (copy/paste errors)

### Phase 2: Report

Present findings as a structured audit report. Group by severity:

```
## Memory Hygiene Audit

### Critical (breaks functionality)
- MEMORY.md is N lines (limit: ~200) — truncation is active
- N orphaned memory files not indexed in MEMORY.md

### Duplicates
- Global lessons: N number collisions (list them)
- Project lessons: N number collisions (list them)
- Cross-file: N lessons duplicated between global and project (list them)
- ADRs: N number collisions (list them)

### Structural
- MEMORY.md contains N lines of inline content that should be in topic files
- N memory files missing valid frontmatter type
- N memory files with stale/outdated content (>30 days old, referencing deleted files)

### Recommendations
- For each issue, state: what to do, what files are affected, estimated impact
```

For cross-file duplicates (global vs project lessons), the decision of where to keep the lesson matters. Use this heuristic:
- **Keep in global** if the lesson applies to any project using the same tools/methods (e.g., "Fourier needs 2+ years of data" is general time series advice)
- **Keep in project** if the lesson is hyper-specific to this project's data, configuration, or codebase (e.g., "method catalog IDs for this webapp")
- When unsure, **ask the user** — present the lesson content and both options

### Phase 3: Get approval

After presenting the report, ask the user which fixes to proceed with. Respect their decisions — they may want to keep some "duplicates" that serve different audiences, or skip renumbering if they reference lesson numbers in external docs.

### Phase 4: Execute fixes

Apply approved changes. For each fix type:

**MEMORY.md bloat:**
- Extract inline content (session logs, architecture sections, decision tables) into dedicated topic files with proper frontmatter
- Rewrite MEMORY.md as a concise index (~40 lines) with one-line entries: `- [Title](file.md) — brief description`
- Group entries under semantic sections (Workflow, Development, Analysis, References, History)

**Orphaned memory files:**
- Add missing files to MEMORY.md under the appropriate section
- Or, if the file is clearly stale/superseded, confirm deletion with the user

**Lesson deduplication:**
- For number collisions within a file: suffix the duplicate (e.g., `### 41b.`) or merge if content overlaps
- For cross-file duplicates: keep the better-written version in the appropriate location, remove the other
- When merging, preserve unique details from both versions
- Do NOT renumber all lessons sequentially — that would break external references. Only fix collisions.

**ADR renumbering:**
- Keep the first file at each duplicate number; give subsequent files the next available number
- Update the ADR number in the file's title line (e.g., `# ADR-0006:` → `# ADR-0016:`) to match the new filename
- Delete obvious duplicates (same content, different filenames) after user confirmation

**Stale memory files:**
- Flag but don't auto-delete. Present the content and let the user decide.

### Phase 5: Verify

After executing fixes:
- Confirm MEMORY.md line count is under 200
- Confirm all memory files are indexed
- Confirm no duplicate lesson numbers remain
- Confirm all ADR numbers are unique
- Present a summary table: before/after counts

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
- Optional: Alternatives Considered, Consequences, Revert Criteria
