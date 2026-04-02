/**
 * Eval Suite Integrity Tests — Generalized Template
 *
 * Validates the structural quality of eval-suite.json:
 * - All triggers/test_cases/edge_cases have required fields
 * - All regex patterns compile
 * - All assertion types are valid
 * - Trigger balance (positive/negative ratio)
 * - Edge cases have expected_behavior descriptions
 *
 * Handles schema variations: skill_name vs skill, presence/absence of
 * test_cases, edge_cases, and assertions arrays.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

const evalSuitePath = resolve(ROOT, "eval-suite.json");
if (!existsSync(evalSuitePath)) {
  describe("Eval suite integrity", () => {
    it("eval-suite.json not present — skipping", { skip: "no eval-suite.json" }, () => {});
  });
} else {
  const evalSuite = JSON.parse(readFileSync(evalSuitePath, "utf-8"));

  // ---------------------------------------------------------------------------
  // Trigger validation
  // ---------------------------------------------------------------------------

  if (evalSuite.triggers && evalSuite.triggers.length > 0) {
    describe("Trigger structure", () => {
      for (const trigger of evalSuite.triggers) {
        it(`trigger ${trigger.id || "(no id)"} is well-formed`, () => {
          assert.ok(trigger.prompt, "trigger must have a prompt");
          assert.ok(
            typeof trigger.should_trigger === "boolean",
            "should_trigger must be boolean"
          );
        });
      }

      it("has balanced positive vs negative triggers", () => {
        const positives = evalSuite.triggers.filter((t) => t.should_trigger).length;
        const negatives = evalSuite.triggers.filter((t) => !t.should_trigger).length;
        const total = positives + negatives;
        assert.ok(
          positives / total >= 0.25,
          `Should have at least 25% positive triggers (got ${((positives / total) * 100).toFixed(0)}%)`
        );
        assert.ok(
          negatives / total >= 0.15,
          `Should have at least 15% negative triggers (got ${((negatives / total) * 100).toFixed(0)}%)`
        );
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Test case assertion validation
  // ---------------------------------------------------------------------------

  if (evalSuite.test_cases && evalSuite.test_cases.length > 0) {
    describe("Test case assertions", () => {
      const validTypes = ["pattern", "excludes", "contains", "format", "response_excludes", "response_contains", "response_pattern"];

      describe("Assertion types are valid", () => {
        for (const tc of evalSuite.test_cases) {
          if (tc.assertions) {
            for (const assertion of tc.assertions) {
              it(`${tc.id || tc.prompt?.slice(0, 40)} — type "${assertion.type}"`, () => {
                assert.ok(
                  validTypes.includes(assertion.type),
                  `assertion type "${assertion.type}" must be one of: ${validTypes.join(", ")}`
                );
              });
            }
          }
        }
      });

      describe("Pattern assertions compile as valid regexes", () => {
        for (const tc of evalSuite.test_cases) {
          if (tc.assertions) {
            for (const assertion of tc.assertions) {
              if (assertion.type === "pattern") {
                it(`${tc.id || "?"} — ${assertion.description || assertion.value}`, () => {
                  const cleaned = assertion.value.replace(/^\(\?i\)/, "");
                  assert.doesNotThrow(
                    () => new RegExp(cleaned, "i"),
                    `Pattern "${assertion.value}" must be a valid regex`
                  );
                  // Verify non-trivial (doesn't match empty string)
                  const regex = new RegExp(cleaned, "i");
                  assert.equal(
                    regex.test(""),
                    false,
                    `Pattern "${assertion.value}" should not match empty string`
                  );
                });
              }
            }
          }
        }
      });

      describe("Excludes assertions are non-empty", () => {
        for (const tc of evalSuite.test_cases) {
          if (tc.assertions) {
            for (const assertion of tc.assertions) {
              if (assertion.type === "excludes") {
                it(`${tc.id || "?"} — ${assertion.description || assertion.value}`, () => {
                  assert.ok(
                    assertion.value && assertion.value.length > 0,
                    "excludes value must be non-empty"
                  );
                });
              }
            }
          }
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Edge case validation
  // ---------------------------------------------------------------------------

  if (evalSuite.edge_cases && evalSuite.edge_cases.length > 0) {
    describe("Edge case validation", () => {
      describe("Edge cases have expected_behavior", () => {
        for (const ec of evalSuite.edge_cases) {
          it(`${ec.id || ec.prompt?.slice(0, 40)} has expected_behavior`, () => {
            assert.ok(
              ec.expected_behavior,
              "edge case must have expected_behavior"
            );
            assert.ok(
              ec.expected_behavior.length > 5,
              "expected_behavior should be descriptive"
            );
          });
        }
      });

      describe("Edge cases have assertions", () => {
        for (const ec of evalSuite.edge_cases) {
          it(`${ec.id || ec.prompt?.slice(0, 40)} has assertions`, () => {
            assert.ok(
              ec.assertions && ec.assertions.length > 0,
              "edge case must have at least one assertion"
            );
          });
        }
      });

      describe("Edge case pattern assertions compile", () => {
        for (const ec of evalSuite.edge_cases) {
          if (ec.assertions) {
            for (const assertion of ec.assertions) {
              if (assertion.type === "pattern") {
                it(`${ec.id || "?"} — ${assertion.description || assertion.value}`, () => {
                  const cleaned = assertion.value.replace(/^\(\?i\)/, "");
                  assert.doesNotThrow(
                    () => new RegExp(cleaned, "i"),
                    `Pattern "${assertion.value}" must be a valid regex`
                  );
                });
              }
            }
          }
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Flat assertions validation (for skills using top-level assertions array)
  // ---------------------------------------------------------------------------

  if (evalSuite.assertions && evalSuite.assertions.length > 0 && !evalSuite.test_cases) {
    // Detect schema: text-match (type=pattern/contains/excludes) vs behavioral (input+expected)
    const isBehavioralSchema = evalSuite.assertions.some((a) => a.input && a.expected);

    if (isBehavioralSchema) {
      describe("Flat behavioral assertions validation", () => {
        for (const assertion of evalSuite.assertions) {
          it(`${assertion.id || assertion.input?.slice(0, 50)} is well-formed`, () => {
            assert.ok(assertion.id, "assertion must have an id");
            assert.ok(assertion.input || assertion.prompt, "must have input or prompt");
            const hasExpectation = assertion.expected || assertion.expected_contains ||
              assertion.expected_not_contains || assertion.expected_behavior;
            assert.ok(hasExpectation, "must have an expected, expected_contains, expected_not_contains, or expected_behavior field");
          });
        }

        it("assertion IDs are unique", () => {
          const ids = evalSuite.assertions.map((a) => a.id).filter(Boolean);
          const unique = new Set(ids);
          assert.equal(ids.length, unique.size, "all assertion IDs must be unique");
        });

        const triggers = evalSuite.assertions.filter((a) => a.type === "trigger");
        if (triggers.length > 0) {
          it("has both positive and negative triggers", () => {
            const positives = triggers.filter((t) => t.polarity === "positive").length;
            const negatives = triggers.filter((t) => t.polarity === "negative").length;
            assert.ok(positives > 0, "should have at least one positive trigger");
            assert.ok(negatives > 0, "should have at least one negative trigger");
          });
        }
      });
    } else {
      describe("Flat text-match assertions validation", () => {
        const validTypes = ["pattern", "excludes", "contains", "format", "response_excludes", "response_contains", "response_pattern"];

        for (const assertion of evalSuite.assertions) {
          it(`assertion: ${assertion.description || assertion.value?.slice(0, 50)}`, () => {
            assert.ok(
              validTypes.includes(assertion.type),
              `assertion type "${assertion.type}" must be one of: ${validTypes.join(", ")}`
            );
          });
        }
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Structural integrity
  // ---------------------------------------------------------------------------

  describe("Structural integrity", () => {
    it("has a version field", () => {
      assert.ok(evalSuite.version, "eval-suite must have a version");
    });

    it("has a skill name field", () => {
      const name = evalSuite.skill_name || evalSuite.skill;
      assert.ok(name, "eval-suite must have skill_name or skill field");
    });

    it("has at least one test section", () => {
      const hasTriggers = evalSuite.triggers && evalSuite.triggers.length > 0;
      const hasTestCases = evalSuite.test_cases && evalSuite.test_cases.length > 0;
      const hasEdgeCases = evalSuite.edge_cases && evalSuite.edge_cases.length > 0;
      const hasAssertions = evalSuite.assertions && evalSuite.assertions.length > 0;
      assert.ok(
        hasTriggers || hasTestCases || hasEdgeCases || hasAssertions,
        "eval-suite must have at least one of: triggers, test_cases, edge_cases, assertions"
      );
    });
  });
}
