# Intended architecture (not implemented by the current HTML)

**Name:** App-Nanny  
**Model:** Detachable Development Layer (DDL)  
**Preferred implementation:** Pure Go, with an optional embedded HTML5/SVG interface.

The intended global command is `app-nanny`; an optional, explicitly authorized `app-nanny --init` could create a detachable repository-local development layer. A later Go-only tree-sitter implementation may be evaluated for repository inspection. These are **design intentions**, not current CLI capabilities.

## Core invariants

- `TOOL_REMOVAL != PRODUCTION_FAILURE`
- `OBSERVATION != MODIFICATION`
- `UI != EXECUTION_AUTHORITY`
- `INFERENCE != VERIFIED_FACT`
- `GLOBAL_UPDATE != REPOSITORY_MUTATION`
- `DETACH != DESTRUCTIVE_CLEANUP`
- `HOST_REPOSITORY != TOOL_OWNERSHIP`

A development tool may read a repository without taking ownership of it; project modification requires explicit, narrowly scoped approval. The resulting production application must not require App-Nanny to remain installed.

## Current checkpoint boundary

The committed HTML Studio is a proof-of-concept planning/export artifact under independent adversarial review. It must not be interpreted as a working Go transport, global executable, repository mutation engine, release gate, or secure backup authority.

**Phase 1 is blocked** until separate authorization and successful independent review.
