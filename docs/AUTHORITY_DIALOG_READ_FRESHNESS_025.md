# Repair 025 — authority-dialog file-read freshness

**Independent finding:** R024-I01 · Medium · Repair 024 `CORE_INVARIANT_FAILURE`.

**Base:** Repair 024 commit `750c9c050cc3a336ce53e0771241e7e8ac07cd00` (frozen).

**Gate:** `IMPLEMENTED_CANDIDATE__CI_AND_INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`.

## Contract

When the user clicks **Generate / replace tree**, the application captures the current editable scaffold as an import task. That task may immediately commit, be rejected, or be suspended while the human chooses an authoritative project identity. In all cases, an earlier unfinished file selection must not overwrite the captured scaffold.

Repair 024's file-read freshness predicate tracked file-selection generation, editor generation, exact editor text and active project-state identity. Those signals do not change merely because a project-authority modal opens. Consequently, an old file read could update the textarea to B after task A had been captured, while the modal could still accept A. The resulting valid backup represented A even though the editor displayed B.

Repair 025 introduces three **narrow UI-only fences**:

1. On an admitted Generate attempt (after live-mode and replace-confirmation guards), capture the original textarea and advance `scaffoldSelectionGeneration` and `scaffoldEditorGeneration`. This invalidates previously started file reads whether the next step is parsing, immediate import or an authority dialog.
2. `scaffoldFileReadIsCurrent` requires `pendingAuthorityTask===null`, so reads started while a human decision remains unresolved cannot change the editor or overwrite conflict status.
3. `closeAuthorityDialog()` advances both generations before clearing the task, invalidating reads started while the dialog was open even if they complete after **Accept** or **Cancel**.

The same freshness predicate gates both successful file results and rejected read/decode promises. Current valid file selections after a dialog is settled continue to work.

**Unchanged:** Repair 023's exact-byte `File.arrayBuffer` + fatal UTF-8 decoder, Repair 022's strict Generate JSON parser, prior ZIP Verify/Restore admission and metadata contract. No code is executed from imported scaffolds.

## Test contract

`tests/test_authority_dialog_read_freshness_025.py` uses controlled Chromium `File.arrayBuffer` promises and the exact SHA-256-pinned Repair 024 HTML as a negative control. It asserts:

- Parent vulnerability: B finishes after Generate captured A, overwrites the editor; the human approves A, and a valid Full Project ZIP contains A while the textarea displays B.
- Candidate: approval and cancellation both suppress stale B completions, preserve the captured editor, and leave the actual project backupable.
- Completion before Generate remains valid: if B is already in the textarea when Generate captures, importing B is legitimate.
- Reads **started during** an authority dialog cannot override text either during the modal or after acceptance/cancellation.
- Stale I/O errors and fatal UTF-8 failures cannot mask an unresolved-authority warning.
- New file choices after settlement still load normally.

The CI suite uses synthetic localStorage in disposable browser contexts; this does **not** prove durable native `file://` persistence.

## Remaining authorization gates

R020-I02 advisory/extension metadata remains open. Native `file://` persistence, browser crash durability, authenticated historical actors, legacy migration and specialist sign-off remain unresolved.

**Go Phase 1 authorization: `false`.** No production repository or previous repair branch may be mutated by this test-only candidate. Even passing CI requires a fresh independent byte-exact adversarial review before owner merge consideration.

**Repair 025 HTML SHA-256:** `dab25c2b1b7caa7a6c58f620c32da47194cbd25a162b902f7df5b76079401be2`

**Repair 025 test SHA-256:** `39901177ac6e2cb86191546a4ecfbcc2eb6ab7cfc7629f612bcb016b7a8a6d8e`.
