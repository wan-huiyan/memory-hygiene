"""Opt-in context selection, not a skill, source editor or permission gate.

Python 3.10+, standard library only. Canonical shared engine for memory-hygiene
and its consumers. See docs/context-routing.md for the v1 contract and limits.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any
import unicodedata

API_VERSION = 1
ENGINE_VERSION = "0.1.0"
EXCLUDED = {".git", "node_modules", ".venv", "venv", "__pycache__", ".env"}
STATUSES = {"active", "reference", "disputed", "superseded", "archived"}
STOP = set("a an and are as at be by for from in is it of on or that the this to use when with".split())
META_KEYS = {"id", "kind", "summary", "status", "scope", "valid_from", "valid_until",
             "supersedes", "depends_on", "conflicts_with", "relationship_evidence",
             "reviewed", "incident_id", "public_summary", "egress_approved", "mandatory",
             "verification", "tags", "invocation_policy"}


class RoutingError(ValueError):
    """A visible, recoverable routing failure; never permission to proceed."""


def error_code(exc: BaseException) -> str:
    """The closed-vocabulary code when we raised it, the class name otherwise.

    Routing and provider errors carry codes written in this repository, so
    reporting them reveals nothing about an external response. Any other
    exception contributes only its type: its message may quote a payload.
    """
    if isinstance(exc, RoutingError):
        return str(exc) or type(exc).__name__
    code = getattr(exc, "provider_error_code", None)
    return code if isinstance(code, str) and code else type(exc).__name__


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def terms(text: str) -> set[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    words = set(re.findall(r"[^\W_]+", text, re.UNICODE)) - STOP
    # Local-only bigrams make Chinese passages searchable without a network model.
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        words.update(run[i:i + 2] for i in range(len(run) - 1))
    return words


def source_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(p in {"..", "."} for p in path.parts):
        raise RoutingError("unsafe_source_path")
    if "\\" in relative or any(p in EXCLUDED for p in path.parts):
        raise RoutingError("excluded_source_path")
    cursor = root.resolve()
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RoutingError("symlink_source")
    if not cursor.is_file() or cursor.suffix.lower() != ".md":
        raise RoutingError("source_not_markdown_file")
    return cursor


def frontmatter(text: str) -> dict[str, str]:
    """Read scalar discovery fields only; reject ambiguous invocation controls.

    This is deliberately NOT a general YAML loader. Relationships and lifecycle
    live in reviewed JSON sidecars. Unsupported security-field syntax fails closed.
    """
    text = text.removeprefix("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise RoutingError("unclosed_frontmatter") from exc
    values: dict[str, str] = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([\w-]+):\s*(.*)$", line)
        if match:
            key, value = match.groups()
            if key in values:
                raise RoutingError("duplicate_frontmatter_key")
            values[key] = value.strip()
        elif line[:1].isspace() and key and line.strip():
            values[key] += " " + line.strip()
        elif line.strip() and not line.lstrip().startswith("#"):
            raise RoutingError("unsupported_frontmatter_syntax")
    for key in ("name", "description"):
        if key in values:
            value = values[key]
            value = re.sub(r"^[|>][-+]?\s*", "", value)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    if "disable-model-invocation" in values:
        value = values["disable-model-invocation"].split(" #", 1)[0].strip().strip("\"'").lower()
        if value not in {"true", "false"}:
            raise RoutingError("ambiguous_invocation_control")
        values["disable-model-invocation"] = value
    return values


def inventory(root: Path, includes: list[str]) -> list[str]:
    if not includes:
        raise RoutingError("explicit_include_required")
    found = set()
    for pattern in includes:
        if not pattern or Path(pattern).is_absolute() or ".." in PurePosixPath(pattern).parts:
            raise RoutingError("unsafe_include")
        for path in root.glob(pattern):
            relative = path.relative_to(root).as_posix()
            if any(p in EXCLUDED for p in path.relative_to(root).parts):
                continue
            if path.suffix.lower() == ".md":
                source_path(root, relative)
                found.add(relative)
    return sorted(found)


def index(root: Path, namespace: str, includes: list[str], metadata: dict | None = None) -> dict:
    """Read explicit roots only. Metadata is reviewed user input, never model output."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", namespace):
        raise RoutingError("invalid_namespace")
    metadata = metadata or {}
    paths = inventory(root, includes)
    if not paths:
        raise RoutingError("empty_inventory")
    if set(metadata) - set(paths):
        raise RoutingError("metadata_source_missing")
    records = []
    for path in paths:
        text = source_path(root, path).read_bytes().decode("utf-8")
        fm = frontmatter(text)
        extra = metadata.get(path, {})
        if not isinstance(extra, dict) or set(extra) - META_KEYS:
            raise RoutingError("unknown_metadata_field")
        manual = fm.get("disable-model-invocation") == "true"
        record = {
            "id": f"{namespace}:{path}", "source": path, "content_hash": text_hash(text),
            "kind": "skill" if Path(path).name == "SKILL.md" else "memory",
            "title": fm.get("name") or Path(path).stem,
            "summary": fm.get("description", ""), "status": "active", "scope": {},
            "invocation_policy": "manual-only" if manual else "automatic",
            "source_manual_only": manual, "verification": "unverified",
            "supersedes": [], "depends_on": [], "conflicts_with": [],
            "mandatory": False, "egress_approved": False, "reviewed": False,
            "search_terms": sorted(terms(text)),
        }
        record.update(extra)
        if manual and record["invocation_policy"] != "manual-only":
            raise RoutingError("cannot_relax_source_invocation_policy")
        records.append(record)
    result = {"api_version": API_VERSION, "namespace": namespace,
              "includes": includes, "records": records}
    validate(result)
    result["digest"] = digest(result)
    return result


def validate(registry: dict) -> dict[str, dict]:
    if registry.get("api_version") != API_VERSION:
        raise RoutingError("unsupported_registry_version")
    records = registry.get("records")
    if not isinstance(records, list) or not records:
        raise RoutingError("empty_registry")
    by_id = {}
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise RoutingError("invalid_record")
        if item["id"] in by_id:
            raise RoutingError("duplicate_id")
        by_id[item["id"]] = item
        if item.get("status") not in STATUSES:
            raise RoutingError("unknown_status")
        if item.get("invocation_policy") not in {"automatic", "manual-only"}:
            raise RoutingError("unknown_invocation_policy")
        if item.get("source_manual_only") and item["invocation_policy"] != "manual-only":
            raise RoutingError("cannot_relax_source_invocation_policy")
        for field_name in ("reviewed", "mandatory", "egress_approved", "source_manual_only"):
            if type(item.get(field_name)) is not bool:
                raise RoutingError("invalid_boolean")
        if item["mandatory"] and not item["reviewed"]:
            raise RoutingError("unreviewed_mandatory_policy")
        if item["egress_approved"] and (not item["reviewed"] or not item.get("public_summary")):
            raise RoutingError("egress_requires_reviewed_summary")
        if not isinstance(item.get("scope"), dict) or any(
            not isinstance(v, list) or not v or any(not isinstance(s, str) for s in v)
            for v in item["scope"].values()
        ):
            raise RoutingError("invalid_scope")
        for key in ("source", "content_hash", "title", "summary"):
            if not isinstance(item.get(key), str):
                raise RoutingError("invalid_record_text")
        dates = {}
        for key in ("valid_from", "valid_until"):
            if item.get(key):
                dates[key] = iso_day(item[key])
        if len(dates) == 2 and dates["valid_from"] > dates["valid_until"]:
            raise RoutingError("inverted_validity_interval")
        for relation in ("supersedes", "depends_on", "conflicts_with"):
            links = item.get(relation)
            if not isinstance(links, list) or any(not isinstance(s, str) for s in links):
                raise RoutingError("invalid_relationship")
            if links and (not item["reviewed"] or not item.get("relationship_evidence")):
                raise RoutingError("unreviewed_relationship")
    for item in records:
        for relation in ("supersedes", "depends_on", "conflicts_with"):
            if any(target not in by_id or target == item["id"] for target in item[relation]):
                raise RoutingError("dangling_or_self_relationship")
    # Dependencies and supersession must be DAGs; symmetric conflicts may cycle.
    for relation in ("supersedes", "depends_on"):
        visiting, done = set(), set()
        def visit(key: str) -> None:
            if key in visiting:
                raise RoutingError(f"{relation}_cycle")
            if key in done:
                return
            visiting.add(key)
            for target in by_id[key][relation]:
                visit(target)
            visiting.remove(key)
            done.add(key)
        for key in by_id:
            visit(key)
    return by_id


def combine(registries: list[dict], relationships: dict | None = None) -> dict:
    """One budget across explicitly mapped roots; no absolute paths in the index.

    Cross-store edges must be supplied as reviewed JSON, never inferred here.
    Separate namespaces prevent one project's record from shadowing another's.
    """
    sources, records = {}, []
    for registry in registries:
        validate(registry)
        namespace = registry["namespace"]
        if "sources" in registry or namespace in sources:
            raise RoutingError("nested_or_duplicate_namespace")
        sources[namespace] = {"includes": registry["includes"]}
        records.extend({**item, "origin": namespace} for item in registry["records"])
    by_id = {r["id"]: r for r in records}
    for key, changes in (relationships or {}).items():
        if key not in by_id or set(changes) - {"supersedes", "depends_on", "conflicts_with", "reviewed", "relationship_evidence"}:
            raise RoutingError("invalid_cross_store_relationship")
        by_id[key].update(changes)
    result = {"api_version": API_VERSION, "namespace": "combined", "sources": sources,
              "records": records}
    validate(result)
    result["digest"] = digest(result)
    return result


def snapshot(registry: dict, root: Path | dict[str, Path]) -> dict[str, str]:
    by_id = validate(registry)
    if "digest" in registry:
        expected = digest({k: v for k, v in registry.items() if k != "digest"})
        if expected != registry["digest"]:
            raise RoutingError("registry_digest_mismatch")
    if "sources" in registry:
        if not isinstance(root, dict) or set(root) != set(registry["sources"]):
            raise RoutingError("exact_explicit_root_mapping_required")
        roots = {key: Path(path) for key, path in root.items()}
        sources = registry["sources"]
    else:
        if isinstance(root, dict):
            raise RoutingError("single_registry_requires_single_root")
        roots = {"": Path(root)}
        sources = {"": {"includes": registry["includes"]}}
    for origin, spec in sources.items():
        expected = sorted({r["source"] for r in by_id.values() if r.get("origin", "") == origin})
        if inventory(roots[origin], spec["includes"]) != expected:
            raise RoutingError("inventory_changed_reindex_required")
    texts = {}
    for key, item in by_id.items():
        origin = item.get("origin", "")
        if origin not in roots:
            raise RoutingError("unknown_source_root")
        text = source_path(roots[origin], item["source"]).read_bytes().decode("utf-8")
        if text_hash(text) != item["content_hash"]:
            raise RoutingError("source_changed_reindex_required")
        fm = frontmatter(text)
        if fm.get("disable-model-invocation") == "true" and item["invocation_policy"] != "manual-only":
            raise RoutingError("cannot_relax_source_invocation_policy")
        texts[key] = text
    return texts


def iso_day(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise RoutingError("date_must_be_iso_day")
    return date.fromisoformat(value)


def in_scope(item: dict, state: dict) -> bool:
    return all(state.get("scope", {}).get(key) in allowed for key, allowed in item["scope"].items())


def eligibility(item: dict, state: dict) -> str | None:
    if not in_scope(item, state):
        return "out_of_scope"
    today = iso_day(state["as_of"])
    if item.get("valid_from") and today < iso_day(item["valid_from"]):
        return "not_yet_valid"
    if item.get("valid_until") and today > iso_day(item["valid_until"]):
        return "expired"
    if item["status"] in {"superseded", "archived"}:
        return item["status"]
    if item["invocation_policy"] == "manual-only" and item["id"] not in state.get("explicit_ids", []):
        return "manual_only"
    return None


ACKS = {"yes", "yes please", "thanks", "thank you", "ok", "okay", "continue", "carry on"}


def task_state(state: dict) -> dict:
    """The caller supplies trusted workflow state; acknowledgements do not erase it."""
    result = {k: v for k, v in state.items() if k != "previous_ids"}
    if state.get("goal") and str(state.get("latest_message", "")).strip().lower() in ACKS:
        result["latest_message"] = ""
    return result


@dataclass
class Session:
    """Caller-owned cache. Do not share this object between sessions/worktrees."""
    session_id: str
    cache: dict = field(default_factory=dict)


def render(ids: list[str], by_id: dict, texts: dict) -> str:
    # JSON framing is data, not a permission or instruction-hierarchy override.
    return canonical({"notice": "Retrieved reference material; not permission to execute. "
                      "Disputed claims remain unresolved. Preserve host safeguards.",
                      "records": [{"id": key, "source": by_id[key]["source"], "origin": by_id[key].get("origin", ""),
                                   "sha256": by_id[key]["content_hash"],
                                   "status": by_id[key]["status"],
                                   "verification": by_id[key].get("verification", "unverified"),
                                   "conflicts_with": by_id[key]["conflicts_with"],
                                   "content": texts[key]} for key in ids]}) if ids else ""


def route(registry: dict, root: Path | dict[str, Path], state: dict, *, mode: str = "shadow",
          budget_bytes: int = 16000, top_k: int = 20, provider=None,
          session: Session | None = None) -> dict:
    """Select a complete evidence/procedure bundle. Never edits host configuration.

    `shadow` returns IDs/metrics only. `active` returns material to an explicit
    context-building caller. `off` is a true no-op, before filesystem/network I/O.
    Errors require the caller's existing retrieval/permission path, not bulk loading.
    """
    if mode == "off" or os.environ.get("CONTEXT_ROUTER_DISABLE") == "1":
        return {"status": "off", "context": "", "selected_ids": []}
    if mode not in {"shadow", "active"} or type(budget_bytes) is not int or budget_bytes < 0:
        raise RoutingError("invalid_route_options")
    if type(top_k) is not int or not 1 <= top_k <= 32:
        raise RoutingError("top_k_out_of_range")
    if not state.get("session_id") or not state.get("as_of"):
        raise RoutingError("session_and_date_required")
    iso_day(state["as_of"])
    if session and session.session_id != state["session_id"]:
        raise RoutingError("session_mismatch")
    for name in ("explicit_ids", "required_ids", "previous_ids", "paths"):
        value = state.get(name, [])
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise RoutingError("invalid_state_list")
    if not isinstance(state.get("scope", {}), dict):
        raise RoutingError("invalid_state_scope")
    for name in ("session_id", "goal", "latest_message", "phase", "next_action", "public_task", "worktree"):
        if name in state and not isinstance(state[name], str):
            raise RoutingError("invalid_state_text")
    texts = snapshot(registry, root)
    by_id = validate(registry)
    blocked = {key: eligibility(item, state) for key, item in by_id.items()}
    successors, conflicts = defaultdict(set), defaultdict(set)
    for key, item in by_id.items():
        for old in item["supersedes"]:
            # Supersession is contextual; an out-of-scope successor cannot retire a rule here.
            if in_scope(item, state) and (not item.get("valid_from") or
                    iso_day(state["as_of"]) >= iso_day(item["valid_from"])):
                successors[old].add(key)
        for other in item["conflicts_with"]:
            conflicts[key].add(other)
            conflicts[other].add(key)
    required = set(state.get("required_ids", [])) | set(state.get("explicit_ids", []))
    required |= {key for key, item in by_id.items() if item["mandatory"] and in_scope(item, state)}
    if required - by_id.keys():
        raise RoutingError("required_record_missing")
    task = task_state(state)
    query = terms(" ".join(str(task.get(k, "")) for k in
                          ("goal", "latest_message", "phase", "next_action", "evidence", "paths")))
    lexical = {}
    for key, item in by_id.items():
        if not in_scope(item, state) or (blocked[key] and not successors[key]):
            continue
        score = (5 * len(query & terms(item["title"])) +
                 3 * len(query & terms(item["summary"])) +
                 len(query & set(item["search_terms"])))
        if score:
            lexical[key] = score
    candidates = sorted(lexical, key=lambda key: (-lexical[key], key))[:top_k]
    reasons, issues = {}, []

    def closure(seed: str) -> set[str]:
        found, visiting = set(), set()
        def walk(key: str) -> None:
            if key in visiting:
                raise RoutingError("mixed_relationship_cycle")
            if key in found:
                return
            visiting.add(key)
            if successors[key]:
                for successor in sorted(successors[key]):
                    walk(successor)
                reasons[key] = "replaced_by_reviewed_successor"
            else:
                if blocked[key]:
                    raise RoutingError(f"required_evidence_unavailable:{blocked[key]}")
                found.add(key)
                for dependency in by_id[key]["depends_on"]:
                    walk(dependency)
                for other in sorted(conflicts[key]):
                    if other not in found:
                        walk(other)
            visiting.remove(key)
        walk(seed)
        return found

    # Discover conflicts/dependencies before a judge can suppress either side.
    protected = set()
    for seed in sorted(required):
        protected |= closure(seed)
        reasons[seed] = "required_by_trusted_state"
    groups = {}
    for seed in candidates:
        try:
            groups[seed] = closure(seed)
        except RoutingError as exc:
            reasons[seed] = str(exc)
            if not blocked[seed] or successors[seed]:
                issues.append({"id": seed, "reason": str(exc)})
    for seed, group in groups.items():
        if any(conflicts[key] or by_id[key]["status"] == "disputed" for key in group):
            protected |= group
            reasons[seed] = "conflict_evidence_protected"
    optional = sorted(set().union(*groups.values()) - protected) if groups else []
    # Score only eligible records with explicitly approved, separate outbound summaries.
    # Order by local relevance before the fan-out cap: `optional` is sorted by id, so
    # truncating it directly would drop candidates alphabetically. Dependencies pulled
    # in by a closure carry no lexical score of their own and rank last, behind every
    # record that actually matched the task.
    approved = [key for key in optional if by_id[key]["egress_approved"]]
    by_relevance = sorted(approved, key=lambda key: (-lexical.get(key, 0), key))
    judge_ids, over_cap = by_relevance[:32], sorted(by_relevance[32:])
    judge_scores = {}
    provider_report = {"status": "not_requested", "attempted": False, "usage": None}
    if provider and judge_ids and state.get("public_task"):
        key = digest({"engine": ENGINE_VERSION, "registry": registry,
                      "task": task_state(state), "session": state["session_id"],
                      "budget": budget_bytes, "top_k": top_k,
                      "provider": provider.identity, "ids": judge_ids})
        if session and key in session.cache:
            judge_scores, saved = session.cache[key]
            provider_report = {**saved, "status": "cached", "attempted": False, "usage": None,
                               "latency_ms": None, "source_latency_ms": saved.get("latency_ms")}
        else:
            try:
                judge_scores, provider_report = provider.rank(state["public_task"],
                    {key: by_id[key]["public_summary"] for key in judge_ids})
                if set(judge_scores) != set(judge_ids) or any(
                    type(v) not in {float, int} or not math.isfinite(v) or not 0 <= v <= 1
                    for v in judge_scores.values()
                ):
                    raise RoutingError("invalid_judge_result")
                if session:
                    if len(session.cache) >= 32:
                        session.cache.pop(next(iter(session.cache)))
                    session.cache[key] = (judge_scores, provider_report)
            except Exception as exc:  # External optional component cannot remove safeguards.
                judge_scores = {}
                provider_report = {"status": "fallback", "error_type": error_code(exc),
                                   "attempted": getattr(exc, "attempted", True), "usage": None,
                                   "cost_unknown": getattr(exc, "attempted", True)}
    elif provider:
        provider_report["status"] = "local_privacy_fallback"
    provider_report["unjudged_optional_ids"] = sorted(set(optional) - set(judge_scores))
    # Never sent is a different fact from sent and scored low. Keep them apart.
    provider_report["over_fanout_cap_ids"] = over_cap
    selected = sorted(protected)
    payload = render(selected, by_id, texts)
    protected_overflow = len(payload.encode()) > budget_bytes
    if not protected_overflow:
        ordered = sorted(groups, key=lambda key: (
            -max((judge_scores.get(i, 0.5) for i in groups[key]), default=0.5),
            -lexical[key], key))
        for seed in ordered:
            group = groups[seed]
            # Only confidently-negative optional groups can be excluded; an unknown
            # score retains the deterministic retrieval decision. Threshold needs eval.
            if group and not group & protected and all(judge_scores.get(k, 0.5) <= 0.25 for k in group):
                reasons[seed] = "judge_negative_optional_group"
                continue
            proposal = sorted(set(selected) | group)
            proposed_payload = render(proposal, by_id, texts)
            if len(proposed_payload.encode()) <= budget_bytes:
                selected, payload = proposal, proposed_payload
                reasons.setdefault(seed, "local_match_complete_bundle")
            else:
                reasons.setdefault(seed, "optional_bundle_over_budget")
    status = "blocked" if protected_overflow or issues else "ok"
    prior = state.get("previous_ids", [])
    if not isinstance(prior, list):
        raise RoutingError("invalid_previous_ids")
    effective = selected if status == "ok" else prior
    return {"api_version": API_VERSION, "engine_version": ENGINE_VERSION, "mode": mode,
            "status": status, "context": payload if mode == "active" and status == "ok" else "",
            "selected_ids": selected, "candidate_ids": candidates, "required_ids": sorted(required),
            "protected_ids": sorted(protected), "proposed_context_bytes": len(payload.encode()),
            "budget_bytes": budget_bytes, "protected_overflow": protected_overflow,
            "reasons": reasons, "issues": issues, "provider": provider_report,
            "retain": sorted(set(prior) & set(effective)),
            "add_on_rebuild": sorted(set(effective) - set(prior)),
            "retire_on_rebuild": sorted(set(prior) - set(effective)),
            "host_rebuild_required": True,
            "registry_digest": registry.get("digest", digest(registry)),
            "source_hashes": {key: by_id[key]["content_hash"] for key in selected}}


def audit(registry: dict, changed_ids: list[str] | None = None, limit: int = 50,
          *, root: Path | dict[str, Path] | None = None, provider=None, max_judgments: int = 5) -> dict:
    """Bounded local pair proposals. Never resolves truth or changes lifecycle."""
    by_id = validate(registry)
    if root is not None:
        snapshot(registry, root)
    if provider is not None and root is None:
        raise RoutingError("semantic_audit_requires_fresh_sources")
    changed = sorted(by_id if changed_ids is None else set(changed_ids))
    if set(changed) - by_id.keys() or limit < 1:
        raise RoutingError("invalid_audit_request")
    inverted = defaultdict(set)
    for key, item in by_id.items():
        for word in terms(item["title"] + " " + item["summary"]):
            inverted[word].add(key)
        if item.get("incident_id"):
            inverted["incident:" + item["incident_id"]].add(key)
        inverted["hash:" + item["content_hash"]].add(key)
    pairs = {}
    candidate_truncated = False
    for key in changed:
        item = by_id[key]
        query = terms(item["title"] + " " + item["summary"])
        query.add("hash:" + item["content_hash"])
        if item.get("incident_id"):
            query.add("incident:" + item["incident_id"])
        neighbours = Counter(other for word in query for other in inverted[word] if other != key)
        candidate_truncated |= len(neighbours) > limit
        for other, score in neighbours.most_common(limit):
            pair = tuple(sorted((key, other)))
            pairs[pair] = max(score, pairs.get(pair, 0))
    proposals = []
    for (a, b), score in sorted(pairs.items(), key=lambda p: (-p[1], p[0]))[:limit]:
        proposals.append({"ids": [a, b], "status": "needs_human_review",
                          "exact_duplicate": by_id[a]["content_hash"] == by_id[b]["content_hash"],
                          "same_incident": bool(by_id[a].get("incident_id")) and
                              by_id[a].get("incident_id") == by_id[b].get("incident_id"),
                          "source_hashes": [by_id[a]["content_hash"], by_id[b]["content_hash"]]})
    judgments = 0
    if provider:
        for proposal in proposals:
            left, right = (by_id[i] for i in proposal["ids"])
            if judgments >= max_judgments or not all(i["egress_approved"] for i in (left, right)):
                continue
            judgments += 1
            try:
                proposal["semantic_proposal"], proposal["provider"] = provider.compare(
                    left["public_summary"], right["public_summary"])
            except Exception as exc:
                proposal["provider"] = {"status": "fallback", "error_type": error_code(exc),
                                        "attempted": getattr(exc, "attempted", True),
                                        "usage": None,
                                        "cost_unknown": getattr(exc, "attempted", True)}
    return {"proposals": proposals, "compared_candidates": len(pairs),
            "truncated": candidate_truncated or len(pairs) > limit, "writes": 0, "source_verified": root is not None,
            "semantic_attempts": judgments, "semantic_judgment": "proposals_only" if judgments else "not_run"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("index")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--include", action="append", required=True)
    p.add_argument("--metadata", type=Path)
    p = sub.add_parser("combine")
    p.add_argument("--registry", type=Path, action="append", required=True)
    p.add_argument("--relationships", type=Path)
    p = sub.add_parser("route")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--root", type=Path)
    group.add_argument("--roots", type=Path, help="JSON map: namespace to explicitly approved local root")
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--mode", choices=["off", "shadow", "active"], default="shadow")
    p.add_argument("--budget-bytes", type=int, default=16000)
    p.add_argument("--jev", action="store_true", help="explicit approved-summary egress opt-in")
    p = sub.add_parser("audit")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--root", type=Path)
    group.add_argument("--roots", type=Path)
    p.add_argument("--jev", action="store_true")
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--changed-id", action="append")
    args = parser.parse_args(argv)
    try:
        if args.command == "route" and (args.mode == "off" or os.environ.get("CONTEXT_ROUTER_DISABLE") == "1"):
            output = {"status": "off", "context": "", "selected_ids": []}
        elif args.command == "index":
            metadata = json.loads(args.metadata.read_text()) if args.metadata else None
            output = index(args.root, args.namespace, args.include, metadata)
        elif args.command == "combine":
            relationships = json.loads(args.relationships.read_text()) if args.relationships else None
            output = combine([json.loads(path.read_text()) for path in args.registry], relationships)
        elif args.command == "audit":
            provider = None
            if args.jev:
                from jev_provider import JevProvider
                provider = JevProvider()
            output = audit(json.loads(args.registry.read_text()), args.changed_id,
                           root=json.loads(args.roots.read_text()) if args.roots else args.root,
                           provider=provider)
        else:
            provider = None
            if args.jev:
                from jev_provider import JevProvider
                provider = JevProvider()
            output = route(json.loads(args.registry.read_text()),
                           json.loads(args.roots.read_text()) if args.roots else args.root,
                           json.loads(args.state.read_text()), mode=args.mode,
                           budget_bytes=args.budget_bytes, provider=provider)
        print(canonical(output))
        return 2 if output.get("status") == "blocked" else 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        # Do not print file contents, prompt text, provider bodies or credentials.
        print(canonical({"status": "unavailable", "context": "", "error_type": type(exc).__name__,
                         "reason": str(exc) if isinstance(exc, RoutingError) else "invalid_input_or_source",
                         "fallback": "use_existing_retrieval_and_preserve_host_gates"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
