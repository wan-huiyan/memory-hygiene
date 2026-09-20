"""Frozen-case replay and honest A/native, B/local, C/Jev scoring.

Native-agent observations must be imported from actual runs; absent arms, usage
and end-to-end outcomes stay unknown. Synthetic regression tests are not evidence
of model quality or subscription savings. No automatic tuning or activation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics
import time

import context_router as cr

ARMS = ("A-native", "B-local", "C-jev")


def validate_cases(cases: list[dict]) -> None:
    if not cases:
        raise ValueError("empty_evaluation")
    ids, families = set(), {}
    for case in cases:
        if not case.get("id") or case["id"] in ids:
            raise ValueError("missing_or_duplicate_case_id")
        ids.add(case["id"])
        for field in ("family", "split", "source_revision", "label_provenance"):
            if not isinstance(case.get(field), str) or not case[field]:
                raise ValueError("missing_evaluation_provenance")
        if case["split"] not in {"train", "test"}:
            raise ValueError("invalid_split")
        if case["family"] in families and families[case["family"]] != case["split"]:
            raise ValueError("family_leakage_across_train_test")
        families[case["family"]] = case["split"]
        for field in ("required_ids", "forbidden_ids", "conflict_pairs"):
            if not isinstance(case.get(field), list):
                raise ValueError("missing_expected_outcomes")
        if set(case["required_ids"]) & set(case["forbidden_ids"]):
            raise ValueError("contradictory_evaluation_labels")
        if any(not isinstance(p, list) or len(p) != 2 for p in case["conflict_pairs"]):
            raise ValueError("invalid_conflict_pair")


def replay(cases: list[dict], registry: dict, roots, *, provider=None) -> list[dict]:
    validate_cases(cases)
    observations = []
    for case in cases:
        started = time.perf_counter()
        result = cr.route(registry, roots, case["state"], mode="shadow", provider=provider,
                          budget_bytes=case.get("budget_bytes", 16000))
        observations.append({"case_id": case["id"], "arm": "C-jev" if provider else "B-local",
            "source_revision": case["source_revision"], "registry_digest": result["registry_digest"],
            "selected_ids": result["selected_ids"] if result["status"] == "ok" else [],
            "candidate_ids": result["candidate_ids"], "status": result["status"],
            "latency_ms": 1000 * (time.perf_counter() - started),
            "context_bytes": result["proposed_context_bytes"], "provider": result["provider"],
            "input_tokens": None, "cached_input_tokens": None, "task_success": None})
    return observations


def score(cases: list[dict], observations: list[dict]) -> dict:
    validate_cases(cases)
    expected = {case["id"]: case for case in cases}
    seen, groups = set(), {arm: [] for arm in ARMS}
    for observation in observations:
        key = observation.get("case_id"), observation.get("arm")
        if key in seen or key[0] not in expected or key[1] not in ARMS:
            raise ValueError("duplicate_or_unknown_observation")
        seen.add(key)
        if observation.get("source_revision") != expected[key[0]]["source_revision"]:
            raise ValueError("observation_source_revision_mismatch")
        if not isinstance(observation.get("selected_ids"), list):
            raise ValueError("missing_selection_observation")
        groups[key[1]].append(observation)
    result = {"case_count": len(cases), "arms": {}, "activation": "requires_human_review"}
    for arm, rows in groups.items():
        if not rows:
            result["arms"][arm] = {"status": "not_run", "evaluated": 0}
            continue
        hits = total = forbidden = partial_conflicts = protected_pairs = pair_total = blocked = 0
        retrieval_hits = retrieval_total = 0
        for row in rows:
            case = expected[row["case_id"]]
            selected = set(row["selected_ids"])
            required = set(case["required_ids"])
            hits += len(selected & required)
            total += len(required)
            forbidden += len(selected & set(case["forbidden_ids"]))
            blocked += row.get("status") in {"blocked", "unavailable", "preflight_required"}
            if row.get("candidate_ids") is not None:
                retrieval_hits += len(set(row["candidate_ids"]) & required)
                retrieval_total += len(required)
            for pair in case["conflict_pairs"]:
                loaded = len(selected & set(pair))
                partial_conflicts += loaded == 1
                protected_pairs += loaded == 2
                pair_total += 1
        usage = [r["input_tokens"] for r in rows if r.get("input_tokens") is not None]
        latency = sorted(r["latency_ms"] for r in rows if r.get("latency_ms") is not None)
        success = [r["task_success"] for r in rows if type(r.get("task_success")) is bool]
        result["arms"][arm] = {
            "status": "complete" if len(rows) == len(cases) else "partial", "evaluated": len(rows),
            "missing_case_ids": sorted(set(expected) - {r["case_id"] for r in rows}),
            "required_coverage": hits / total if total else None,
            "candidate_recall": retrieval_hits / retrieval_total if retrieval_total else None,
            "forbidden_loads": forbidden, "partial_conflicts": partial_conflicts,
            "conflict_pair_coverage": protected_pairs / pair_total if pair_total else None,
            "blocked_count": blocked, "input_tokens_total": sum(usage) if len(usage) == len(rows) else None,
            "input_token_observations": len(usage),
            "latency_p50_ms": statistics.median(latency) if latency else None,
            "latency_p95_ms": latency[max(0, __import__('math').ceil(.95 * len(latency)) - 1)] if latency else None,
            "task_success_rate": sum(success) / len(success) if success else None,
            "task_success_observations": len(success),
            "jev_live_or_cached": sum(r.get("provider", {}).get("status") in {"live", "cached"} for r in rows),
            "warning": "Context bytes are not billed tokens; partial observations are not a full comparison."}
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("replay")
    q.add_argument("--cases", type=Path, required=True)
    q.add_argument("--registry", type=Path, required=True)
    roots = q.add_mutually_exclusive_group(required=True)
    roots.add_argument("--root", type=Path)
    roots.add_argument("--roots", type=Path)
    q.add_argument("--jev", action="store_true")
    q = sub.add_parser("score")
    q.add_argument("--cases", type=Path, required=True)
    q.add_argument("--observations", type=Path, required=True, action="append")
    args = p.parse_args(argv)
    cases = json.loads(args.cases.read_text())
    if args.command == "score":
        observations = [row for path in args.observations for row in json.loads(path.read_text())]
        result = score(cases, observations)
    else:
        provider = None
        if args.jev:
            from jev_provider import JevProvider
            provider = JevProvider()
        roots = json.loads(args.roots.read_text()) if args.roots else args.root
        result = replay(cases, json.loads(args.registry.read_text()), roots, provider=provider)
    print(cr.canonical(result))


if __name__ == "__main__":
    main()
