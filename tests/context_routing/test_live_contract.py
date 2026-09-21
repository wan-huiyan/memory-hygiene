"""Replay of REAL TypeSafe Jev responses captured 2026-09-21.

Every other Jev test in this suite injects a transport written by hand to satisfy
the validator under test, so it can only prove the validator agrees with its own
author. These tests replay verbatim server responses instead, which is what makes
them capable of failing if the live contract moves.

Offline and deterministic: no network, no API key. Re-capture the fixture per
tests/context_routing/fixtures/README.md when the contract changes.
"""
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/memory-hygiene/scripts"
sys.path.insert(0, str(SCRIPTS))
from jev_provider import JevProvider, ProviderError, MODEL

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "jev_live_responses.json").read_text())


class LiveContractReplay(unittest.TestCase):
    """The shipped validator against bytes the real API actually returned."""

    def replay(self, case):
        recorded = FIXTURE[case]["response"]
        return JevProvider(transport=lambda _payload: recorded)

    def test_recorded_rank_response_is_accepted(self):
        scores, report = self.replay("rank").rank(
            FIXTURE["rank"]["request"]["state"]["task"],
            {"mem-a": "Procedure for rotating database credentials in staging.",
             "mem-b": "Notes on choosing chart colours for the quarterly dashboard."})
        self.assertEqual(report["status"], "live")
        self.assertEqual(report["resolved_model"], MODEL)
        self.assertFalse(report["cost_unknown"])
        self.assertEqual(set(scores), {"mem-a", "mem-b"})
        for value in scores.values():
            self.assertIsInstance(value, float)
            self.assertTrue(0.0 <= value <= 1.0)

    def test_recorded_rank_scores_discriminate(self):
        """The captured call ranked the relevant record above the irrelevant one."""
        answers = FIXTURE["rank"]["response"]["answers"]
        self.assertGreater(answers["q0"]["noul"], answers["q1"]["noul"])

    def test_recorded_compare_response_is_accepted(self):
        values, report = self.replay("compare").compare(
            FIXTURE["compare"]["request"]["state"]["left"],
            FIXTURE["compare"]["request"]["state"]["right"])
        self.assertEqual(report["status"], "live")
        self.assertEqual(set(values), {"contradiction", "overlap"})

    def test_recorded_usage_shape_matches_validator(self):
        """Real usage carries int input_tokens/output_tokens, so spend is knowable."""
        for case in ("rank", "compare"):
            usage = FIXTURE[case]["response"]["usage"]
            self.assertIsInstance(usage["input_tokens"], int)
            self.assertIsInstance(usage["output_tokens"], int)

    def test_api_echoes_resolved_version_never_the_alias(self):
        """Why the version pin is required rather than cosmetic.

        Requesting the alias `jev-latest` returns `model: jev-1.13.0`. The provider
        asserts `response["model"] == self.model`, so a provider permitted to send
        `jev-latest` would raise unexpected_model on every live call. The
        constructor regex is what prevents that.
        """
        self.assertEqual(FIXTURE["alias_probe"]["requested_model"], "jev-latest")
        self.assertEqual(FIXTURE["alias_probe"]["response_model"], MODEL)
        self.assertNotEqual(FIXTURE["alias_probe"]["requested_model"],
                            FIXTURE["alias_probe"]["response_model"])
        with self.assertRaises(ProviderError):
            JevProvider(model="jev-latest")

    def test_pinned_model_round_trips(self):
        """The pinned request model is echoed back unchanged, so the check passes."""
        for case in ("rank", "compare"):
            self.assertEqual(FIXTURE[case]["request"]["model"], MODEL)
            self.assertEqual(FIXTURE[case]["response"]["model"], MODEL)

    def test_recorded_response_fails_a_wrongly_pinned_provider(self):
        """Guard against the fixture passing trivially: a different pin must reject it."""
        provider = JevProvider(model="jev-9.99.9",
                               transport=lambda _p: FIXTURE["rank"]["response"])
        with self.assertRaises(ProviderError) as caught:
            provider.compare("left summary", "right summary")
        self.assertIn("unexpected_model", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
