# Live Jev response fixtures

`jev_live_responses.json` holds **verbatim responses from the live TypeSafe Jev
API**, captured 2026-09-21 against `https://api.typesafe.ai/v1/systemone` with
model `jev-1.13.0`. They are not hand-authored.

## Why they exist

Every other Jev test injects a transport whose reply was written to satisfy the
validator being tested. That proves the validator matches its author's belief
about the API, not the API. These fixtures are the only thing in the offline
suite that can fail if TypeSafe changes the response contract.

`test_live_contract.py` replays them through the shipped `JevProvider`.

## What the capture established

- Requesting `jev-1.13.0` returns `model: "jev-1.13.0"`.
- Requesting the alias `jev-latest` **also** returns `model: "jev-1.13.0"` — the
  API echoes the resolved version, never the alias. Because the provider asserts
  `response["model"] == self.model`, a provider allowed to send `jev-latest`
  would fail every live call. The constructor's version regex prevents that.
- `usage` carries integer `input_tokens` / `output_tokens`, so spend is knowable.
- Noul answers are `{"type": "noul", "noul": <float 0..1>}`.

## Re-capturing

Needs a real `TYPESAFE_API_KEY` and makes three billed requests. Use synthetic
content only — whatever goes in the request is committed to the repository.

```sh
export TYPESAFE_API_KEY=...        # never commit this
python tests/context_routing/fixtures/capture.py 2026-09-21   # the UTC capture date
```

The date argument is required; `capture.py` refuses to guess it, so the
`captured_utc` field always reflects a date a human chose.

If a re-capture changes the response *shape* (not just the probabilities), that is
a contract change: update `jev_provider.py` in the same commit and say so in the
message. Probabilities drifting between captures is expected and is not a failure —
no test asserts an exact score, only ordering and shape.
