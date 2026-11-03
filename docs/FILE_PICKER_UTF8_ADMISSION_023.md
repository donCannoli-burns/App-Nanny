# Repair 023 — file-picker UTF-8 admission

**Finding:** R022-I01 · Medium · Confirmed by independent Repair 022 audit.

**Status:** `LOCAL_REPAIR_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`

This is a focused amendment based on frozen Repair 022 commit `a98d88771a0ffe0cb5bb14ee009b33c349711994`.

## Defect and fix

The original scaffold file-picker event used `file.text()`. That browser API performs replacement decoding: malformed UTF-8 may become Unicode U+FFFD before the strict Generate parser sees the content. Consequently, the Studio could accept a silently modified project, then verify its own export even though the original uploaded file bytes were invalid.

The Repair 023 event handler reads original uploaded **bytes** using `file.arrayBuffer()`, then calls:

```js
new TextDecoder('utf-8', {fatal:true}).decode(bytes)
```

Only successful decoding populates the editable `jsonInput` textarea. A decoding failure shows an explicit `Scaffold file rejected: Invalid UTF-8 ...` error. The prior editable text, active project, tree and release state are not changed by that rejection; the file input resets so the same file can be retried after correction.

The unchanged Repair 022 `strictJsonParse(utf8(raw), 'editable scaffold JSON')` still validates the user's editable JSON when Generate is pressed. Existing ZIP Verify/Restore admission code remains unchanged.

**BOM boundary:** A valid leading UTF-8 BOM remains accepted and stripped by the browser decoder, consistent with previous behavior. This repair does not introduce a new BOM policy or guarantee byte-for-byte ZIP re-export of every valid JSON file; it prevents *lossy decoding of invalid UTF-8* at file selection.

## Reproducible tests

The SHA-pinned Repair 022 source is used as a negative baseline. The executable `tests/test_file_picker_utf8_023.py` reproduces an invalid `0xFF` byte being accepted, converted to `�`, and exported in the old app.

Repair 023's **15/15 local browser checks** pass, covering:

- 9 invalid UTF-8 sequences, including unexpected continuation, truncation, overlong encodings, surrogate UTF-8 and out-of-range code points.
- Rejection before textarea mutation, project replacement or release changes; old project still exports as `SEMANTICS_VALID`.
- 4 clean controls: ASCII, Unicode (accented and emoji), literal valid U+FFFD, and legacy-compatible BOM.
- No browser JavaScript exceptions in the new suite.

The prior Repair 022 suite hit a local execution limit, so that attempt is **not credited as a completed pass**. The GitHub Actions workflow runs the unchanged Repairs 020, 021 and 022 test scripts against the Repair 023 HTML, then runs the 023 file-byte suite.

All test storage is browser-session mock localStorage. No native `file://` persistence or crash durability is demonstrated.

## Outstanding authorization boundaries

- Independent byte-exact re-audit of Repair 023 is required.
- **R020-I02** (descriptive/unknown extension metadata policy) remains unresolved.
- Historical actor authentication, legacy migration, external specialist signoff, native `file://` durability and crash recovery remain unverified.
- **Go Phase 1 authorization is `false`; no Go lifecycle was started.**

Repair 023 source SHA-256: `f4bde89f4efd585fc406f020d659b2eda5990b41ed1e62e9837aa08f3ffd2b73`. Parent Repair 022 HTML remains frozen and unmodified.
