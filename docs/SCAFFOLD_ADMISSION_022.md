# Repair 022 — strict scaffold admission

**Finding:** R021-I01 (Medium). Independent Repair 021 audit: `CORE_INVARIANT_FAILURE`, `INDEPENDENT_REAUDIT_FAILED__PHASE1_BLOCKED`.

## Scope and decision

The Generate / replace tree action previously used `JSON.parse(raw)` on editable scaffold JSON. A duplicate `project.name` or `schema` key was silently resolved by the JavaScript parser, and the UI declared `SEMANTICS_VALID`. The saved `tree_raw.json` still contained duplicate keys, so a subsequent Full Project ZIP export refused to download: the same project had been accepted and then deemed unbackuppable.

Repair 022 replaces **only this admission call** with:

```js
const doc = strictJsonParse(utf8(raw), 'editable scaffold JSON');
```

The exact Repair 021 `strictJsonParse` implementation remains unchanged. It checks per-object key uniqueness from the original UTF-8 input, decodes Unicode-escaped equivalents, and rejects invalid JSON. The existing schema and authority-resolution logic remain in place.

A rejected scaffold leaves the original editable textarea intact for correction and does **not** commit a new project, mutate the current tree, or advance the release version. Scaffolds loaded through the file picker still enter via the same textarea and Generate gate. This is a local input-consistency repair, **not** a new signed-authorship claim.

## Reproducible verification

`tests/test_scaffold_admission_022.py` checks 20 browser assertions in disposable, isolated Chromium sessions:

- Reproduces the original Repair 021 accepted-import/blocked-export failure using SHA-256-pinned original HTML.
- A valid scaffold imports, exports as Full Project ZIP, and verifies `SEMANTICS_VALID`.
- Duplicate keys in either order, identical duplicates, Unicode-escaped equivalent keys, nested node fields and schema keys are rejected before state commit.
- Broken JSON and invalid escape sequences fail closed.
- Failed imports preserve both the current project and the exact textarea content, and the previously valid project still produces a valid ZIP.
- File-picker imports use the same gate.
- Equal member names in *different objects* remain valid.

The suite passed locally **20/20** with no browser JavaScript errors. GitHub CI additionally executes both unchanged Repair 020 and Repair 021 suites against the Repair 022 HTML and checks inline JavaScript syntax.

## Out of scope and preserved gates

- Do not modify the existing ZIP Verify / Restore strict parser or historical Repair 021 source.
- R020-I02 (low): policy for advisory `manifest.notes` and unknown extension keys remains open.
- BOM handling remains a separate portability-policy question; this repair does not introduce a new BOM prohibition.
- Native `file://` persistence, browser crash durability, historical actor authentication, migration and external specialist signoff remain unverified.
- **No Go lifecycle; Phase 1 authorization stays `false`.** Local and GitHub CI pass does not equal independent approval. The exact committed Repair 022 bytes need an independent adversarial re-audit before approval.

**Branch:** `repair/022-scaffold-strict-admission` from Repair 021 commit `8663d8a6def9295c88060e49bab9128f916107b5`.

**Repair 022 HTML SHA-256:** `9cbeb950e2b4d3ccb1a4b6b0fc07faec41a1dc974d8ca8a5274268287daab3d8`.
