# App-Nanny

**Pre-alpha source checkpoint — not a production release.**

App-Nanny is intended to become a **Detachable Development Layer (DDL)**: a globally callable, pure-Go development tool that can inspect a repository without becoming a runtime dependency or modifying that repository without explicit, scoped authorization.

The code currently preserved here is **Context Tree Studio**, a single-file **HTML5/JavaScript experimental planning and export workbench**. It is not the proposed Go application and does not establish that the DDL architecture is implemented.

## Current source

- [Context Tree Studio — Repair 019](studio/context_tree_studio_authority_repaired_019.html)
- [Independent audit status](docs/AUDIT_STATUS.md)
- [Target architecture and invariants](docs/ARCHITECTURE_INTENT.md)
- [Machine-readable checkpoint](audit/checkpoint-019.json)
- [Source SHA-256](SOURCE_SHA256SUMS.txt)

For local inspection, download the Studio HTML file and open it in a browser. **Do not rely on it for authoritative or sole-copy backups.** Native `file://` persistence, crash durability, and untrusted-input safety have not been established. Review its known failures before importing data.

## Governing status

`CORE_INVARIANT_FAILURE` — `INDEPENDENT_REAUDIT_FAILED__PHASE1_BLOCKED`

Repair 019 fixed eight earlier metadata inconsistencies in its tested scope; the independent byte-exact re-audit confirmed further checksum-label and resource-registry metadata contradictions. There is **no Phase 1 Go authorization**, release approval, or production-readiness claim.

## Scope and history

This checkpoint deliberately commits the **exact 170 KB HTML source and a compact audit record**, not recursive archives of all preceding repairs. The original Repair 019 ZIP and the independent evidence ZIP have SHA-256 identities recorded in [audit status](docs/AUDIT_STATUS.md), but their 80+ MB binary contents are **not in this Git tree**.

The existing [BSD 3-Clause license](LICENSE) remains unchanged. This repository is **App-Nanny**, not the separate Gen Type-go project.
