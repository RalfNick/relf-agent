# Stable Local Delivery Implementation Plan

> Native execution in the established checkout, under the user's standing authorization to implement continuously and commit locally. No push, remote CI, deployment or public release. One final read-only review after implementation.

**Goal:** Close the eight-item stable-delivery objective with one exact local candidate, consistent entry documentation and a ready independent onboarding protocol.

**Architecture:** Keep the original Harness and Local/Temporal authorities. Correct only the shared Runtime seconds validator; normal finite values, original control calls, approval/effect/stop responsibilities and release identities stay unchanged. Use the established content-derived private version convention, preserving all old artifacts.

**Tech Stack:** Python 3.12.7 on macOS ARM64; existing setuptools/build, pytest and local dependency wheels. No new dependency, model request or service combination.

**Spec:** Active eight-item goal; [confirmed review](../../../architecture/reviews/2026-10-30-framework-review.md), base `11fa206`. This pre-existing untracked review is retained byte-for-byte as evidence.

## Global constraints

- Scope: existing Agent/Session, semantic RAG, rule Plan/fixed Supervisor, Local Tool graphs and the already accepted event/display-stream subsets. No generic node/reducer, topology/backend, multimodal or enterprise additions.
- Keep valid timeout type/value and existing ValidationError wording. Reject huge integers before dispatch/close-state changes; waiting cancellation remains observation-only.
- Sole current entry: `docs/current-delivery.md`; other current pages link there. Dated historic evidence retains its own version semantics, no regrading old quality/platform reports.
- Candidate: `0.1.0a8+maintenance.<product digest prefix>` from the exact committed source and an isolated build copy. Root Alpha base and all previous wheels/manifests remain unchanged. Only this local candidate is recommended; no index-install claim.
- Candidate gates: same source/installed risk suite (original Alpha selected modules plus affected Runtime/Agent/stream/application/Tool configuration tests); pip/metadata/license/source-byte checks; default CLI/starter and editable application commands outside checkout; original approval/restart/dedup and prior release compatibility. Fix tests first, collect/freeze exact test IDs before final runs, warnings-as-errors. Reuse unchanged actual-model/service evidence with a written dependency mapping, not a new qualification claim.
- External adoption: deliver empty-directory instructions and an unfilled evidence template. No independent participant is established; mark pending and keep internal rehearsal separate. Engineering can freeze without waiting or adding features.
- Final docs/review/local commit, one-command hook bypass and [skip ci]; no persistent hook change.

## Review focus

1. Huge positive/negative ints, bool, NaN/inf and wrong types produce ValidationError without starting/closing work; ordinary zero/int/float values remain valid.
2. Invalid wait on a live Run does not cancel, advance or duplicate work; normal wait still completes it.
3. Local/Temporal shared validator and profile preflight reject before ownership/resource side effects; local close override remains retryable.
4. Candidate metadata/module/CLI and product bytes agree, and historical artifacts do not change; docs must not recommend an older private wheel as current.
5. Offline replacement fixtures/internal rehearsal never become real model quality or independent-adoption claims; scope and platform evidence stay explicit.

## Task 1: Correct the confirmed shared validation boundary

Files: `src/relf_agent/agent_runtime.py`, new `tests/test_runtime_timeout_values.py`, public timeout guide notes.

- [x] Reproduce original constructor/wait overflow with meaningful tests; cover shared validator, Local constructor/profile/close/wait and Temporal constructor/wait using existing fixtures.
- [x] Catch numeric finiteness overflow at the shared guard; retain finite original value and prior error contract.
- [x] Run new tests and related public lifecycle/observation tests; record RED/GREEN and no business cancellation/extra calls.

## Task 2: Freeze one coherent local candidate and current entry

Files: README, `docs/current-delivery.md`, `docs/continuous-development.md`, `docs/implementation-status.md`, installation/getting-started/support journey/index and historical-entry disclaimers as needed. Candidate build and evidence under `dist/stable-delivery-20261030/`.

- [x] Replace stale current assertions with one authoritative entry, preserving historical snapshot text under explicit history headings.
- [ ] Commit the product correction and build-input docs; freeze exact source commit/product digest and build a unique private wheel offline. Archive input hashes, metadata and licenses; install it into a new directory outside checkout.
- [ ] Freeze risk suite selectors/test IDs; run source and exact installed suites, install checks, default CLI/starter/application commands and old/new receipt compatibility. Reuse unchanged service/model evidence with an explicit coverage map. Preserve all failed attempts.

## Task 3: Onboarding, audit and local freeze

Files: `docs/independent-onboarding.md`, evidence template, `architecture/reviews/2026-10-30-stable-local-delivery.md`, final current-entry artifact/hash/gates.

- [ ] Document an empty-directory install + own model/tool + approval + original-factory process restart path, ownership and troubleshooting. Rehearse offline with the installed candidate; record times/failures separately from independent adoption.
- [ ] Final read-only review; fix important scope defects with RED/GREEN, defer nonblocking expansion.
- [ ] Audit all eight requirements against actual files/artifacts/tests/unchanged evidence, run static/link/secret-pattern checks; commit locally and verify original hook configuration, [skip ci], no push. Close engineering objective while external adoption remains pending.
