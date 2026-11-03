# Repair 026 — authority-modal interaction isolation

**Finding:** R025-I01 · Medium · now reproduced end-to-end against exact Repair 025 bytes.

**Frozen base:** `ad5800171cdff62a4435a239d9b0918b5a15a9af`, Repair 025 HTML SHA-256 `dab25c2b1b7caa7a6c58f620c32da47194cbd25a162b902f7df5b76079401be2`.

**Status:** `LOCAL_CANDIDATE_PASS__CI_AND_INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`.

## Independent local reproduction — no assumed patch

The actual unmodified Repair 025 Studio was loaded in isolated Chromium with mock localStorage. After importing Original Project, Generate captured Import Candidate A and displayed an unresolved human-authority dialog. From the modal's rationale box, **49 physical Shift+Tab keystrokes** navigated focus into the background `#jsonInput` editor. Typing File B, then approving the still-pending A task, produced active project A with editor B and a successful `SEMANTICS_VALID` import.

A second full-application reproduction used physical Shift+Tab to reach the background Generate control. Pressing Enter reentered the Generate handler, resetting the dialog rationale. This showed that keyboard focus escape and reentrant background dispatch are separate effects of the same missing modal boundary. They were not introduced by Repair 025's asynchronous-file-read fencing.

## Bounded candidate and rationale

The smallest defensible local boundary is **modal interaction isolation plus acceptance-time task binding**:

- On opening a pending authority dialog, set the sibling `.app` workbench `inert=true`, retaining the previous focus target.
- Trap Tab / Shift+Tab navigation within the actual dialog's visible enabled controls. Inertness alone left the document BODY in the native Chromium tab sequence, so explicit focus trapping was required by a failed initial local test.
- While a task is pending, global click/input/change handlers reject background actions, including reentrant Generate, demo replacement, exports, and project edits.
- Allow synthetic `scaffoldFile` change events to reach the **existing** guarded file-read path for backwards-compatible regression testing; the pending-task predicate still prevents their success/error continuations from updating the editor or status.
- Before Accept commits an import task, require the same captured state-object identity and **exact original editable scaffold text**. If either changed by out-of-band JavaScript, keep the modal open and require Cancel followed by a fresh Generate.
- On Accept/Cancel, remove `inert`, hide the modal, restore prior focus where still attached, and preserve Repair 025's modal-period file-read generation invalidation.

This is a UI and transaction-admission repair. It does **not** claim that DOM inertness prevents arbitrary scripts from modifying page memory; acceptance-time checks fail closed if an out-of-band editor change occurred.

No existing ZIP semantic verifier, Restore, strict JSON parser, fatal UTF-8 decoding, or original Repair 025 source was changed.

## Verified local tests and required CI

Exact Repair 025 browser negative controls independently reproduce both **keyboard editor/project disagreement** and **background Generate reentry**. The Repair 026 test then checks focus containment in both Tab directions, A import / Full Project ZIP semantic verification, reentrant background action suppression, stale editor-text fail-closed, both authoritative-definition choices, cancellation and fresh Generate, and modal rationale validation.

**Local Chromium: 10/10 passing checks; 0 page exceptions.**

CI runs unchanged Repair 020/021/022/023/024/025 suites against Repair 026, plus its ten-case test. The historical suites are not credited as passing until hosted CI actually reports their results.

Source SHA-256 `0f3b37f2c0f8f1ec5d2046a5ee11fa73323b715161b6f065751363f9382f6a98`.

Test SHA-256 `1ac432050d7aaafa2a6278db89794c760ea169b768db791c2bd225ea47d82097`.

## Preserved authority gates

- R020-I02 advisory/extension metadata remains open.
- Native `file://` persistence, browser crash durability, authenticated historical actor identity, legacy-data migration, and external specialist signoff remain unverified.
- **`phase1_authorized=false`**, no Go lifecycle. This draft stays unmerged pending new byte-exact independent re-audit, and the owner retains final merge authority.
