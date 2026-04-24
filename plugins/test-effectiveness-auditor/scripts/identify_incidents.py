#!/usr/bin/env python3
"""
identify_incidents.py — Mine a project's incident signal sources and return
a merged, de-duplicated list of candidate incidents for test-effectiveness replay.

Signal sources (all read-only):
  - docs/findings/*.md, docs/issues/*.md, docs/diagnostics/*.md, docs/audits/*.md
  - Root-level discovery_*.md, incident_*.md, postmortem_*.md
  - git log commits matching fix|bug|revert|hotfix|incident (case-insensitive)

Output: JSON list written to stdout. Each entry has:
  {
    "incident_id": "slug",
    "source": "docs/findings/foo.md" | "commit:<sha>",
    "title": "first line / commit subject",
    "fix_commit": "<sha>" | null,
    "pre_fix_commit": "<sha>" | null,
    "signal_strength": "write-up" | "hotfix" | "revert" | "commit"
  }

Usage:
  python identify_incidents.py <project-path> [--limit N]

The agent is expected to present the output to the user for confirmation before
Phase 3 replay. Do not blindly replay 200 commits — cap at 10 for a first pass.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SIGNAL_DIRS = ["docs/findings", "docs/issues", "docs/diagnostics", "docs/audits"]
SIGNAL_ROOT_GLOBS = ["discovery_*.md", "incident_*.md", "postmortem_*.md"]
COMMIT_GREP = r"fix|bug|revert|hotfix|incident"  # ERE alternation (unescaped)


def slugify(text: str, max_len: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s[:max_len] or "unnamed"


def first_line(path: Path) -> str:
    try:
        with path.open() as f:
            for line in f:
                line = line.strip().lstrip("#").strip()
                if line:
                    return line
    except Exception:
        pass
    return path.stem


def run_git(project: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(project), *args], text=True, stderr=subprocess.DEVNULL
    )


def find_commit_that_touched(project: Path, doc_path: Path) -> str | None:
    """Best-effort: the commit that added this doc likely fixed the incident or documented it."""
    try:
        rel = doc_path.relative_to(project)
        out = run_git(project, "log", "--follow", "--format=%H", "--", str(rel))
        shas = [s.strip() for s in out.splitlines() if s.strip()]
        return shas[-1] if shas else None  # oldest (when doc was first added)
    except Exception:
        return None


def collect_docs(project: Path) -> list[dict]:
    results: list[dict] = []
    for rel in SIGNAL_DIRS:
        d = project / rel
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")) + sorted(d.glob("*.html")):
            title = first_line(p)
            commit = find_commit_that_touched(project, p)
            results.append({
                "incident_id": slugify(p.stem),
                "source": str(p.relative_to(project)),
                "title": title,
                "fix_commit": commit,
                "pre_fix_commit": None,
                "signal_strength": "write-up",
            })
    for pattern in SIGNAL_ROOT_GLOBS:
        for p in sorted(project.glob(pattern)):
            title = first_line(p)
            commit = find_commit_that_touched(project, p)
            results.append({
                "incident_id": slugify(p.stem),
                "source": str(p.relative_to(project)),
                "title": title,
                "fix_commit": commit,
                "pre_fix_commit": None,
                "signal_strength": "write-up",
            })
    return results


def collect_commits(project: Path, limit: int = 200) -> list[dict]:
    """Commits matching the keyword regex, most recent first."""
    try:
        out = run_git(
            project,
            "log",
            "--all",
            "-i",
            f"--grep={COMMIT_GREP}",
            "--extended-regexp",
            f"-n{limit}",
            "--format=%H%x09%s",
        )
    except subprocess.CalledProcessError:
        return []
    results: list[dict] = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        subj_lower = subject.lower()
        if "revert" in subj_lower:
            strength = "revert"
        elif "hotfix" in subj_lower:
            strength = "hotfix"
        else:
            strength = "commit"
        results.append({
            "incident_id": slugify(subject),
            "source": f"commit:{sha[:10]}",
            "title": subject,
            "fix_commit": sha,
            "pre_fix_commit": None,
            "signal_strength": strength,
        })
    return results


def resolve_pre_fix(project: Path, sha: str | None) -> str | None:
    if not sha:
        return None
    try:
        return run_git(project, "rev-parse", f"{sha}^").strip()
    except subprocess.CalledProcessError:
        return None


def merge_and_rank(docs: list[dict], commits: list[dict]) -> list[dict]:
    """Keep every doc as its own incident; dedup commits whose SHA already belongs to a doc.

    Two docs can share a fix_commit SHA (both added in the same commit), and they
    are legitimately separate incidents — don't collapse them on SHA alone.
    """
    doc_shas = {d["fix_commit"] for d in docs if d["fix_commit"]}
    commit_by_sha: dict[str, dict] = {}
    orphans: list[dict] = []
    for entry in commits:
        sha = entry["fix_commit"]
        if sha and sha in doc_shas:
            continue
        if sha:
            commit_by_sha[sha] = entry
        else:
            orphans.append(entry)
    strength_order = {"write-up": 0, "hotfix": 1, "revert": 2, "commit": 3}
    merged = list(docs) + list(commit_by_sha.values()) + orphans
    merged.sort(key=lambda e: (strength_order.get(e["signal_strength"], 9), e["title"]))
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--limit", type=int, default=200, help="git log commit limit")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    if not (project / ".git").exists():
        print(f"not a git repo: {project}", file=sys.stderr)
        return 2

    docs = collect_docs(project)
    commits = collect_commits(project, args.limit)
    merged = merge_and_rank(docs, commits)
    for entry in merged:
        entry["pre_fix_commit"] = resolve_pre_fix(project, entry["fix_commit"])

    json.dump(merged, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
