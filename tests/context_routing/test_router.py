"""Synthetic regression fixtures. No claim of measured native-agent/Jev quality."""
from copy import deepcopy
from datetime import date
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/memory-hygiene/scripts"
sys.path.insert(0, str(SCRIPTS))
import context_router as cr
from jev_provider import JevProvider, ProviderError, NoRedirect


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = {"session_id": "test-session", "as_of": "2026-09-20", "goal": "deploy service",
                      "worktree": "test-tree", "scope": {"project": "alpha"}}

    def write(self, name, body="deploy service procedure", **meta):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return name, meta

    def registry(self, *entries):
        return cr.index(self.root, "test", ["**/*.md"], dict(entries))

    def record(self, registry, name):
        return next(r for r in registry["records"] if r["source"] == name)

    def run_route(self, registry, **kwargs):
        return cr.route(registry, self.root, self.state, **kwargs)


class RegistryTests(Fixture):
    def test_index_does_not_write(self):
        r = self.registry(self.write("one.md"))
        self.assertEqual(list(self.root.iterdir()), [self.root / "one.md"])
        self.assertEqual(r["records"][0]["verification"], "unverified")

    def test_no_implicit_scan(self):
        self.write("one.md")
        with self.assertRaises(cr.RoutingError): cr.index(self.root, "test", [])

    def test_empty_scan_is_not_clean(self):
        with self.assertRaises(cr.RoutingError): cr.index(self.root, "test", ["*.md"])

    def test_excluded_tree(self):
        self.write(".git/private.md")
        self.write("one.md")
        self.assertEqual(len(cr.index(self.root, "test", ["**/*.md"])["records"]), 1)

    def test_symlink_file_rejected(self):
        self.write("one.md")
        (self.root / "two.md").symlink_to(self.root / "one.md")
        with self.assertRaises(cr.RoutingError): self.registry()

    def test_symlink_directory_rejected(self):
        self.write("dir/one.md")
        (self.root / "link").symlink_to(self.root / "dir", target_is_directory=True)
        with self.assertRaises(cr.RoutingError): cr.source_path(self.root, "link/one.md")

    def test_traversal_rejected(self):
        for path in ("../one.md", "/one.md", "x\\one.md"):
            with self.subTest(path=path), self.assertRaises(cr.RoutingError):
                cr.source_path(self.root, path)

    def test_manual_control_cannot_be_relaxed(self):
        e = self.write("SKILL.md", "---\nname: manual\ndisable-model-invocation: true\n---\ndeploy")
        with self.assertRaises(cr.RoutingError):
            self.registry((e[0], {"invocation_policy": "automatic"}))

    def test_invalid_control_fails_closed(self):
        for value in ("maybe", "&flag true", "|\n true"):
            self.write("SKILL.md", "---\ndisable-model-invocation: " + value + "\n---\ndeploy")
            with self.subTest(value=value), self.assertRaises(cr.RoutingError): self.registry()

    def test_duplicate_control_fails_closed(self):
        with self.assertRaises(cr.RoutingError):
            cr.frontmatter("---\ndisable-model-invocation: true\ndisable-model-invocation: false\n---\n")

    def test_folded_description(self):
        fm = cr.frontmatter("---\nname: test\ndescription: >\n  first line\n  second line\n---\nbody")
        self.assertEqual(fm["description"], "first line second line")

    def test_unclosed_frontmatter(self):
        with self.assertRaises(cr.RoutingError): cr.frontmatter("---\nname: broken\n")

    def test_duplicate_ids(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", id="same"), self.write("b.md", id="same"))

    def test_dangling_relation(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", depends_on=["missing"], reviewed=True, relationship_evidence="review"))

    def test_unreviewed_relation(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", depends_on=["test:b.md"]), self.write("b.md"))

    def test_dependency_cycle(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", depends_on=["test:b.md"], reviewed=True, relationship_evidence="review"),
                          self.write("b.md", depends_on=["test:a.md"], reviewed=True, relationship_evidence="review"))

    def test_supersession_cycle(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", supersedes=["test:b.md"], reviewed=True, relationship_evidence="review"),
                          self.write("b.md", supersedes=["test:a.md"], reviewed=True, relationship_evidence="review"))

    def test_bad_validity(self):
        for meta in ({"valid_from": "yesterday"}, {"valid_until": "20260920"},
                     {"valid_from": "2026-09-20", "valid_until": "2026-09-19"}):
            with self.subTest(meta=meta), self.assertRaises(ValueError): self.registry(self.write("a.md", **meta))

    def test_source_change_requires_reindex(self):
        r = self.registry(self.write("a.md"))
        self.write("a.md", "changed")
        with self.assertRaises(cr.RoutingError): self.run_route(r)

    def test_added_source_requires_reindex(self):
        r = self.registry(self.write("a.md"))
        self.write("b.md")
        with self.assertRaises(cr.RoutingError): self.run_route(r)

    def test_deleted_source_requires_reindex(self):
        r = self.registry(self.write("a.md"))
        (self.root / "a.md").unlink()
        with self.assertRaises(cr.RoutingError): self.run_route(r)

    def test_registry_tamper_detected(self):
        r = self.registry(self.write("a.md"))
        r["records"][0]["summary"] = "tampered"
        with self.assertRaises(cr.RoutingError): self.run_route(r)

    def test_unknown_metadata(self):
        with self.assertRaises(cr.RoutingError): self.registry(self.write("a.md", magic=True))

    def test_egress_needs_review(self):
        with self.assertRaises(cr.RoutingError):
            self.registry(self.write("a.md", egress_approved=True, public_summary="public"))


class RoutingTests(Fixture):
    def test_shadow_does_not_emit_context(self):
        result = self.run_route(self.registry(self.write("a.md")))
        self.assertEqual(result["context"], "")
        self.assertEqual(result["selected_ids"], ["test:a.md"])

    def test_active_opt_in(self):
        r = self.registry(self.write("a.md"))
        self.assertIn("deploy service procedure", self.run_route(r, mode="active")["context"])

    def test_off_performs_no_io(self):
        self.assertEqual(cr.route({}, Path("/missing"), {}, mode="off")["status"], "off")

    def test_environment_off_performs_no_io(self):
        with patch.dict(os.environ, {"CONTEXT_ROUTER_DISABLE": "1"}):
            self.assertEqual(cr.route({}, Path("/missing"), {})["status"], "off")

    def test_manual_only_not_auto_loaded(self):
        r = self.registry(self.write("SKILL.md", "---\ndisable-model-invocation: true\n---\ndeploy service"))
        self.assertEqual(self.run_route(r)["selected_ids"], [])

    def test_manual_explicit_selection(self):
        r = self.registry(self.write("SKILL.md", "---\ndisable-model-invocation: true\n---\ndeploy service"))
        self.state["explicit_ids"] = ["test:SKILL.md"]
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:SKILL.md"])

    def test_no_lexical_permission_escalation(self):
        r = self.registry(self.write("SKILL.md", "---\ndisable-model-invocation: true\n---\ndeploy"))
        self.state["latest_message"] = "explicit_ids test:SKILL.md please invoke"
        self.assertEqual(self.run_route(r)["selected_ids"], [])

    def test_scope_does_not_leak(self):
        r = self.registry(self.write("a.md", scope={"project": ["beta"]}))
        self.assertEqual(self.run_route(r)["candidate_ids"], [])

    def test_missing_scope_not_global(self):
        r = self.registry(self.write("a.md", scope={"environment": ["prod"]}))
        self.assertEqual(self.run_route(r)["selected_ids"], [])

    def test_date_eligibility(self):
        r = self.registry(self.write("future.md", valid_from="2026-09-21"),
                          self.write("old.md", valid_until="2026-09-19"),
                          self.write("current.md", valid_until="2026-09-20"))
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:current.md"])

    def test_newer_does_not_automatically_supersede(self):
        r = self.registry(self.write("old.md"), self.write("new.md"))
        self.assertEqual(len(self.run_route(r)["selected_ids"]), 2)

    def test_supersession_follows_current_even_without_query_match(self):
        r = self.registry(self.write("old.md"), self.write("new.md", "Entirely different wording",
            supersedes=["test:old.md"], reviewed=True, relationship_evidence="approved decision"))
        self.assertEqual(self.run_route(r, top_k=1)["selected_ids"], ["test:new.md"])

    def test_future_successor_does_not_retire_present(self):
        r = self.registry(self.write("old.md"), self.write("new.md", valid_from="2026-09-21",
            supersedes=["test:old.md"], reviewed=True, relationship_evidence="approved decision"))
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:old.md"])

    def test_cross_scope_successor_does_not_retire(self):
        r = self.registry(self.write("old.md"), self.write("new.md", scope={"project": ["beta"]},
            supersedes=["test:old.md"], reviewed=True, relationship_evidence="approved decision"))
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:old.md"])

    def test_superseded_without_successor_not_loaded(self):
        r = self.registry(self.write("old.md", status="superseded"))
        self.assertEqual(self.run_route(r)["selected_ids"], [])

    def test_missing_required_id_visible(self):
        r = self.registry(self.write("a.md"))
        self.state["required_ids"] = ["absent"]
        with self.assertRaises(cr.RoutingError): self.run_route(r)

    def test_dependency_is_loaded(self):
        r = self.registry(self.write("a.md", depends_on=["test:b.md"], reviewed=True,
                                     relationship_evidence="review"), self.write("b.md", "prerequisite"))
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:a.md", "test:b.md"])

    def test_dependency_cannot_bypass_manual_only(self):
        r = self.registry(self.write("a.md", depends_on=["test:b.md"], reviewed=True,
            relationship_evidence="review"), self.write("b.md", "---\ndisable-model-invocation: true\n---\nprerequisite"))
        result = self.run_route(r, mode="active")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["context"], "")

    def test_conflict_pair_protected(self):
        r = self.registry(self.write("a.md", conflicts_with=["test:b.md"], reviewed=True,
            relationship_evidence="conflict unresolved"), self.write("b.md", "different cause"))
        result = self.run_route(r, top_k=1)
        self.assertEqual(result["protected_ids"], ["test:a.md", "test:b.md"])

    def test_conflict_overflow_blocks_not_half_load(self):
        r = self.registry(self.write("a.md", conflicts_with=["test:b.md"], reviewed=True,
            relationship_evidence="review"), self.write("b.md", "different cause"))
        result = self.run_route(r, mode="active", budget_bytes=1)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["protected_overflow"])
        self.assertEqual(result["context"], "")

    def test_mandatory_survives_no_match(self):
        r = self.registry(self.write("guard.md", "always check provenance", mandatory=True, reviewed=True))
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:guard.md"])

    def test_whole_optional_bundle_or_nothing(self):
        r = self.registry(self.write("large.md", "deploy " * 1000))
        result = self.run_route(r, mode="active", budget_bytes=100)
        self.assertEqual(result["selected_ids"], [])
        self.assertLessEqual(len(result["context"].encode()), 100)

    def test_exact_byte_budget_includes_wrappers(self):
        r = self.registry(self.write("a.md"))
        size = self.run_route(r)["proposed_context_bytes"]
        self.assertEqual(len(self.run_route(r, mode="active", budget_bytes=size)["context"].encode()), size)
        self.assertEqual(self.run_route(r, budget_bytes=size - 1)["selected_ids"], [])

    def test_acknowledgement_retains_goal(self):
        r = self.registry(self.write("a.md"))
        self.state["latest_message"] = "yes please"
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:a.md"])

    def test_no_goal_no_spurious_match_from_state_keys(self):
        r = self.registry(self.write("a.md", "project source scope state date id"))
        self.state["goal"] = ""
        self.state["latest_message"] = "thanks"
        self.assertEqual(self.run_route(r)["selected_ids"], [])

    def test_chinese_local_retrieval(self):
        r = self.registry(self.write("a.md", "并行会话需要工作树隔离"))
        self.state["goal"] = "工作树"
        self.assertEqual(self.run_route(r)["selected_ids"], ["test:a.md"])

    def test_retirement_only_proposed_for_rebuild(self):
        r = self.registry(self.write("a.md"))
        self.state["previous_ids"] = ["old"]
        result = self.run_route(r)
        self.assertEqual(result["retire_on_rebuild"], ["old"])
        self.assertTrue(result["host_rebuild_required"])

    def test_blocked_does_not_retire_prior_context(self):
        r = self.registry(self.write("a.md", mandatory=True, reviewed=True))
        self.state["previous_ids"] = ["guard"]
        result = self.run_route(r, budget_bytes=1)
        self.assertEqual(result["retire_on_rebuild"], [])

    def test_bad_state_lists_rejected(self):
        r = self.registry(self.write("a.md"))
        self.state["required_ids"] = "test:a.md"
        with self.assertRaises(cr.RoutingError): self.run_route(r)


class ProviderTests(Fixture):
    def public_registry(self):
        return self.registry(self.write("a.md", reviewed=True, egress_approved=True,
                                       public_summary="Deployment procedure"))

    def fake(self, score=0.9):
        self.calls = []
        def transport(payload):
            self.calls.append(payload)
            return {"model": "jev-1.13.0", "answers": {
                key: {"type": "noul", "noul": score} for key in payload["questions"]},
                "usage": {"input_tokens": 20, "output_tokens": 0}}
        return JevProvider(transport=transport)

    def test_no_egress_by_default(self):
        p = self.fake()
        self.state["public_task"] = "Deploy a service"
        self.run_route(self.registry(self.write("a.md")), provider=p)
        self.assertEqual(self.calls, [])

    def test_explicit_public_task_required(self):
        p = self.fake()
        self.run_route(self.public_registry(), provider=p)
        self.assertEqual(self.calls, [])

    def test_only_public_fields_leave(self):
        p = self.fake()
        self.state["public_task"] = "Deploy a service"
        self.state["evidence"] = "PRIVATE_INTERNAL_IDENTIFIER"
        self.run_route(self.public_registry(), provider=p)
        sent = json.dumps(self.calls)
        self.assertNotIn("PRIVATE_INTERNAL_IDENTIFIER", sent)
        self.assertNotIn("test:a.md", sent)
        self.assertNotIn("deploy service procedure", sent)
        self.assertEqual(self.calls[0]["questions"]["q0"]["type"], "noul")

    def test_provider_failure_falls_back(self):
        p = self.fake()
        p.transport = lambda payload: (_ for _ in ()).throw(TimeoutError("private failure body"))
        self.state["public_task"] = "Deploy a service"
        result = self.run_route(self.public_registry(), provider=p)
        self.assertEqual(result["selected_ids"], ["test:a.md"])
        self.assertNotIn("private failure body", json.dumps(result))
        self.assertIsNone(result["provider"]["usage"])

    def test_negative_can_drop_only_optional(self):
        p = self.fake(0.01)
        self.state["public_task"] = "Unrelated request"
        self.assertEqual(self.run_route(self.public_registry(), provider=p)["selected_ids"], [])

    def test_uncertain_retains_local(self):
        p = self.fake(0.5)
        self.state["public_task"] = "Deploy"
        self.assertEqual(self.run_route(self.public_registry(), provider=p)["selected_ids"], ["test:a.md"])

    def test_pinned_records_not_judged(self):
        p = self.fake(0.01)
        r = self.public_registry()
        self.state.update(public_task="Unrelated", required_ids=["test:a.md"])
        self.assertEqual(self.run_route(r, provider=p)["selected_ids"], ["test:a.md"])
        self.assertEqual(self.calls, [])

    def test_cache_reuses_acknowledgement(self):
        p = self.fake()
        r = self.public_registry()
        session = cr.Session("test-session")
        self.state["public_task"] = "Deploy"
        self.state["latest_message"] = "yes"
        self.run_route(r, provider=p, session=session)
        self.state["latest_message"] = "thanks"
        result = self.run_route(r, provider=p, session=session)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["provider"]["status"], "cached")
        self.assertIsNone(result["provider"]["usage"])

    def test_cache_invalidates_on_semantic_state_or_budget(self):
        p = self.fake()
        r = self.public_registry()
        session = cr.Session("test-session")
        self.state["public_task"] = "Deploy"
        self.run_route(r, provider=p, session=session)
        for key, value in (("phase", "merge"), ("source_revision", "new"),
                           ("context_window", 50000), ("worktree", "other"), ("policy_revision", "new")):
            self.state[key] = value
            self.run_route(r, provider=p, session=session)
        self.run_route(r, provider=p, session=session, budget_bytes=15000)
        self.assertEqual(len(self.calls), 7)

    def test_session_mismatch_rejected(self):
        with self.assertRaises(cr.RoutingError):
            self.run_route(self.public_registry(), session=cr.Session("other"))

    def test_partial_reply_falls_back(self):
        p = JevProvider(transport=lambda _: {"model": "jev-1.13.0", "answers": {}})
        self.state["public_task"] = "Deploy"
        self.assertEqual(self.run_route(self.public_registry(), provider=p)["provider"]["status"], "fallback")

    def test_invalid_noul(self):
        for value in (float("nan"), float("inf"), True, -1, 2, "0.9"):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.fake(value).rank("Deploy", {"a": "Deployment"})

    def test_response_model_must_match(self):
        p = JevProvider(transport=lambda _: {"model": "other", "answers": {}})
        with self.assertRaises(ProviderError): p.rank("Deploy", {"a": "Deployment"})

    def test_alias_refused(self):
        with self.assertRaises(ProviderError): JevProvider(model="jev-latest")

    def test_encoded_limit_not_character_limit(self):
        p = self.fake()
        with self.assertRaises(ProviderError): p.rank("汉" * 10000, {"a": "Deployment"})
        self.assertEqual(self.calls, [])

    def test_credential_screen_before_transport(self):
        p = self.fake()
        with self.assertRaises(ProviderError): p.rank("api_key: synthetic-danger-value", {"a": "Deploy"})
        self.assertEqual(self.calls, [])

    def test_redirect_refused(self):
        with self.assertRaises(ProviderError): NoRedirect().redirect_request(None, None, 302, None, None, "https://other.test")

    def test_unknown_usage_not_zero(self):
        p = JevProvider(transport=lambda _: {"model": "jev-1.13.0", "answers": {"q0": {"type": "noul", "noul": .8}}})
        _, report = p.rank("Deploy", {"a": "Deployment"})
        self.assertIsNone(report["usage"])
        self.assertTrue(report["cost_unknown"])


class AuditTests(Fixture):
    def test_duplicate_proposal_does_not_delete(self):
        r = self.registry(self.write("a.md"), self.write("b.md"))
        result = cr.audit(r, root=self.root)
        self.assertTrue(result["proposals"][0]["exact_duplicate"])
        self.assertEqual(result["writes"], 0)
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)

    def test_changed_id_bound(self):
        r = self.registry(*(self.write(f"{i}.md") for i in range(8)))
        result = cr.audit(r, changed_ids=["test:0.md"], limit=2)
        self.assertEqual(len(result["proposals"]), 2)
        self.assertTrue(all("test:0.md" in p["ids"] for p in result["proposals"]))

    def test_semantic_audit_needs_verified_snapshot(self):
        with self.assertRaises(cr.RoutingError):
            cr.audit(self.registry(self.write("a.md")), provider=JevProvider())

    def test_semantic_proposal_never_becomes_approved_edge(self):
        e = dict(reviewed=True, egress_approved=True, public_summary="Deployment rule")
        r = self.registry(self.write("a.md", **e), self.write("b.md", **e))
        before = cr.canonical(r)
        p = JevProvider(transport=lambda payload: {"model": "jev-1.13.0", "answers": {
            key: {"type": "noul", "noul": .99} for key in payload["questions"]}})
        result = cr.audit(r, root=self.root, provider=p)
        self.assertEqual(result["semantic_attempts"], 1)
        self.assertEqual(result["proposals"][0]["status"], "needs_human_review")
        self.assertEqual(before, cr.canonical(r))



class MultiRootTests(Fixture):
    def make_two(self):
        self.write("one.md")
        other = self.root / "second"
        other.mkdir()
        (other / "two.md").write_text("Deployment dependent procedure")
        a = cr.index(self.root, "a", ["*.md"])
        b = cr.index(other, "b", ["*.md"])
        return a, b, {"a": self.root, "b": other}

    def test_one_budget_across_roots(self):
        a, b, roots = self.make_two()
        r = cr.combine([a, b])
        result = cr.route(r, roots, self.state, mode="active", budget_bytes=800)
        self.assertLessEqual(len(result["context"].encode()), 800)
        self.assertNotIn(str(self.root), cr.canonical(r))

    def test_cross_root_dependency(self):
        a, b, roots = self.make_two()
        r = cr.combine([a, b], {"a:one.md": {"depends_on": ["b:two.md"], "reviewed": True,
                                            "relationship_evidence": "Owner approved cross-store dependency"}})
        self.state["required_ids"] = ["a:one.md"]
        result = cr.route(r, roots, self.state)
        self.assertEqual(result["protected_ids"], ["a:one.md", "b:two.md"])

    def test_cross_root_conflict(self):
        a, b, roots = self.make_two()
        r = cr.combine([a, b], {"a:one.md": {"conflicts_with": ["b:two.md"], "reviewed": True,
                                            "relationship_evidence": "Unresolved scope-matched disagreement"}})
        result = cr.route(r, roots, self.state, budget_bytes=1)
        self.assertTrue(result["protected_overflow"])

    def test_duplicate_namespace_refused(self):
        a, _, _ = self.make_two()
        with self.assertRaises(cr.RoutingError): cr.combine([a, a])

    def test_missing_root_refused(self):
        a, b, roots = self.make_two()
        with self.assertRaises(cr.RoutingError): cr.route(cr.combine([a, b]), {"a": roots["a"]}, self.state)

    def test_second_root_change_invalidates(self):
        a, b, roots = self.make_two()
        r = cr.combine([a, b])
        (roots["b"] / "two.md").write_text("new source")
        with self.assertRaises(cr.RoutingError): cr.route(r, roots, self.state)

    def test_cross_root_metadata_cannot_relax_invocation(self):
        a, b, _ = self.make_two()
        with self.assertRaises(cr.RoutingError):
            cr.combine([a, b], {"a:one.md": {"invocation_policy": "automatic"}})

    def test_bom_crlf_control_is_preserved(self):
        (self.root / "SKILL.md").write_bytes(b'\xef\xbb\xbf---\r\ndisable-model-invocation: true\r\n---\r\ndeploy service')
        r = cr.index(self.root, "test", ["*.md"])
        self.assertEqual(self.run_route(r)["selected_ids"], [])
        self.assertEqual(r["records"][0]["content_hash"], __import__('hashlib').sha256((self.root / "SKILL.md").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
