---
id: TASK-92
title: 'Spike: subprocess network sandboxing for backend extensions'
status: To Do
assignee: []
created_date: '2026-04-07 03:43'
labels:
  - spike
  - security
  - 'estimate: lp'
milestone: m-15
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Investigate making `network.fetch` a true enforcement gate rather than an API-scoping declaration.

Currently `network.fetch` only controls access to `KampGround.fetch()` — extensions can still call `requests`, `musicbrainzngs`, `urllib`, etc. directly and reach the network without declaring anything. `library.write` is the only real security gate today.

**Goal:** determine whether subprocess-level network restriction is feasible and what it would cost.

**Approaches to investigate:**

- **macOS:** `sandbox-exec` with a custom profile that denies outbound connections; apply it to the spawn-context worker process via a wrapper script or `ctypes` call to `sandbox_init()`.
- **Linux:** `seccomp-bpf` filter blocking `connect(2)` / `sendto(2)` syscalls; apply via `prctl` in the worker's initializer before the extension module is imported.
- **Cross-platform fallback:** Replace `socket.socket` at the top of `_extension_worker` before the extension class is instantiated (runtime stub, not just import-time as the probe does now). Weaker than a real sandbox but stops library-level calls without OS involvement.

**Deliverable:** a written recommendation (spike document or task notes) covering:
1. Which approach works on which platform
2. Interaction with `spawn` context (child starts clean, so hooks must be applied early in `_extension_worker`)
3. Whether the runtime socket-stub fallback is a reasonable interim measure
4. Estimated effort to productionise the chosen approach
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Spike document written covering macOS sandbox-exec, Linux seccomp-bpf, and runtime socket-stub approaches
- [ ] #2 Recommendation identifies which approach to implement and on which platforms
- [ ] #3 Effort estimate provided for the productionisation task that follows this spike
<!-- AC:END -->
