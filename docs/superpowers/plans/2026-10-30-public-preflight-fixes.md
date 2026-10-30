# Public Entry Preflight Fixes Implementation Plan

> Native execution in the established checkout under the user's explicit instruction to fix, validate, freeze and commit locally. No repeated worktree/plan approval; no push, remote CI, deployment or publication. One fresh read-only final review.

**Goal:** Fix the confirmed one P2 and four P3 findings on bf65e58, preserve execution semantics and freeze one new exact private candidate with source/install evidence.

**Architecture:** Reuse pure argument validation and the existing cleanup-origin guard before durable submit or entry detachment. Local and Temporal remain the execution authorities; original handles, controls, approval/effect/credit/actual-stop facts and retryable owned cleanup are unchanged. No new public extension, backend, topology or dependency.

**Tech Stack:** Python3.12.7/macOS ARM64, existing pytest/build/setuptools and local wheelhouses.

**Spec:** User's 2026-10-30 instruction; five repro-backed findings in `dist/review-bf65e58-20261030/review.md` and `review-summary.json`; base bf65e584a039d9b2f24814ac5f48bcc9f848bbcd.

## Global constraints

- Invalid wait_timeout/terminal_only on Agent.run and both Session.run wrappers must reject before durable admission, model/tool dispatch, Session turn or credit reservation. Valid run and direct-handle observation cancellation remain unchanged.
- Invalid owned-Agent close options or wrong cleanup origin must leave the entry usable if no shutdown started. Real shutdown/failure/cancelled close waits still detach the entry and retain owned resources for retry. Already closed Runtime keeps its idempotent no-op behavior; borrowed Agent only detaches its entry.
- Resource callback reentry must use BuildContext's original guard before facade waits for its own shutdown. External concurrent close observers must still coalesce, not become resource-callback rejection.
- Event subscription keeps its original finite supported ranges and strict bool rejection; huge integers become ValidationError without source calls.
- Current entry distinguishes already-pushed bf65e58, this new local-only source/candidate, private artifact distribution and unchanged platform/public qualification. Original artifacts, failed tests and version-specific reports stay immutable.
- New private version follows existing `0.1.0a8+maintenance.<product digest>` convention; source Alpha base unchanged, build-copy metadata/module/CLI agree. Do not rebuild any prior candidate.
- Freeze existing937 node IDs plus new regressions and affected event/Temporal Session client checks; same source/installed bytes, -W error, original one service deselection. Do not mechanically rerun unrelated whole SDK/model/service matrices: user requested the review's bounded affected checks and installation gates. Reuse unchanged engine/provider/History/model/service evidence with an explicit dependency map.
- End: independent review, static/links/byte/protected-artifact checks, local commits with one-command hook bypass+[skip ci]. No push or publication. External adoption remains pending.

## Review focus

1. Invalid options before admission: zero Runs/turns/commands/reservations/effects, then a valid retry with the same command works; Local and Temporal client wrappers.
2. Close preflight failure: entry and Runtime stay open; original loop, closed no-op, borrowed ownership and unknown options behave consistently.
3. Cleanup callback reentry: immediate ValidationError; handled callbacks can finish, unhandled failures retain one resource and retry safely; no false rejection of external close observers.
4. Event numeric boundaries: oversized positive/negative ints, nonfinite floats, bool and valid inclusive endpoints preserve error/range behavior.
5. Candidate remains distinct from all previous versions; exact source commit, wheel hash, supported combinations and old/new local receipts are accurately recorded without promoting fixtures to real quality or independent adoption.

## Task 1 — Regression-first minimal fixes

Files: new `tests/test_facade_preflight_review.py`, `tests/test_event_timeout_values.py`; modify `agent.py`, `agent_runtime.py`, `agent_session.py`, `temporal_agent_runtime.py`, `temporal_agent_session.py`, `event_stream.py`; API close/observation notes as needed.

- [x] Write real Local admission/effect/Session tests and existing Temporal transport/state tests for preflight; test ordinary valid retry.
- [x] Add owned close/preflight and builder-owned resource reentry/retry cases, plus event range tests. Observe expected RED without product edits.
- [x] Add a private shared wait validator before three submit+wait entry points; reuse it in direct waits. Reuse a side-effect-free facade close preflight for owned Agent and Runtime, retaining original close task authority; compare event bounds before finiteness.
- [x] Run new and existing affected lifecycle/observation checks; preserve RED and GREEN evidence.

## Task 2 — Exact candidate and install gates

Build/evidence: new `dist/public-preflight-fixes-20261030/`; record first code/test source commit before isolated offline build. Reuse established private wheel preparation with new output paths and exact product digest; never overwrite previous directories.

- [x] Update current source-push/candidate preparation state and API contracts, commit the tested build inputs locally, freeze product/source manifests and unique private version.
- [x] Build/install exact wheel outside checkout, check metadata/module/CLI/license/dependencies and all product bytes. Freeze old937 plus risk-added node IDs and same original deselection, run serial source/install suites.
- [x] Run installed default application/replacement/approval/restart/dedup and original candidate↔new candidate Local receipt compatibility using fresh isolated directories; keep internal-only quality labels.

## Task 3 — Document and freeze

Files: `docs/current-delivery.md` (sole authority/support matrix), `docs/agent-api.md`, current entry pointers if needed, `architecture/reviews/2026-10-30-public-preflight-fixes.md`, safe machine-readable evidence under evals/results.

- [x] Record all five fixes with exact test scope, previous source push, new source/package/hash, unchanged support boundary, historical evidence reuse and independent-adoption/platform limitations.
- [x] Fresh read-only final review: zero Critical/Important/Minor findings; 41 new cases independently passed. No correction pass or product rebuild needed. Arbitrary indirect user-task cleanup cycles, fresh real-quality/adoption/platform qualification remain outside this bounded repair.
- [x] Audit source/install IDs/bytes and old artifacts/quality DBs, static checks and relative links; local final commit with [skip ci]/one-command hook bypass, verify clean tree and unchanged hook. No push/public release. Final local commit receipt is retained in the ignored evidence directory, avoiding self-referential source hashes.

### Acceptance

Exact source `4af364b403ed9ee01487cc8eb571d242a5bece7b`; private candidate `0.1.0a8+maintenance.0608576182db502f`. Source and installed risk suites each passed1002 with the same original one service deselection, preserving old937/Alpha370 nodes. Core-only install without Temporal, 30-command internal application/receipt recovery, Ruff/format/links, 10 protected artifacts and204 historical DBs passed. Evidence: `dist/public-preflight-fixes-20261030/validation-summary.json`; sole delivery entry: [current delivery](../../current-delivery.md). Public quality/adoption/platform boundaries are unchanged.
