# Decisions

Each entry records one decision: the context, what was decided, the alternatives considered and the consequences. Entries are dated. Network addresses, device names and key material are not recorded here.

## 1. Repository layout for the second slice (2026-11-14)

**Context.** Version 1.0 is closed as a development slice and is tagged. The second slice changes the project substantially: the model moves to a cloud instance, three more users are planned, and phone access is added.

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

**Context.** The operator, and later three invited users, work with Hermes output (for example network captures and reports) that contains addresses and other identifying data. Masked output would be useless for analysis.

**Decision.** Data is not masked in use: the operator and the invited users receive Hermes output with real data, and data may be sent unmasked to the cloud model. Masking applies only to material chosen for publication on GitHub, case by case, before it is published. It is not a standing transformation of the data, and nothing produced by running the tools is committed by default.

**Alternatives considered.** Masking all data before it reaches the model or the user. Rejected because it makes the analysis unusable.

**Consequences.** Transport is protected by the tunnel, but the instance necessarily processes the text unencrypted. Masking before publication is a manual step, and a leak into a commit stays in the history, so the staged changes are checked for IP and MAC patterns before each push. Not assessed: whether the instance logs request contents, and who can access the instance once other users are added. Both points are to be revisited in the GRC phase.

## 6. Configurable Ollama address (2026-11-15)

**Context.** The Ollama address was hardcoded as localhost in two requests, so Hermes could not use the cloud model without freeing the local port.

**Decision.** An optional field `ollama_url` in the local configuration file, which Git ignores, with `http://localhost:11434` as the default in code. The example configuration documents the field.

**Alternatives considered.** An environment variable. Rejected because the project already keeps local settings in ignored configuration files.

**Consequences.** Behaviour is unchanged when the field is absent. The cloud address lives only in the local file and is never committed. A request through the tunnel completed end to end. Request timeouts are unchanged and have not been measured against the cloud instance.

## 7. GRC becomes the last phase (2026-11-14)

**Context.** The GRC phase was originally planned as the second phase, when only the first existed, so the project at v1.0 was the only possible scope. The second slice then adds a cloud instance, a tunnel, further users and a new access route from a phone.

**Decision.** GRC moves to the last phase, so that it covers the whole project at v2.0.

**Alternatives considered.** None recorded. The scope followed from the order of the phases.

**Consequences.** The ISMS scope and asset inventory already drafted for v1.0 are kept as the "before" snapshot and will be extended to the new assets when the GRC phase starts.
