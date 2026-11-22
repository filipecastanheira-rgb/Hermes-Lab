# Decisions

Each entry records one decision: the context, what was decided, the alternatives considered and the consequences. Entries are dated. Network addresses, device names and key material are not recorded here.

## 1. Repository layout for the second slice (2026-11-14)

**Context.** Version 1.0 is closed as a development slice and is tagged. The second slice changes the project substantially: the model moves to a cloud instance and two more users are planned.

**Decision.** The second slice stays in this repository, developed in a branch named `v2` and closed with the tag `v2.0`. The tag `v1.0` is left untouched.

**Alternatives considered.** Cloning the repository under a new name. Rejected because it leaves two near-identical repositories, fixes would have to be duplicated, and the comparison between versions is available in a single view with the GitHub compare page between `v1.0` and `v2`.

**Consequences.** Anyone browsing the repository sees one project growing in the same folders, not two. The `master` branch keeps describing v1.0 until `v2` is merged at the v2.0 milestone, so its README is to carry a short roadmap in the meantime.

## 2. Same model in the cloud as locally (2026-11-11)

**Context.** The cloud phase exists to learn cloud deployment and to document it in a public repository. Model quality is not the goal.

**Decision.** The cloud instance runs the same model as the local setup (llama3.2:3b), which was already known to work on the desktop.

**Alternatives considered.** A larger model. Not pursued for now, because the aim is learning and documentation, not model quality. It may be tried later as a separate experiment.

**Consequences.** Both sides can be compared directly: about 7.4 tokens/s on the 2-core Arm instance and 8.4 tokens/s on the local 6-core desktop (CPU only), for one short prompt, two runs each. The Ollama versions differ, so this is an indication and not a benchmark.

## 3. Access to the cloud instance only through a WireGuard tunnel (2026-11-12)

**Context.** The instance is on a public cloud, where an open SSH port or model port is exposed to the internet.

**Decision.** The instance is reachable only through an encrypted WireGuard tunnel. There is no public SSH and no public model port, and the host firewall accepts SSH only on the tunnel interface.

**Alternatives considered.** Public SSH was kept open only until the tunnel was proven, and was then closed. Other alternatives: not recorded.

**Consequences.** If the tunnel is down, there is no access to the instance except through the cloud provider's console, so the console login is kept working as a recovery path. The tunnel and firewall rules were verified to survive reboots.

## 4. Container hardening and start at boot (2026-11-14)

**Context.** The model server runs in a container on an internet-connected host.

**Decision.** Rootless Podman, image pinned by digest, all Linux capabilities dropped, no-new-privileges set, and the port bound to the tunnel address only. The container is started by a systemd Quadlet service at boot.

**Alternatives considered.** Not recorded.

**Consequences.** The capability settings were checked from inside the container (all capability sets empty, no-new-privileges on), and the boot start was verified with a reboot test. One reboot does not rule out a race between the service and the tunnel interface at boot, so the service keeps a restart-on-failure policy as a safety net.

## 5. Data handling for the cloud model (2026-11-14)

**Context.** The operator, and later two invited users, work with Hermes output (for example network captures and reports) that contains addresses and other identifying data. Masked output would be useless for analysis.

**Decision.** Data is not masked in use: the operator and the invited users receive Hermes output with real data, and data may be sent unmasked to the cloud model. Masking applies only to material chosen for publication on GitHub, case by case, before it is published. It is not a standing transformation of the data, and nothing produced by running the tools is committed by default.

**Alternatives considered.** Masking all data before it reaches the model or the user. Rejected because it makes the analysis unusable.

**Consequences.** Transport is protected by the tunnel, but the instance necessarily processes the text unencrypted. Masking before publication is a manual step, and a leak into a commit stays in the history, so the staged changes are checked for IP and MAC patterns before each push. Not assessed: whether the instance logs request contents, and who can access the instance once other users are added. Both points are to be revisited in the GRC phase.

## 6. Configurable Ollama address (2026-11-15)

**Context.** The Ollama address was hardcoded as localhost in two requests, so Hermes could not use the cloud model without freeing the local port.

**Decision.** An optional field `ollama_url` in the local configuration file, which Git ignores, with `http://localhost:11434` as the default in code. The example configuration documents the field.

**Alternatives considered.** An environment variable. Rejected because the project already keeps local settings in ignored configuration files.

**Consequences.** Behaviour is unchanged when the field is absent. The cloud address lives only in the local file and is never committed. A request through the tunnel completed end to end. Request timeouts are unchanged and have not been measured against the cloud instance.

## 7. GRC becomes the last phase (2026-11-14)

**Context.** The GRC phase was originally planned as the second phase, when only the first existed, so the project at v1.0 was the only possible scope. The second slice then adds a cloud instance, a tunnel and further users.

**Decision.** GRC moves to the last phase, so that it covers the whole project at v2.0.

**Alternatives considered.** None recorded. The scope followed from the order of the phases.

**Consequences.** The ISMS scope and asset inventory already drafted for v1.0 are kept as the "before" snapshot and will be extended to the new assets when the GRC phase starts.

## 8. Cloud-first AI with local fallback and an indicator (2026-11-15)

**Context.** Hermes can reach the cloud model through the tunnel (entry 6), but with the tunnel or the instance down, report generation had no other route. The operator also could not tell which model wrote a report, and the cloud model processes data outside the local machine (entry 5).

**Decision.** Hermes tries the cloud model first and falls back to the local model only when the connection to the cloud fails. The fallback exists only when `ollama_url` is set; without it, behaviour is that of v1.0. The connection timeout is 5 s, separate from the 200 s read timeout, and a read timeout or an HTTP error from the cloud does not trigger the fallback. The text generation function still returns a string; the model that answered is kept in a separate `ai_source` field ("Cloud AI" or "Local AI"), which is returned by `/run_tool` and written into the report event. The dashboard shows an indicator with the current AI state (cloud, local or none), kept in its own cache of about 30 s, and a label under the report card showing which model answered that run.

**Alternatives considered.** Putting the label in the report text. Rejected in favour of the separate field and the indicator. Other alternatives: not recorded.

**Consequences.** With the cloud down, every request pays the 5 s connection timeout before the local model is used; one test took 17.6 s, consistent with that timeout plus local generation. The tool-calling path (`gerar_com_tools()`) and `definir_provider()` are unchanged and have no fallback. Tested: cloud, local and no-AI states in Python; a connection failure, a connection cut mid-read, a read timeout and an HTTP error from the cloud (the last two without fallback, as decided), using local test servers; and the indicator and label with the cloud up and down in the browser. Verified by reading the code only: the `ai` field of `/status`, and the dashboard latency with the cloud down, where only the request that finds the 30 s state cache expired waits for the check (about 5 s; the server is threaded, so other requests are not blocked). Not tested: the "none" state and the empty label in the browser. The 200 s read timeout was measured on the cloud instance for an nmap run and with synthetic prompts; OpenVAS, Suricata and Zeek runs were not measured with real data, and the events of a run enter the prompt without a cap.

## 9. Read-only access for invited users through a proxy on the cloud instance (2026-11-19)

**Context.** Invited users should reach Hermes from outside, to test an architecture where people who are not the operator can see its output without touching the machine that runs it. The main API (`purple_api`) listens on loopback only and is protected by tokens.

**Decision.** A separate Flask app (`guest_view.py`) serves the invited users: GET only, Host header validation, a log line per request, and a bind restricted to loopback or the tunnel network. It returns only the status, two counters, the AI state and a reduced list of alerts. It is started by the runner only if `config/guest_config.json` enables it, and that file is Git-ignored. Each invited user has a WireGuard peer whose allowed addresses are limited to the instance's tunnel address. A web server on the instance listens only on that address, accepts GET and HEAD, and forwards to the guest port of the machine running Hermes. The instance does not forward packets (`ip_forward` is 0 and the FORWARD chain ends in REJECT), so no guest traffic reaches that machine. On the machine, a firewall rule on the tunnel interface accepts the guest port only from the instance's address and drops the rest; it is installed and removed with the tunnel. On the instance, SSH and the model port accept only the operator's tunnel address, and each guest peer may reach only the proxy port. Invited users see real, unmasked data, as in entry 5. Access control is the WireGuard key; the page itself has no login.

**Alternatives considered.** Forwarding guest traffic through the instance to the machine: rejected, because a mistake in the forwarding rules would open a direct path to it. Adding a guest role to the existing API: rejected, to leave that API untouched on loopback. Putting a firewall in front of the machine was considered and left for a later phase.

**Consequences.** If the instance is down, invited users cannot connect, while Hermes itself keeps working with the local fallback (entry 8); if the machine is off or Hermes is not running, the proxy returns 502. Tested with both invited users: the handshake, the dashboard loading and refreshing, a POST rejected with 403, no response from the model port, SSH to the instance refused, and no reply from the machine's tunnel address. For one guest the last test was repeated with the allowed addresses widened to the whole tunnel network and routes added to the machine and to the other guest: both pings stayed unanswered and without an ICMP error, which fits a silently dropped packet but does not show which layer dropped it (the instance does not forward packets, and the machine's WireGuard accepts only the instance's address as a source). The machine-side rule was checked with the tunnel taken down and up again, and a reboot of the instance brought back the tunnel, the proxy, the firewall rules and the model container on their own. New alerts do reach the guest's alert table, which shows the time but not the date. Not assessed: an invited user probing the ports of the instance raised no alert, because the instance firewall rejects without logging and Hermes sees only the machine's own traffic; the guest server runs on Flask's development server; invited users see real alerts, including open ports of the lab machine; the proxy logs the source address and path of each request, and retention and access to those logs have not been reviewed.
