# App-Nanny Repair 028 — cross-operation async Export authority

**Finding:** R027-I01 · Medium, now reproduced against exact Repair 027 application.  
**Frozen parent commit:** `03f80a97b68143cdf80073b87285ef35ea375475`.  
**Gate:** `LOCAL_CANDIDATE_PASS__CI_AND_INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED`.

## Evidence and technical distinction

The prior review identified a source-traced risk. A full Chromium replay against the actual Repair 027 source verified the flaw, using a valid Full Project ZIP produced by App-Nanny itself. That ZIP contains an intentional project-definition conflict, resolved with the existing human-authority mechanism so that Restore displays a legitimate **Restore-origin** decision dialog.

Four distinct Repair 027 behaviors were reproduced: a suspended `tree_raw` checksum either successfully added a receipt or (after a human brief edit) emitted a failure status while the Restore dialog was open; the separate `doExportLedger()` path reproduced both outcomes. In each case the original unresolved-authority status could be displaced, and successful exports were allowed to commit receipts during another operation's unresolved authority decision. No malformed ZIP or SHA collision was involved.

The negative controls are reproduced against unchanged, SHA-pinned Repair 027 within `tests/test_cross_operation_async_028.py`. This is a different boundary from Repair 027's successfully defended asynchronous **Restore** commits.

## Minimal correction derived from evidence

This repair does not install a general scheduler or rewrite Export/Restore verification. It reuses Repair 027's already implemented monotonic `restoreTransactionGeneration` as a **shared cross-operation authority-intent epoch**, which advances when a newer Restore, Generate, or authority-dialog opening/closure supersedes pending work.

For each `doExport(kind)` and `doExportLedger()`:

- Reject a new export while `pendingAuthorityTask` is non-null.
- Capture originating `state` identity and the shared authority generation before asynchronous work.
- At the final, synchronous download and receipt-commit boundary, require `exportTransactionIsCurrent(originState,originGeneration)` **before** calls that might report a new template error.
- In `catch`, only display an export failure if the originating export is still current. A stale operation must not mask a newer authority dialog or a newer project.
- Keep the existing structural fingerprint/template guards, release/ledger semantics, and Full Project ZIP verification.
- For Full Project ZIP, preserve provisional self-referential receipt rollback exclusively on the original project object. A Restore-origin dialog that captured the provisional state must be reconsidered by the user after this rollback; the old receipt must not be silently accepted as history.

Restore-origin authority tasks now record state-object identity, meaningful project fingerprint, exact editor text/generations, template fingerprint, and dialog epoch when shown. Before Accept can commit that task, those bindings must match the current project and editor. A mismatch leaves the dialog open with `AUTHORITY_INPUT_CHANGED` and requires Cancel plus a fresh Restore attempt. Timer-only autosave details remain excluded by the existing Repair 027 fingerprint contract.

No change to cryptographic ZIP verification, strict JSON admission, fatal UTF-8 decoding, recovery data model, or earlier repair HTML.

## Tests and chain of custody

A separate local exploratory matrix passed **17/17** checks, including four exact Repair 027 negative controls, successful/failed exports, Restore authority accept/cancel, valid exports before the dialog, Full Project provisional receipt rollback, and an out-of-band state-change guard. A compact checked-in equivalent `tests/test_cross_operation_async_028.py` passed **15/15** in Chromium locally, with no page JavaScript exceptions. Source inline JavaScript passes `node --check`.

The checked-in test uses instrumented in-page SHA promise deferral and localStorage emulation, but executes the actual application's export, ZIP generation, Restore, authority UI, and semantic admission logic. This does **not** establish native `file://` persistence or crash durability.

| Artifact | SHA-256 | Git blob |
| --- | --- | --- |
| Studio HTML | `bd00c4c6326efe65a39fc896f567f4ea0b53f12aa01f6372112eb31ec0dcb1f1` | `31b3269a8f8d42632cfa0c26eedf82a2ba32c122` |
| New Playwright test | `213c48c4a7aa2c18df8406fb9849719bd6b1336cc3d2cbe777ca6788b639d24c` | `40b8e228697b0241922c42097daf5daf0ed4bb47` |

CI runs **unchanged Repair 020–027 browser suites against Repair 028 HTML** plus the checked-in 15-case test. CI must actually complete before candidate acceptance, and independent byte-exact adversarial review is still required.

## Independent re-audit suggestions

Stress exports whose hash awaits finish before, during, or after Restore-origin authority dialogs, both Accept and Cancel, stale failures after an unrelated project edit, and the provisional Full Project receipt. Inspect other asynchronous UI operations and status writers without assuming this bounded patch makes all of them safe.

**Governance:** R020-I02 (advisory/extension-metadata policy) remains open. Native `file://` persistence, browser crash durability, authenticated historical actors, legacy migration, and specialist sign-off remain unverified. `phase1_authorized=false`. No Go lifecycle or production mutation. PR remains draft/unmerged; prior repair branches remain frozen.
