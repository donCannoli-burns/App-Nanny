# Repair 029 — Typed metadata authority policy (candidate)

**Owner decision:** Policy B approved for a separately reviewed candidate on 2026-11-04.  
**Baseline:** Repair 028 commit `daa4179f086645add845a55de8f96ce5b4928d5e`.  
**Source:** `studio/context_tree_studio_authority_repaired_029.html`.  
**Status:** LOCAL_CANDIDATE_UNVERIFIED / INDEPENDENT_REAUDIT_REQUIRED / PHASE1_BLOCKED.  
**Do not merge, release, authorize Go Phase 1, or rewrite frozen PR #10.**

## Problem and evidence

The exact Repair 028 Chromium P1-01 v2 matrix found seven extension/advisory modifications accepted by Verify and Restore as `SEMANTICS_VALID`, but all seven incoming values disappeared or were canonicalized when Restore was followed by a Full Project re-export. The eight controls (clean + seven normative/structural negatives) behaved as expected. The original v2 output used an in-memory mocked `localStorage` browser context, so does not establish native persistence or crash durability.

A successfully self-hashed ZIP proves byte consistency with its own manifest, **not authenticated actor identity**.

## Versioned contract: app-nanny/metadata-policy-b/v1

The Repair 029 candidate uses **closed, path-specific metadata fields**:

| JSON object | Known normative fields | Explicitly permitted untrusted extension |
| --- | --- | --- |
| `manifest.json` | format, version, timestamp, projectId, planningRevision, keywords, sha256Scope, files, exportLedger, notes | `x_reviewer_extension` object with *only* string `advisory` (max 256) and nonnegative integer `revision` |
| `manifest.json.files[*]` | name, bytes, sha256 | `x_extra_hint` string (max 256) |
| `tree_*.json` | export, data | None |
| `tree_*.json.export` | format, kind, version, timestamp, keywords, sha256 | `x_advisory` string (max 256) |
| `tree_*.json.export.sha256` | algorithm, scope, value | None |
| `planning_snapshot.json` | format, projectId, version, timestamp, revision, contentHash, data | None |
| `planning_ledger.json` | format, version, timestamp, revision, sha256, data | None |
| `resource_registry.json` | format, projectId, resources, keywords, priorityPolicy | `x_audit_hint` string (max 256) |
| `templates.json` | format, templates | None |
| `project_state.json.authority` | format, status, source, actor, reason, conflictFields, canonicalProjectSha256, importedProjectSha256, resolvedAt | None |

Advisory strings reject ASCII control characters. The same wrapper/hash-field policy applies to standalone verified tree JSON, planning snapshot and planning ledger files; supported standalone tree metadata uses the same typed `x_advisory` field and visible warning. Direct restored `project_state.json` authority records reject extra authority keys. Any other unknown key **is a semantic conflict** with path-specific reason `METADATA_UNKNOWN_FIELD`. Malformed explicitly allowed values are rejected with `METADATA_EXTENSION_INVALID`. This version has **no wildcard** `x_*` extension policy. Known semantic checks remain additional requirements; fields that are present can still fail for inconsistent values.

**Generated note decision:** `manifest.json.notes` is exact producer metadata, not free-form trusted testimony. An altered note, including a forged actor claim, is rejected as `NONCANONICAL_GENERATED_NOTE`. This is a deliberate strict choice, not a promise to migrate unknown legacy notes.

## Visible loss warning

Every explicitly permitted extension is *untrusted*, has **no execution or authentication authority**, and is intentionally not carried into new generated ZIPs. Verify and Restore must both display:

`WARNING: UNTRUSTED_EXTENSION_DROPPED_ON_REEXPORT:<JSON path>`

Warnings must also remain visible when Restore requires an unresolved human authority decision, and after its eventual Accept. The warning does not count as metadata-authority proof. Unknown authority-like fields (for example `actorAttestation`) are never silently stripped and accepted.

## Acceptance and rollback

- New 16-case ZIP candidate suite plus 7-case standalone JSON and Restore-origin authority-modal suite must pass through actual Chromium Verify, Restore and re-export, with positive allowed-extension warning checks, unchanged field-specific negative controls, and no JS exceptions.
- Existing Repair 020–028 regressions must run **on the Repair 029 source**.
- Independent byte-exact adversarial reproduction must confirm the exact source, warning persistence through Restore-origin dialogs, malformed/ambiguous input handling, and full-archive re-export.
- A separate specialist reviewer must decide whether the typed allowlist should be extended, restricted, or changed before merge.
- Repair 028 source and PR #10 stay unchanged; the candidate is isolated and reversible by abandoning its draft branch.

This candidate does **not** resolve native file:// persistence, crash durability, migration, external actor identity authentication, or external specialist signoff. `phase1_authorized=false`.
