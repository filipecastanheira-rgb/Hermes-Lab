# Security

This document describes the security-relevant design decisions in Hermes-Lab,
and what is (and isn't) covered by automated tests.

## Authentication

The PURPLE API is protected by a bearer token stored in
`config/purple_auth.json`.

- **Token generation:** the initial token is generated with
  `secrets.token_hex(32)` (a cryptographically random 256-bit value), created
  fresh on first run. It is never derived from a fixed or guessable string.
- **Token comparison:** token validation uses `hmac.compare_digest()`, a
  constant-time comparison, to avoid timing-based side-channel attacks.
- **Network exposure:** the API binds to `127.0.0.1` only. It is not reachable
  from other devices on the local network or from the internet, even if the
  host machine has other services exposed.

An earlier version of this project generated the initial token as
`sha256("hermes-default")` — a fixed, publicly computable value for anyone
reading the source code. This was found and fixed before the project's public
release, and is the reason the two points above exist.

## The lab_boundary invariant

Every tool call that targets an IP or network — whether triggered manually by
the user or proposed by the AI decision layer — is validated against
`hermes/core/lab_boundary.py`'s `alvo_permitido()` before execution. This is
the single point of authority for "is this target allowed to be scanned",
backed by an explicit allowlist (`config/lab_allowed.json`, defaulting to
loopback-only if the file is missing or unreadable). No tool, current or
future, is meant to bypass this check.

## AI tool-calling constraints

When the AI decision layer (`IntelligenceService.decide_action()`) is used, it
is allowed to decide **whether** and **which** pre-approved tool to call
(from a fixed allowlist in `tool_dispatcher.py`), but it never decides
**where**:

- Any target the AI proposes in a tool call is discarded and replaced with
  `mission_target` (a value the user or the calling code controls, defaulting
  to `127.0.0.1`) before the call reaches the dispatcher.
- Tools that don't operate on an IP at all (e.g. TShark, which captures on a
  network interface) have their target hard-fixed and never take the AI's
  suggestion, regardless of what it proposes.

This was validated with adversarial testing (e.g. explicitly prompting the
model to scan an external IP) — the override held in every case.

## Automated tests

`tests/` covers the security-critical invariants above with unit tests, not
just manual verification:

- `test_lab_boundary.py` — allowed/disallowed targets, malformed input
  (fails closed), mixed IPv4/IPv6 comparisons (no crash), missing or corrupted
  config (falls back to the safe default).
- `test_tool_dispatcher.py` — tool names outside the allowlist are rejected,
  targets outside `lab_boundary` are rejected, and the AI can never override a
  tool's fixed target (e.g. TShark's interface).
- `test_intelligence_service.py` — `mission_target` always overrides any
  target the AI proposes, both for the default value and for an explicit
  user-supplied one.

These tests run with `pytest tests/` and are intended to keep failing loudly
if any of these invariants ever regresses, rather than relying on the author
remembering to check manually.

## Known limitations (accepted, not fixed)

- TShark, Suricata, and Zeek cannot target a remote IP — they operate on a
  local network interface or local log files respectively. Only Nmap and
  OpenVAS can be pointed at a network target. Extending this is possible
  future work, not currently planned.
- The local LLM (llama3.2:3b, CPU-only) can reliably make a single tool-call
  decision, but cannot chain multiple tool calls in response to a previous
  result. Because of this, the project intentionally runs in a
  non-autonomous mode: the user picks the tool and target, Hermes executes
  and reports. See the main README for the reasoning behind this decision.
