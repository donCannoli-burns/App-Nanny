# Repair 020 — generated ZIP metadata contract

**Status: local candidate, independent re-audit required, Go Phase 1 blocked.**

This branch repairs R019-I01 and R019-I02 and closes the optional R019-I03 generated-README drift through strict generated-output equality. It does not reclassify self-hashed archives as authenticated provenance.

## Canonical metadata

| Member | Required value |
|---|---|
| `manifest.json.sha256Scope` | `exact UTF-8 bytes for each named ZIP member` |
| `tree_{full,context,leafs,core}.json.export.sha256.algorithm` | `SHA-256` |
| `tree_{full,context,leafs,core}.json.export.sha256.scope` | `UTF-8 pretty-printed data payload with terminal LF` |
| `planning_snapshot.json.contentHash.algorithm`, `planning_ledger.json.sha256.algorithm` | `SHA-256` |
| Snapshot / ledger checksum scope | `exact UTF-8 JSON of data (pretty, terminal LF)` |
| `resource_registry.json.format` | `context-tree/resources-v1` |
| `resource_registry.json.priorityPolicy` | Exactly `{ "1": "local convenience", "10": "hard-stop dependency if unavailable or unsafe", "higherNumberMeansMoreCritical": true }` |
| `README.txt` | Exact generated text of `canonicalBundleReadme(manifest.version, manifest.timestamp)` |

The application generates these fields using shared constants and validates them using the same constants. Both **Verify** and **Restore** use `validateBundleSemantics`. A recomputed member SHA-256 can establish byte integrity, not metadata truth.

**README policy decision:** The Studio's `README.txt` in its own generated Full Project ZIP is a deterministic, *normative description of that generated bundle* for semantic-admission purposes. It is not an independent actor's authority or a generalized natural-language instruction to the application. Altered text fails semantic admission; no semantics are inferred by executing or interpreting README prose.

**Legacy policy:** ZIPs using different label spelling, registry policy or noncanonical generated README are rejected with `SEMANTICS_CONFLICT`; no silent migration or rewrite is attempted. Genuine migrations require a separate, opt-in, audited operation.

## Reproducible test approach

The exact SHA-256-pinned `studio/context_tree_studio_authority_repaired_019.html` creates a fresh clean control ZIP via the normal UI at test runtime. `tests/test_metadata_contract_020.py` makes 13 **hash-valid** mutations at runtime, updates the manifest member checksum, and runs the app's actual browser Verify and Restore paths. A clean control must verify, restore, re-export to a self-verifying ZIP, and restore in a second session. The generated mutation ZIPs are temporary and are not committed. Browser `about:blank` tests use an isolated mocked storage backend; they do not establish native `file://` durability.

Run locally:

```bash
python -m pip install playwright==1.57.0
python -m playwright install chromium
python tests/test_metadata_contract_020.py
```

The PR contains a GitHub Actions workflow for this suite. Even a green CI result is **not** independent audit clearance. The frozen Repair 019 checkpoint and its original forensic evidence remain unchanged.
