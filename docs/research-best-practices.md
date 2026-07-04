# Research: Memory & ADR Best Practices for AI Coding Agents (2025-2026)

**Date:** 2026-03-31
**Purpose:** Inform memory-hygiene v2.0 with the latest patterns from the AI agent ecosystem

---

## 1. Claude Code's Memory Architecture

Claude Code has four distinct memory layers ([official docs](https://code.claude.com/docs/en/memory)):

| Layer | Who writes | When loaded | Budget |
|-------|-----------|------------|--------|
| **CLAUDE.md** | Human | Every session, in full | No hard limit but affects context |
| **Auto Memory** (MEMORY.md + topic files) | Claude | First 200 lines / 25KB of MEMORY.md | Strict truncation |
| **Session Memory** | Claude | Active session only | Conversation context |
| **Auto Dream** | Claude (background subagent) | Between sessions | N/A (writes to MEMORY.md) |

**Auto Dream** ([system prompt revealed by Piebald-AI](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/agent-prompt-dream-memory-consolidation.md)) runs a 4-phase consolidation: Orient → Gather Signal → Consolidate → Prune and Index. Triggers when both gates fire: 24+ hours elapsed AND 5+ sessions completed. Community reimplementation: [grandamenium/dream-skill](https://github.com/grandamenium/dream-skill).

**Path-scoped rules** (`.claude/rules/*.md`) support YAML `paths:` frontmatter for conditional loading — only loaded when Claude touches matching files.

### Unverified internals — re-check after Claude Code updates

Some claims in this section come from community reverse-engineering rather than official documentation. Reverse-engineered behavior can change silently in any Claude Code release. Status as of 2026-07-03:

| Claim | Status | How to re-verify |
|-------|--------|------------------|
| MEMORY.md load limit: first 200 lines / 25KB | **Official-docs-backed** — documented at [code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory) | Re-read the official memory docs page after each Claude Code release and confirm the limit figures are still stated. |
| Auto Dream consolidation: 4-phase flow (Orient → Gather Signal → Consolidate → Prune and Index) and trigger gates (24+ hours elapsed AND 5+ sessions completed) | **Reverse-engineered** — sourced from the [Piebald-AI extracted system prompt](https://github.com/Piebald-AI/claude-code-system-prompts), not official docs | Diff the extracted-prompts repo against the latest Claude Code release; check whether official docs have since documented consolidation behavior. |
| Exact auto-memory path: `~/.claude/projects/<project>/memory/MEMORY.md` (+ topic files alongside it) | **Reverse-engineered / observed** — path layout inferred from local inspection, not guaranteed by official docs | In a scratch project on the current Claude Code version, ask Claude to save a memory, then inspect `~/.claude/projects/` to confirm the layout is unchanged. |

---

## 2. How Other AI Agents Handle Memory

| Agent | Memory mechanism | Persistence | Cross-session |
|-------|-----------------|-------------|---------------|
| **Cursor** | `.cursor/rules/` + community [Memory Bank](https://github.com/vanzan01/cursor-memory-bank) (6 structured .md files) | In-repo | Via committed files |
| **Windsurf** | Native [Cascade Memories](https://docs.windsurf.com/windsurf/cascade/memories) in `~/.codeium/windsurf/memories/` | Local machine | Yes, workspace-scoped |
| **OpenHands** | `AGENTS.md` + ConversationMemory event processing | In-repo | Via committed files |
| **Aider** | `CONVENTIONS.md` (read-only, human-maintained) | In-repo | No native learning |

**Cross-tool solutions:**
- [memoir](https://memoir.sh) — MCP-based, E2E encrypted, syncs across Claude Code, Cursor, Windsurf, and 6+ other tools
- [claude-mem](https://github.com/thedotmack/claude-mem) — SQLite + ChromaDB, 5 lifecycle hooks, ~10x token savings via progressive disclosure

**Cursor Memory Bank** is notable for organizing along a **stability axis**: rarely-changing files (projectbrief, systemPatterns) vs frequently-changing files (activeContext, progress). This minimizes unnecessary context churn.

---

## 3. Knowledge Base Organization Patterns

### By type (Claude Code default)
```
memory/
  MEMORY.md           # index
  feedback_*.md       # corrections, "don't do X"
  reference_*.md      # stable lookup data
  project_*.md        # codebase-specific facts
  user_*.md           # user preferences/role
```

### By stability (Cursor Memory Bank)
Separates files that change rarely from files that change every session. Achieves ~70% token reduction by not reloading stable context.

### Hot/Warm/Glacier ([Cog](https://github.com/marciopuga/cog))
- **Hot** (<50 lines): Current priorities only — pointer document
- **Warm** (domain files): Contextually activated topic files
- **Glacier** (archive): Aged data with searchable YAML frontmatter

Promotion logic: observations appearing 3+ times across 2+ weeks automatically get promoted into persistent threads via `/reflect`.

---

## 4. Memory Staleness and Decay

The core problem: flat markdown systems have no decay mechanism — every fact persists with equal weight unless explicitly deleted.

### Approaches in the wild

| Approach | Used by | How it works |
|----------|---------|-------------|
| **Recency-weighted scoring** | Mem0, academic systems | `score = similarity * exp(-lambda * days_since_access)` |
| **TTL / expiry frontmatter** | Community practice | `expires: 2026-06-30` in YAML frontmatter; hygiene pass flags expired entries |
| **Activity-based pruning** | [Cog](https://github.com/marciopuga/cog) | /housekeeping moves entries from hot → glacier based on access patterns |
| **Contradiction invalidation** | [Zep/Graphiti](https://arxiv.org/abs/2501.13956) | New facts invalidate old edges in a temporal knowledge graph |
| **Codebase contradiction** | [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill) | Memory says "uses axios" but code uses "fetch" → flagged as stale |

### Practical recommendation for memory-hygiene
Codebase-contradiction detection is the highest-value approach for file-based memory. It catches the largest class of stale memories (library changes, renamed functions, deleted files) without requiring embeddings or graph infrastructure.

---

## 5. Memory Deduplication

### File-based systems (our scale)
- **Pre-write grep** ([claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill)): Check all files before writing. Exact match → skip. Partial overlap → merge. Contradiction → resolve using current session as authoritative.
- **Three-question quality gate**: (1) Would forgetting this cause a bug? (2) Is this project-specific? (3) Does it already exist?

### At scale (for reference)
- **SemDeDup** (NVIDIA NeMo Curator / [MinishLab/semhash](https://github.com/MinishLab/semhash)): K-means clustering + cosine similarity dedup within clusters
- **Graph-based** ([Neo4j agent-memory](https://github.com/neo4j-labs/agent-memory)): Auto-merge >95% similarity, flag for review >85%

---

## 6. ADR Best Practices

### Modern format: MADR 4.0 ([adr.github.io/madr](https://adr.github.io/madr/))

Key additions over the original Nygard format:
- **Decision Drivers** — explicit quality requirements that shaped the choice
- **Considered Options** with structured **Pros/Cons** per option
- **Confirmation** — "how do we verify this was implemented?" (new in 4.0)
- **YAML frontmatter** — `status`, `date`, `deciders`, `consulted`, `informed`

### Status lifecycle (community consensus)

| Status | Meaning |
|--------|---------|
| Draft / Proposed | Under review, not binding |
| Accepted | Approved and active |
| Rejected | Considered but not adopted |
| Deprecated | No longer relevant (not replaced by specific ADR) |
| Superseded | Replaced by specific newer ADR (always link both) |
| Amended | Core decision stands, later ADR modifies a specific aspect |

Sources: [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html), [Decentraland ADR-277](https://adr.decentraland.org/adr/ADR-277), [Thunderbird docs](https://source-docs.thunderbird.net/en/latest/adr/README.html).

The **Deprecated vs Superseded** distinction matters: superseded = "a newer decision replaced this"; deprecated = "the world changed and this no longer applies."

### Numbering: preventing duplicates

| Approach | Pros | Cons |
|----------|------|------|
| **Sequential** (0001, 0002...) | Clean, human-readable | Collision risk on parallel PRs ([issue #102](https://github.com/npryce/adr-tools/issues/102)) |
| **Date-based** (20260331-title) | No collisions | Long filenames, temporal not conceptual order |
| **Hybrid** (20260331-001-title) | Best of both | Rarely seen in practice |

**Mitigations for sequential numbering:**
1. `.next-number` lock file (forces merge conflict on collision)
2. Pre-commit hook checking for duplicate prefixes
3. PR convention: renumber before merge

### Linking best practices

**Bidirectional links for all relationships:**
- ADR-B supersedes ADR-A → update BOTH files
- Relationship vocabulary: `Supersedes/Superseded by`, `Amends/Amended by`, `Relates to`, `Motivated by`

**Linking to code/PRs:**
- PR templates: "Does this PR require an ADR? Link: ___"
- Code comments: `// See ADR-0019: docs/decisions/0019-dual-cloudrun-jobs.md`
- Commit messages: `feat: dual Cloud Run jobs (ADR-0019)`
- ADR back-link: `## Links` section with implementing PR number

### At scale (50+ ADRs)

- **Domain subdirectories**: `docs/decisions/infrastructure/`, `docs/decisions/webapp/`
- **Index file**: `docs/decisions/README.md` with sortable table (ID, Title, Status, Domain, Date)
- **Tags in frontmatter**: `tags: [infrastructure, cloud-run, cost]` for faceted search

### ADRs in AI-assisted workflows

Emerging patterns:
1. **ADRs as system prompt context** — Summary table in CLAUDE.md constrains AI-generated code to stay within architectural boundaries
2. **AI-generated ADR drafts** — LLM generates the "Considered Options" section (surfaces alternatives humans didn't think to document), human reviews and accepts
3. **Post-session ADR generation** — At session end, AI proposes ADR drafts for decisions made during the session

---

## 7. What memory-hygiene v2.0 Adopts

| Research finding | v2.0 feature |
|-----------------|-------------|
| OpenViking L0/L1/L2 | Explicit tiered loading audit |
| OpenViking auto-compression + Cog glacier | Session compression heuristics |
| claude-memory-skill codebase-contradiction | Staleness via broken references + code contradictions |
| claude-memory-skill three-question gate | Writing guidelines quality gate |
| MADR 4.0 Confirmation section | ADR audit suggests adding Confirmation |
| MADR bidirectional linking | ADR audit checks for missing cross-links |
| ADR index file pattern | Suggest README.md index when >10 ADRs |
| ADR gap stubs | Suggest stubs for missing numbers |

---

## Sources

### Core Inspirations
- [OpenViking](https://github.com/volcengine/OpenViking) — L0/L1/L2 tiered loading, filesystem paradigm
- [MADR 4.0](https://adr.github.io/madr/) — Modern ADR template
- [claude-memory-skill](https://github.com/SomeStay07/claude-memory-skill) — Quality gate, contradiction detection
- [Cog](https://github.com/marciopuga/cog) — Hot/warm/glacier architecture

### Memory Management
- [Claude Code Memory Docs](https://code.claude.com/docs/en/memory)
- [Piebald-AI System Prompts](https://github.com/Piebald-AI/claude-code-system-prompts) — Auto Dream prompt
- [dream-skill](https://github.com/grandamenium/dream-skill) — Community Auto Dream
- [claude-mem](https://github.com/thedotmack/claude-mem) — SQLite + ChromaDB progressive disclosure
- [Cursor Memory Bank](https://github.com/vanzan01/cursor-memory-bank) — Stability-axis organization
- [memoir](https://memoir.sh) — Cross-tool persistent memory

### ADR
- [adr-tools](https://github.com/npryce/adr-tools) — Original CLI
- [Log4brains](https://github.com/thomvaill/log4brains) — Date-based numbering, static site
- [AWS ADR Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [Decentraland ADR-277](https://adr.decentraland.org/adr/ADR-277) — Deprecated vs Superseded

### Academic Papers
- [MemOS](https://arxiv.org/abs/2507.03724) (Jul 2025) — Three-tier memory hierarchy
- [Zep/Graphiti](https://arxiv.org/abs/2501.13956) (Jan 2025) — Temporal knowledge graph
- [A-MEM](https://arxiv.org/abs/2502.12110) (Feb 2025) — Zettelkasten-inspired linking
- [Mem0](https://arxiv.org/abs/2504.19413) (Apr 2025) — LLM-extracted memory operations

### Community
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
- [claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice)
- [centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)
