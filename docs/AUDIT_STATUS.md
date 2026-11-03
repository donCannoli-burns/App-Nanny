# Repair 019 — Byte-exact independent audit

**Date:** 2026-11-02  
**Disposition:** `CORE_INVARIANT_FAILURE`  
**Gate:** `INDEPENDENT_REAUDIT_FAILED__PHASE1_BLOCKED`  
**Phase 1 authorized:** `false`

## Exact verified artifacts

| Artifact | SHA-256 |
|---|---|
| Studio HTML (committed under `studio/`) | `8b41c0096ebbbc4f920b1f059ea908d9b0aded5d6c6f01cdedeec77e77c14674` |
| Original Repair 019 ZIP (**not committed**) | `e26b3d675fb075fe269814a7113c7f2b15407c7172aa8bc6c70c1b8e069a11a0` |
| Independent byte-exact evidence ZIP (**not committed**) | `5012e812135a9109e2a62ba80db228729f0b60801678f43c54439ae68be209b6` |

The independent evidence package had 58 ZIP members and 57 indexed payload hashes. Its verification confirmed the source ZIP and HTML bytes and the portable reproducer passed **17/17**.

## Independently confirmed findings

- **R019-I01 (HIGH):** The verifier accepts contradictory checksum algorithm/scope labels (for example, claiming MD5 while the actual archive digest is SHA-256).
- **R019-I02 (HIGH):** Resource-registry format and priority policy claims are not consistently semantically checked.
- **R019-I03 (LOW):** Contradictory human-readable README claims are accepted; README may be advisory, but must be explicitly classified.

The earlier eight Repair 018 metadata contradictions were **rejected** by Repair 019's shared verifier in the tested scope. Repair 019's targeted suite passed **45/45**; fifteen historical suites completed and passed, while one older suite timed out and is **not** counted as passing. The new eight hash-valid metadata mutations were still labeled `SEMANTICS_VALID`. Successful restore/re-export of selected mutated archives regenerated metadata rather than preserving the supplied contradictions.

These results establish **false semantic validation of metadata**, not SHA-256 collision, unauthorized code execution, or corruption of canonical project data.

## Unresolved gates

Native `file://` persistence, browser crash durability, authenticated historical actor identity, legacy-data migration and external specialist sign-off have not been established. No Go lifecycle was started by these audit/repair runs, and they did not mutate a production repository.

**GitHub checkpoint policy:** preserving this source is not the same as merging an approved implementation or granting Phase 1. New repairs need their own independent, byte-exact review.

This file is an **authored summary of the original independent evidence**, not a replacement for the original machine-readable return or a cryptographically authenticated signature.
