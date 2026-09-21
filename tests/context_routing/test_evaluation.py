from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/memory-hygiene/scripts"))
import context_router_eval as ev


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases = [{"id": "case-a", "family": "conflict-a", "split": "test", "source_revision": "frozen-1",
                       "label_provenance": "synthetic-regression-only", "required_ids": ["a", "b"],
                       "forbidden_ids": ["old"], "conflict_pairs": [["a", "b"]]}]
        self.rows = [{"case_id": "case-a", "arm": "B-local", "source_revision": "frozen-1",
                      "selected_ids": ["a", "b"], "candidate_ids": ["a"], "status": "ok"}]

    def test_absent_arms_not_fabricated(self):
        result = ev.score(self.cases, self.rows)
        self.assertEqual(result["arms"]["A-native"]["status"], "not_run")
        self.assertEqual(result["arms"]["C-jev"]["status"], "not_run")

    def test_unmeasured_usage_and_success_unknown(self):
        arm = ev.score(self.cases, self.rows)["arms"]["B-local"]
        self.assertIsNone(arm["input_tokens_total"])
        self.assertIsNone(arm["task_success_rate"])

    def test_retrieval_and_final_coverage_separate(self):
        arm = ev.score(self.cases, self.rows)["arms"]["B-local"]
        self.assertEqual(arm["candidate_recall"], .5)
        self.assertEqual(arm["required_coverage"], 1)

    def test_partial_conflict_detected(self):
        self.rows[0]["selected_ids"] = ["a"]
        self.assertEqual(ev.score(self.cases, self.rows)["arms"]["B-local"]["partial_conflicts"], 1)

    def test_forbidden_and_blocked_not_hidden(self):
        self.rows[0].update(selected_ids=["old"], status="blocked")
        arm = ev.score(self.cases, self.rows)["arms"]["B-local"]
        self.assertEqual(arm["forbidden_loads"], 1)
        self.assertEqual(arm["blocked_count"], 1)

    def test_no_family_leakage(self):
        extra = {**self.cases[0], "id": "case-b", "split": "train"}
        with self.assertRaises(ValueError): ev.validate_cases(self.cases + [extra])

    def test_no_revision_mismatch(self):
        self.rows[0]["source_revision"] = "different"
        with self.assertRaises(ValueError): ev.score(self.cases, self.rows)

    def test_missing_cases_named(self):
        extra = {**self.cases[0], "id": "case-b"}
        arm = ev.score(self.cases + [extra], self.rows)["arms"]["B-local"]
        self.assertEqual(arm["status"], "partial")
        self.assertEqual(arm["missing_case_ids"], ["case-b"])

    def test_duplicate_observations_rejected(self):
        with self.assertRaises(ValueError): ev.score(self.cases, self.rows * 2)

    def test_empty_evaluation_not_pass(self):
        with self.assertRaises(ValueError): ev.score([], [])
