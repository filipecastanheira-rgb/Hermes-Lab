# Security

This document describes the security-relevant design decisions in Hermes-Lab,
and what is (and isn't) covered by automated tests.

## Authentication

The PURPLE API accepts two credentials: an HttpOnly session cookie, minted for the
local operator at startup, or a token sent in the `X-Hermes-Token` request header
(other machines, scripts). `config/purple_auth.json` stores **only their SHA-256 hashes**
(format 2): the clear token exists at the moment it is created and is shown
once. A file read by mistake — a backup, a copy shared for debugging, a synced
folder — no longer grants access.

- **One token per person or device.** Tokens carry a name and an id, so access
  can be given to someone else and revoked individually, and every log entry
  records which token (`utilizador`) made the call.
- **Token generation:** `secrets.token_hex(32)` — a cryptographically random
  256-bit value, always generated server-side. There is no caller-supplied
  "base" and no derivation from a fixed string.
- **Token comparison:** `hmac.compare_digest()` over every stored hash, so the
  response time does not reveal which token failed (or that any did).
- **Recovery:** if a token is lost, delete `config/purple_auth.json`; the next
  start generates a new one and prints it once. `POST /token/regenerar` revokes
  the presented token and issues a replacement with the same name.
- **Migration:** a format-1 file (clear token) is converted automatically on
  first load; the existing token keeps working, now stored as a hash.

  An earlier version of this file claimed that the publicly computable
  `sha256("hermes-default")` token had been found and fixed before release. The
  fix had been applied to **initial generation only**: the rotation route still
  defaulted to that base, so `POST /token/regenerar` with no body set the token
  to a value printed in this document's source. That path is now gone, and the
  rotation always generates a fresh random value.

- **No token in the URL.** `/dashboard/view` is served as a shell: HTML and
  JavaScript only, no data and no token embedded. Locally the page signs in with a single-use nonce (see *Local
  sign-in*); remote clients send `X-Hermes-Token`, and the page keeps a pasted
  token in `sessionStorage` for the lifetime of the tab. Any request carrying `?token=` is refused with `403` and recorded as
  a `MEDIO` alert in the PURPLE alert log, so an old client cannot silently
  fall back to the query-string path. An earlier version of this file described
  the URL token as "a known, accepted limitation" — it is now removed, because
  a token in the URL survives the request: it lands in the browser history, in
  the `Referer` sent to third parties, and in the server access logs.
- **Network exposure:** the API binds to `127.0.0.1` only, and that is enforced
  in code rather than configuration: `endereco_bind()` refuses anything that is
  not a literal loopback address, so one careless edit — or a tool rewriting
  the file — raises inside the API thread before the server binds, instead of exposing the
  service on a machine that has internet access. The process stays up, the health
  check reports `api_thread_viva: false`, and recovery is manual (or the watchdog,
  if it acts). It fails loudly, but it does not stop the program - stated here
  rather than implied. It is not reachable from other devices on the local
  network or from the internet, even if the host machine has other services
  exposed.
- **Rate limiting:** requests are limited per token and per client address. On a
  loopback-only service every client shares the address `127.0.0.1`, so the
  address limit works as a **global** bucket. That is deliberate: it protects
  against a runaway local client (a bug that fires requests in a loop), while
  the per-token limit is what tells clients apart.
- **Host header validation:** only `127.0.0.1`, `localhost` and `::1` are
  accepted, with or without a port. Anything else is refused with `400` before
  authentication runs. This closes the DNS-rebinding path, where a domain
  controlled by an attacker resolves to `127.0.0.1` and the victim's browser
  then sends that domain in the `Host` header, making the local API reachable
  from a page on the internet.

### Local sign-in (no token to keep)

Opening the dashboard locally used to require a token, which then had to live
somewhere — a file, a password manager, or nowhere and the operator got locked
out. None of that is a security control; it is friction.

- The CLI generates a **single-use nonce** (60 s TTL, in memory only) and opens
  `/dashboard/view#n=<nonce>`.
- A URL **fragment** is never sent to the server, never appears in the
  `Referer`, and never reaches access logs. The page trades the nonce for an
  `HttpOnly; SameSite=Strict` session cookie and strips it from the URL with
  `history.replaceState`.
- The nonce is **consumed by the first attempt even if that attempt fails**, so
  it cannot be guessed by repetition. It is also refused from non-loopback
  addresses.
- Sessions live in the server's memory: restarting Hermes invalidates them, and
  the CLI opens a fresh nonce on every start. `POST /auth/logout` revokes one.
- Tokens (tema 5) are unchanged and remain the way in for other
  machines, and for the friends who will be given access.

The private window is still how Hermes opens the dashboard, and for a
functional reason: dashboard requests to the local API fail in a normal window
on the development machine (the tool buttons answer `NetworkError`), and
extensions are disabled in a private window. It is no longer a token measure -
the token does not travel in the URL, and the session cookie works in either
kind of window.

Residual exposure, stated plainly: a local process running as the same user
could race the browser for the nonce during its 60 s window, and could read the
browser profile anyway. The trust boundary here is the operating-system user,
not the file.

### Residual exposure: the development server's own log

Flask's development server writes the request line to stderr, query string
included. A request to `/dashboard/view?token=...` is refused with `403` and the
API log records only `token_ref`, but the raw URL still lands in the process
stderr, where it is neither rotated nor cleaned by Hermes. That is the residual
exposure of the URL-token path: the API no longer stores it, the process output
still does.

## Tokens in logs and persisted state

The API log (`logs/purple_api.log`) and the rate-limit state
(`config/purple_ratelimit.json`) are plaintext files on disk. Neither holds a
token: every entry carries `token_ref`, a truncated SHA-256 of the token derived from a
separate context string (so it is not a prefix of the stored hash). That
is enough to correlate requests made with the same token (and to spot repeated
abuse) but not enough to reconstruct it.

This was not always true. Earlier versions wrote the token on every call, the
full token on authentication failures, the **newly issued** token on rotation,
and used the token itself as a JSON key in the rate-limit file. **If you ran
Hermes before this change: rotate the token** (`POST /token/regenerar`) and
treat the old log files as secret material — delete them, or move them out of
`logs/`.

Authentication also happens before anything is logged as a call, so a rejected
request produces only an `erro_autenticacao`/`acesso_negado` entry and the body
of an unauthenticated request never reaches the log.

An earlier version of this project generated the initial token as
`sha256("hermes-default")` — a fixed, publicly computable value for anyone
reading the source code. This was found and fixed before the project's public
release, and is the reason the two points above exist.

### No HTML is built from data

The dashboard renders alert descriptions, signature names and interface names
that originate outside Hermes (Suricata rules, log paths, remote banners). An
earlier version interpolated them into `innerHTML`: a crafted signature was
stored XSS inside an authenticated page. The page now builds every node with
`textContent`/`createElement`, so the data is data.

This matters more with a cookie session than it did with a header token: an
injected script cannot read an `HttpOnly` cookie, but it can issue requests in
the page's context while the tab is open.

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
- `test_purple_api_logger.py` — no code path writes a token in clear: calls,
  authentication failures, token rotation and the rate-limit state file all
  store only `token_ref`.
- `test_purple_api_host.py` — local names are accepted, foreign and
  suffix-spoofed names (`localhost.evil.com`, `127.0.0.1.nip.io`) are refused
  with `400`, and the refusal happens before authentication.
- `test_dashboard_page.py` — the dashboard page does not send a JSON content type
  without a body (that used to make the server answer `400` to every dashboard
  request).
- `test_purple_api_bind.py` — the API starts only on loopback and refuses to start
  any other way.
- `test_purple_auth_store.py` — tokens are stored only as a digest, with several
  tokens, one per person.
- `test_purple_bootstrap.py` — local sign-in without a token: a single-use nonce
  is exchanged for an `HttpOnly` cookie.
- `test_purple_requests.py` — the exact shapes of request the dashboard sends,
  at the Flask level.
- `test_purple_session.py` — sessions have an absolute deadline and a cap, and
  the nonce exchange is atomic.
- `test_purple_tokens.py` — the token management helpers called by the CLI.
- `test_purple_config.py` — `POST /config` rejects values the runtime cannot use
  and leaves the config file untouched.
- `test_purple_request_shapes.py` — request bodies of the wrong shape are refused
  with `400` instead of failing with a `500`.
- `test_lab_boundary_config.py` — the allowlist loader survives malformed files,
  ignores entries that are not strings, and never changes the built-in default.
- `test_target_size_limit.py` — a target inside the lab but over 256 addresses is
  not scanned by nmap or OpenVAS.
- `test_target_size_visible_refusal.py` — `/run_tool` and the AI dispatcher refuse
  an oversized target visibly, not as a scan with no findings.

These tests run with `pytest tests/` (install `requirements-dev.txt` first) and are intended to keep failing loudly
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
- Dependencies are pinned to the versions audited on 2026-11-23 (`pip-audit`:
  no known vulnerabilities found) and will not be updated: this is a lab
  project and the repository is not maintained. A later audit may report
  vulnerabilities in these versions. To repeat the audit:
  `pip install pip-audit && pip-audit -r requirements.txt`.
