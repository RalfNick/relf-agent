# Callable, approval preview and delivery fixes

> Implement bounded tasks with TDD in parallel, then one fresh consolidated review. Local commits only.

**Goal:** Fix the three P2 and two P3 findings from the main/e94c57c review, freeze exact new SDK/application candidates and verify isolated installation.

**Architecture:** Preserve Harness proposals, Local/Temporal execution authority, action/approval/effect identities and resource ownership. Clarify callable admission and transient direct executable pins; render terminal data inertly while keeping original approved bytes. Preserve fixed website tutorial code and give current delivery a distinct link.

**Spec:** User's 2026-11-01 instruction; reproduced review evidence under dist/main-review-e94c57c-20261101. Existing local-documents application design remains binding.

## Global constraints

- No new runtime features, backends, dependencies, model requests, remote CI, pushes, deployment or public releases.
- Preserve persisted tool Manifest/implementation_digest, and ordinary handler/reconciler forms. Static inspection must not run descriptor getters or serialize closures, defaults, arguments, object state or credentials.
- Explicitly support ordinary functions/methods, partials/subclasses, callable instances with plain/property Python __call__, and accepted class constructors through stable direct entries. Unsupported opaque descriptors must fail clearly at registration; do not guess or execute them as validation.
- Validate class metaclass-call/new/init and inherited entries; descriptor getters are code entries, dynamically returned arbitrary dependencies retain explicit version/config responsibility. Preserve get() for cleanup.
- Human preview must show controls as visible escapes, including ANSI/OSC, carriage returns, backspace and bidi formatting; retain line breaks and tabs. Machine JSON stays parseable. Exact original report body, hash, action/digest and create-only write receipt stay unchanged.
- Only current delivery/status statements reflect already-completed e94c57c source pushes; historical receipts retain their chronology. New fixes remain local. Preserve old source/artifact records, fixed website tutorial ref300c62c and original untracked review.
- New candidate versions uniquely bind source inputs; source base versions remain0.1.0a8/0.1.0, isolated build patches match metadata/module versions. Freeze SDK/app wheels and sdists, install outside checkout.

## Review focus

- Descriptor-based callable no-mutation stability, constructor/metaclass/inheritance drift, handler/reconciler/queued/in-flight adoption and safe cleanup.
- Descriptor validation purity, supported-form errors before publication and original manifest/recovery compatibility; no blanket arbitrary Python integrity claim.
- Untrusted fields in all human output and approval confirmation, ESC/OSC/C0/C1/bidi/CR/backspace, no change to payload or machine IDs/JSON.
- Current status vs completed main push vs this local batch; website historical source links stay fixed while current-delivery links reach main.
- Exact package metadata, code and standalone sdist assets; identical installed regression nodes, original effect receipts and archived artifact bytes.

## Task 1 — bounded callable contracts

Files: src/relf_agent/tools.py and a small internal helper only if needed; tests/test_generic_tool_pins.py or a new focused module; docs/extending.md.

- [ ] Add RED tests for unchanged property __call__, getter/code replacement, accepted class __init__/__new__/metaclass drift, inherited entries, both execution and reconciliation; preserve baseline manifest values and no getter execution during registration/checks.
- [ ] Implement stable static descriptor/code pins and clear unsupported-form admission, preserving existing runtime boundaries and saved identity format.
- [ ] Pass new and adjacent tool/approval/lifecycle tests; record exact commands/counts and limitations.

## Task 2 — inert human terminal presentation

Files: examples/local_documents/src/local_documents/cli.py; focused new app tests; app README notes.

- [ ] Reproduce raw ANSI hidden paragraph and other terminal controls in default preview. Add end-to-end original approval/save/hash and JSON parsing tests.
- [ ] Escape untrusted text for human display at a common output boundary, including history/errors/paths; keep original strings and structured JSON intact. Preserve existing plain-text UX and cancellation semantics.
- [ ] Pass targeted UI/input/approval and installed-original-byte checks.

## Task 3 — current website link

Files: website/src/lib/repository.mjs, website guides zh/en, scripts/tests that assert repository links.

- [ ] Add failing current-delivery resolution assertion.
- [ ] Introduce a distinct current-delivery link mapping to main; keep existing repo: tutorial links pinned to300c62c and validate paths strictly.
- [ ] Pass website unit, link/doc checks and local build without deployment/network; retain baseline verification date.

## Task 4 — state and immutable candidates

- [ ] Update current status to record e94c57c main push with zero observed CI, private artifacts/no release, and this batch's local-only scope; historical records unchanged.
- [ ] Concentrated fresh review with one regression-first correction pass; run source impact suite and style, then local implementation commit with [skip ci] and single-command hook bypass.
- [ ] Build exact archived commit into unique SDK/app wheels and sdists, pin app SDK dependency, preserve prior21 artifacts. No overwrites.
- [ ] Run the frozen previous1320 selection plus new relevant cases, same IDs in source/installed environments; validate standalone SDK sdist app, runtime-only startup and old/new Local approval/recovery/dedup. No repeat true-model/platform qualification.
- [ ] Record acceptance and explicit remaining limits; local documentation commit, hook/worktree/artifact postcommit audit. No push or public release.
