# Fixed HTTP Write Methods Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Keep shared-file ownership explicit.

**Goal:** Support fixed JSON PUT/PATCH and opt-in empty 204 through existing tools.

**Architecture:** HTTPToolSource and its async factory keep their original resource
ledger and managed Action path. Only request encoding and explicit response
acceptance extend; Local/Temporal retain their unique execution authority.

**Tech Stack:** Python 3.11+, httpx, pytest, existing SDK builders.

**Spec:** [Design](../specs/2026-11-10-http-write-methods-design.md).

## Global constraints

Preserve old identities/defaults, actual handler ownership and original test
deadlines. Preserve a8 and all history. Local commit with a single hook override;
no push, remote CI, public release or changes to unrelated website work.

## Review focus

- Non-boolean empty-response options fail before resource allocation.
- Empty 200, malformed 204 framing and mismatched null Schema cannot succeed.
- PUT/PATCH cannot accidentally use GET query transport or infer idempotency.
- Cancelled close retains actual work and can be retried without redispatch.
- Lost responses keep original unknown effects and stable effect keys.

## Tasks

- [x] Product/test owner: write failing protocol/configuration tests, record RED;
  minimally extend source, transport and factory, then run focused GREEN.
- [x] Execution/test owner: test original approval/reopen, unknown effects and
  cancellation/close retry for new options, without modifying execution engines.
- [x] Root: update current comparison and user guide, build a uniquely versioned
  private candidate; repeat selected tests outside checkout and runtime-only
  install, check sdist and old metadata, review and commit owned paths only.
