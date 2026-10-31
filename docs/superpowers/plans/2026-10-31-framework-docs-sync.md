# Framework Documentation Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Synchronize the bilingual website with the optimized framework's usable public maintenance source and verify its documented user journeys.

**Architecture:** Keep the existing Astro/Pagefind site, 14 bilingual guide pairs and pinned-source validation. Pin public commit `300c62ce8dd417df6b471ce1c10a1b7a562d2c46` (source base version `0.1.0a8`) and distinguish that source installation from original a8 archives and the privately frozen maintenance wheel. Add practical Agent lifecycle/events/stream and model-free Local Tool examples without changing SDK implementation.

**Tech Stack:** Astro 7, Node 24, Pagefind 1.5.2, Python 3.12, existing website source-lock/tutorial/build checks.

**Spec:** User request “对 Agent 框架做了优化，同步优化一下文档”; factual contracts in the fixed source's `docs/agent-api.md`, `docs/agent-stream-updates.md`, `docs/support-journey.md`, `docs/managed-tools.md` and `docs/runtime-assembly.md`.

## Global Constraints

- Chinese and English describe the same fixed source, actual signatures, executable examples and support limits.
- Source checkout reports base `0.1.0a8`; it is not the original a8 artifact or private `0.1.0a8+maintenance.0608576182db502f` wheel. No new package, platform, external-adoption or model-quality qualification follows from website checks.
- Preserve real `.ralf`, RalfError, RalfNick and Worker identifiers, historical evidence and old-Run configuration requirements.
- Do not edit or stage pre-existing changes in `docs/current-delivery.md`, `docs/continuous-development.md` or `architecture/reviews/2026-10-30-framework-followup-review.md`.
- Honor the current delivery freeze: documentation/tutorial work and a local commit only; no SDK code changes, remote CI, push, deployment, contact or publication.

## Review Focus

- Public instructions must work without a private wheel or repository examples: use generated journey/customize modules after installed source.
- Event subscriptions follow through pauses, advance only delivered cursors, and never resume/cancel business implicitly.
- Stream deltas and end events are observations; committed snapshots/effect receipts remain authoritative and arbitrary stdout/reasoning/node dataflow are outside the delivered scope.
- Invalid waits/close preflight are rejected before side effects; accepted execution, ownership, CloseIncomplete and retry semantics remain accurate.
- Empty providers are explicit and only valid for finite Local Tool/Transform graphs; ordinary Agent/Temporal still need their Provider configuration.

### Task 1: Fixed baseline and basic onboarding

**Files:** `website/repository.json`, `website/src/content/guides/{zh,en}/{installation,quickstart,overview,app-tutorial}.md`, other version-bearing guides, `website/src/components/Home.astro`, `website/README.md`, `website/tests/repository.test.ts`.
**Interfaces:** `repositoryInfo` keeps its shape; tutorial bash uses installed a8-maintenance source CLI and generated `agent_app.journey`/`customize`.

- [x] Record pre-existing file hashes and current source/document drift; verify public source ancestry.
- [x] Update version/date/source and bilingual candidate/install explanations; revise application tutorial to generated installed modules and explicit model/tool/memory injection.
- [x] Run existing tests and source-lock checks; distinguish expected old-baseline failures from actual regressions.

### Task 2: Capabilities, API and practical observation workflows

**Files:** `website/src/content/guides/{zh,en}/{api-reference,models-tools,operations,workflows,sessions-memory,recovery,testing,integrations}.md` as contract changes require; `website/scripts/check-tutorials.py`.
**Interfaces:** preserve existing CLI recipes and assertions; add executable Agent, resumable-event, stream example and async Tool graph recipes against the fixed source.

- [x] Document current Agent constructor/Run methods, cancellation, references, preflight and close ownership.
- [x] Add an offline Agent lifecycle/event example, explicit opt-in bounded stream/replay path and support limits.
- [x] Add complete model-free Local Tool graph init/submit/approve/resume/repeat path with original factory/config and independent effect evidence.
- [x] Extend the existing tutorial verifier only for new executable paths; require real completed outcomes and original Run identities; no model/service credentials or SDK suite expansion.

### Task 3: Source parity, production build and review

**Files:** `website/docs-source-lock.json`, acceptance record under `website/reviews/`, this plan.
**Interfaces:** Existing `npm run verify:production` remains the final website gate; local built pages/search reflect this exact source.

- [x] Compare every listed technical source against the fixed Git snapshot, review both locales, then record all 14 source pairs.
- [x] Execute isolated installed-source tutorials for both locales, run website tests/type checks/build/remote source links/dry run and read final results.
- [x] Obtain one fresh read-only review, fix actionable issues, repeat affected checks and inspect rendered bilingual pages/search.
- [x] Record actual evidence, verify original dirty files unchanged, locally commit only this task's changes and leave publication unchanged.
