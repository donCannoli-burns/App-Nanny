# Repair 021 — strict JSON admission

**Scope:** R020-I01 · High · duplicate JSON object member names

**Candidate status:** `LOCAL_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`

This is a small, Git-native repair on top of the frozen Repair 020 commit (`e27cc6b639d000ab9bd1864ac2d91f165823ad36`). The earlier Repair 020 source, tests, and workflow are preserved without edits.

## Vulnerability

Standard JavaScript `JSON.parse` silently keeps the last value of a repeated object key. Other parsers can keep the first value or reject duplicates. A hash-valid Full Project ZIP can therefore convey incompatible project identities despite verifying `SEMANTICS_VALID` in Repair 020.

## Admission rule

`strictJsonParse(bytes, sourceName)` decodes original UTF-8 bytes with `fatal: true`, scans JSON object structure, and rejects a repeated key **within the same object scope** before calling ordinary `JSON.parse`. Every nested object, including objects inside arrays, has its own set of keys. JSON key-token decoding uses `JSON.parse` so literal and Unicode-escaped spellings—and surrogate-pair equivalents—compare as the same JavaScript string. Distinct keys in separate objects remain valid. The scanner limits nesting to 512 levels; malformed or overly deep JSON fails closed.

Admission is applied to **every `.json` member** while parsing the ZIP, before the application can silently discard duplicate evidence, including the manifest, saved state, tree exports, planning exports, resources, templates, and raw scaffold. The same rule applies to standalone JSON Verify and Restore.

On duplicate keys, the verifier displays `SEMANTICS_CONFLICT` inside its **`VERIFICATION FAILED`** result. An invalid document does not receive `BYTES_VERIFIED`, because rejection occurs during raw-byte admission. Restore aborts without changing the current project.

## Tested controls

- Original Repair 020: a hash-valid duplicate-`projectId` ZIP was accepted with `BYTES_VERIFIED · SEMANTICS_VALID` and successfully restored.
- Repair 021: 15 hash-valid duplicate-key ZIPs are rejected by Verify and Restore, including nested keys, reversed first/last ordering, identical-name duplicates, Unicode escapes and surrogate-pair equivalents.
- One clean ZIP verifies, restores, re-exports, verifies again, and restores in a fresh session.
- Five standalone JSON tests cover clean wrappers, duplicated snapshot revision, duplicated hash algorithm, and project-state restore rejection.
- All **21/21** new local cases pass without browser JavaScript errors.

`tests/test_duplicate_json_021.py` generates the seed from the exact pinned Repair 020 HTML at runtime and writes only temporary mutation ZIPs; no binary fixtures are checked into Git. The existing Repair 020 test is also executed unchanged in CI, using its `--html` argument to point to Repair 021.

## Separate low-priority finding left open

**R020-I02 is not fixed here.** `manifest.notes` is currently descriptive/advisory; arbitrary extension fields such as `human_authorized` or `signature_verified` do not grant authority, but their acceptance and removal on re-export still require a clearly defined extension-policy contract. This repair does not promote those fields to authenticated claims or silently assert that the gap is resolved.

## Limits and authorization

This change does not establish native `file://` persistence, browser crash durability, historical actor authentication, migration, or external specialist approval. All Chromium checks use isolated mocked browser storage. SHA-256 and CI checks are not authorship verification. **Go Phase 1 remains unauthorized (`false`).** An independent byte-exact audit of this commit is required.
