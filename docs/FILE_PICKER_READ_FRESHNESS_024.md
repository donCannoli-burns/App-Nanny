# Repair 024 — asynchronous scaffold file-read freshness

**Finding:** R023-I01 · Medium · Independently reproduced against Repair 023.

**Gate:** `LOCAL_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`

**Base:** immutable Repair 023 commit `7405e3b482aba6282cd426c810efaf6a076718b6`.

## Authority rule

The scaffold file picker in Repair 023 correctly validates original file bytes with `file.arrayBuffer()` and fatal UTF-8 decoding, but its asynchronous completion writes to the editable JSON textarea without determining whether its originating selection remains current.

Repair 024 adds two **UI-only monotonic generations** and a project-state identity guard:

- `scaffoldSelectionGeneration` increments on every file-picker change, including an empty selection. Only the newest outstanding selection can commit its decoded text.
- `scaffoldEditorGeneration` increments when the user edits `#jsonInput`, when **Load Demo** programmatically replaces that text, and when a successful file read replaces the textarea.
- The read captures the current project-state object and the exact editor text when selected. Completion requires unchanged project identity and unchanged text, in addition to matching generation values.
- **Both `.then` and `.catch`** are fenced, so stale successes do not overwrite newer input and stale failures do not overwrite the newer status.
- Current read errors and fatal UTF-8 failures remain visible; no errors or input bytes are silently converted into valid projects.
- The input file control remains reset so selecting the same corrected file is possible.

This is not a security claim about authenticated authorship. JavaScript is a single-threaded event loop; monotonic generation checks prevent stale asynchronous continuations from being accepted as newer user intent.

## Regression evidence

A deterministic Chromium harness intercepts `File.prototype.arrayBuffer` for JSON file selection and supplies completion/rejection in a controlled order.

- **Exact Repair 023 negative baseline reproduced:** B completes and fills the editor, A completes later and overwrites B.
- **Repair 024 full local harness:** **17/17** passed, covering both orders, Generate after B completion, semantically valid Full Project ZIP, manual editing, edit-then-revert, Load Demo, project replacement, stale read errors, stale UTF-8 errors, active read errors, empty selection, valid Unicode and BOM.
- **Repair 024 compact CI harness:** **15/15** passed locally and is checked in under `tests/test_file_picker_freshness_024.py`.
- Source verified with `node --check`; exact HTML SHA-256 is recorded in the checkpoint.
- GitHub CI runs the existing unchanged Repairs 020, 021, 022, 023 suites against Repair 024, plus the new 15-case deterministic test.

## Limits and open issues

Repair 024 **does not modify** the strict Generate JSON admission, historical ZIP Verify/Restore, or the Repair 023 fatal UTF-8 decoder. A native `file://` persistence test is still blocked; browser tests use isolated in-memory localStorage. Crash durability, authenticated historical actor identity, legacy migration, and external specialist signoff remain unverified.

R020-I02 remains a separate low-priority open contract issue about advisory metadata and unrecognized extension fields.

**No Go lifecycle has started. `phase1_authorized=false`.** Passing local or GitHub CI does not constitute independent adversarial approval, merge authorization or production readiness.
