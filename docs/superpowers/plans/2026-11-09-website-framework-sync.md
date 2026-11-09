# Website Framework Documentation Synchronization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Review framework changes since the website's October baseline and synchronize practical Chinese and English documentation.

**Architecture:** Keep the existing Astro site and 14 guide pairs. Pin publicly readable development commit `4bb46fe7a8935e6d13962a6c34e02519122c4c53`, retain SDK base version `0.1.0a8`, and verify source links against its published development branch. Add runnable offline paths to existing guides and the tutorial verifier.

**Tech Stack:** Astro, Pagefind, Node, Python, existing source-lock and tutorial checks.

**Spec:** User request “当前框架有更新，review 一下，然后更新网站文档”; contracts in the pinned source's HTTP, stream, managed-node, Temporal-node, adapter-contract and local-documents guides and implementations.

## Global Constraints

- Both locales describe the same immutable source, commands, signatures, outputs and support limits.
- Development source, original a8 archives and frozen private wheels have distinct capabilities; public source availability does not publish a package or grant new platform/model qualification.
- Preserve existing SDK code, historical reviews, real identifiers and old-Run recovery requirements.
- Preserve the pre-existing untracked `architecture/reviews/2026-10-30-framework-followup-review.md` byte-for-byte.
- This task updates and verifies website documentation locally; no SDK publication, main merge, push, remote CI or Cloudflare deployment.

## Review Focus

- Temporal executor nodes permit explicit empty providers only with the registry; ordinary Tool/Transform nodes and session combinations have different support limits.
- Managed-node JSON/config, identity, approval, actual effects and cleanup cannot be inferred from a final display or a retry.
- HTTP GET query mapping and stream policy settings use actual public signatures and reject unsupported inputs.
- Adapter checks distinguish not_run/not_verified, the offline reference and a real business component; default commands never silently contact services.
- Local documents instructions install the separate application and preserve data/config paths, citations and saved-report approval evidence.

### Task 1: Review and source baseline

**Files:** `website/repository.json`, `website/scripts/check-repository-links.mjs`, `website/tests/repository.test.ts`, version-bearing guides, `website/README.md`.
**Interfaces:** Existing repository URLs remain immutable full-SHA links. An explicit published ref lets the remote gate validate development-source ancestry.

- [x] Review changed source contracts and implementations; record actual documentation gaps.
- [x] Verify public commit availability and pin SHA/date, clearly label development-source installation in both locales.
- [x] Correct the remote link gate for the selected public branch and run repository tests and the remote source check.

### Task 2: Practical bilingual coverage

**Files:** Existing bilingual overview, application, integrations, workflows, operations, models/tools, API, recovery and testing guides; `website/scripts/check-tutorials.py`.
**Interfaces:** Preserve existing recipes and source sets; add offline managed-node, identity-profile, node-contract and local-documents commands using the same fixed source.

- [x] Add HTTP GET and bounded stream policy configuration, callable/Schema boundaries and source links.
- [x] Add complete Local managed-node approval/reopen/replay and identity-profile paths; document Temporal's supported subset, prerequisites, capacity and recovery limits.
- [x] Add node adapter checks, API discovery and a separate local-documents application path.
- [x] Extend the existing tutorial verifier for new offline paths and check real outcomes, original identities and effect counts.

### Task 3: Verify and independently review

**Files:** `website/docs-source-lock.json`, `website/reviews/2026-11-09-framework-docs-sync.md`, this plan.
**Interfaces:** Existing website checks/build/search and Python tutorial validation remain the acceptance gates.

- [x] Review source/translation parity before recording all 14 source pairs.
- [x] Run website tests, type checks, bilingual installed-source tutorials, production build, public source links and Cloudflare dry run.
- [x] Obtain one fresh read-only whole-change review; address actionable findings and rerun affected checks.
- [x] Inspect rendered bilingual docs and local search, record actual results and reconfirm the protected file hash.

## Execution Notes

- Ruling: execute the requested documentation update directly in the existing `codex/callable-preview-fixes` feature checkout; it has no tracked working changes, and a protected-file hash snapshot is stored under `/tmp/relf-docs-sync-20261109`. No main branch or user file needs moving.
- Public GitHub API confirmed the exact full SHA above; the source branch is `codex/callable-preview-fixes`, while main remains an earlier snapshot. Review and execution do not authorize merging or publishing that branch.

- Final verification: 33 website tests, 14 source pairs, both locales of the full offline tutorial gate, 32 built pages, 2,027 local targets, 56 public source targets and Cloudflare dry run passed. The original sandbox DNS failure is retained; the failed network step was rerun with network access.
- Final review: three P2 findings and one verifier gap addressed; a missing-role counterexample is rejected after the guard fix. Browser first queries, locale switching and code copying passed locally. No SDK product changes or publication; original untracked file unchanged.

- Added build bootstrap coverage after reviewing the separate-branch baseline: fetch the declared public branch before Cloudflare verification so a main-only clone has the fixed source and advertised tip. Two real Git fixture tests went RED→GREEN; full website suite 33/33 passed. Shell syntax and metadata loading passed.
- Concurrent SDK and technical-doc changes appeared during final checks. They remain outside this task; source review/tutorials continue using immutable public 4bb46fe, and only website files plus this plan are owned here.
