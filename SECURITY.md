# Security

This document describes the security-relevant design decisions in Hermes-Lab,
and what is (and isn't) covered by automated tests.

## Authentication

The PURPLE API is protected by a random token stored in
`config/purple_auth.json` and sent **only** in the `X-Hermes-Token` request
header.

- **Token generation:** the initial token is generated with
  `secrets.token_hex(32)` (a cryptographically random 256-bit value), created
  fresh on first run. It is never derived from a fixed or guessable string.
- **Token comparison:** token validation uses `hmac.compare_digest()`, a
  constant-time comparison, to avoid timing-based side-channel attacks.
- **No token in the URL.** `/dashboard/view` is served as a shell: HTML and
  JavaScript only, no data and no token embedded. The operator pastes the token
  the CLI prints, and the page keeps it in `sessionStorage` for the lifetime of
  the tab. Any request carrying `?token=` is refused with `403` and recorded as
  a `MEDIO` alert in the PURPLE alert log, so an old client cannot silently
  fall back to the query-string path. An earlier version of this file described
  the URL token as "a known, accepted limitation" — it is now removed, because
  a token in the URL survives the request: it lands in the browser history, in
  the `Referer` sent to third parties, and in the server access logs.
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

`IntelligenceService.decide_action()` is **not connected to any execution path**
in the current manual mode (see the README and
`hermes/_archive/autonomia_experimental/`). It is kept, together with its tests,
so the constraints below still hold if autonomy is ever reintroduced. If used,
it is allowed to decide **whether** and **which** pre-approved tool to call
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
- `test_purple_auth.py` — the token is accepted in the `X-Hermes-Token` header
  and refused everywhere else: no token, wrong token, and a valid token in the
  query string all return `403`; the URL token is never copied into the API
  log, and a request with `?token=` is recorded as an alert.

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
