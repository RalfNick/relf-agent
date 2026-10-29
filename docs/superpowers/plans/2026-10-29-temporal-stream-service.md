# Temporal stream Service verification

**Goal:** Complete actual Service evidence for the existing opt-in Agent stream contract before adding more orchestration surfaces. The full alignment objective remains open.

**Basis:** [Harness/Facade contract](../../../architecture/specs/agent-facade-session-contract.md), [R22 guide](../../agent-stream-updates.md), and the [alignment review](../../../architecture/reviews/2026-10-29-framework-alignment.md). LangGraph's graph/stream APIs and AgentScope's pipeline support are comparison references, not evidence that Relf already satisfies their whole capability set.

**Execution:** Native implementation in this session, then one read-only independent review. The user has repeatedly authorized continuing the recommended work without repeated design approval; this batch adds verification and necessary fixes to the accepted stream protocol, not a new execution design.

## Invariants and scope

- Local/Temporal retain their original authorities, fixed Release, approval, credits, unknown effects and observer-only cancellation.
- Start a new owned loopback Temporal Service with a new database and test queues; stop it in finally. Do not attach to old service/data or use model/account credentials.
- Use the installed SDK and a fixed official CLI. Record version/hash, actual server version, tests/history and shutdown. Retain failed setup attempts.
- Model is a deterministic local stream fixture; tool is an explicitly approved read-only lookup. Audit file writes count fixture dispatches, not business writes or model quality.
- No new Alpha, original a8/a7 rebuild, Git commit/push, CI or publication. No new runtime dependency.

## Task 1 — Actual live stream and authoritative facts

Files: `tests/temporal_stream_worker.py`, `tests/test_temporal_stream_service.py`.

Interfaces: `stream_runtime(root, *, limited=False) -> TemporalRuntime`; `definition() -> AgentSpec`. The fixture exposes one text stream and one approved read-only lookup, with durable dispatch audit and file fences before the first complete response. `worker_main(root, address, queue)` runs the original registered Worker until terminated.

- Observe a model prefix from the actual original Workflow while its Activity is still held; cancel the pending observer read and verify business remains running.
- Release the original response, wait for approval, verify no lookup dispatch, approve with a stable command and repeat the command.
- Collect typed deltas and response/receipt end facts, complete the original Run, check two model calls, one lookup, original credits, no unknown/reserved balance, and History replay without new fixture calls.
- Explicit small presentation quota: one gap, bounded deltas, successful original result and unchanged execution credits.

## Task 2 — Actual Worker process restart

Use the same fixture in an independent process. Start the original Worker, submit and wait for the durable approval state, kill it with no active tool, then start a fresh Worker with the same accepted release/queue.

- Attach the original RunRef through a fresh host. Verify persisted prefix/cursor survives and the first model is not re-executed.
- Approve once, repeat approval, observe the original Run to completion; audit must remain two model calls and one lookup.
- Fetch/replay the actual History with the registered Workflow implementation. Preserve process/log/history evidence and stop all owned processes in finally.

## Task 3 — Regression, installed parity and documentation

- Run actual Service tests against source, keeping every failure and fixing product defects only after reproduction.
- Reuse the last verified private wheel when product bytes are unchanged; otherwise build a new uniquely versioned private wheel. Run the same Service test IDs outside checkout with site-packages import and no src directory.
- Run affected pure-state/Activity/stream/lifecycle tests and Ruff/format/diff/link/hash checks. Do not re-run unrelated full sandbox tests already known to require other privileges; preserve their record.
- Update R22/guide/status with the exact Service subset and remaining windows; do not grant full R22, enterprise/platform/model quality or a8 qualification.

## Review focus

1. Signal/Activity completion ordering: a displayed prefix cannot be adopted as a decision.
2. Observer cancellation/close cannot cancel the original Activity or Worker.
3. Approval and Worker restart must not dispatch an unapproved tool or replay the accepted first model.
4. Quota/transport gaps cannot affect business success, budget or authorize retries.
5. A passing in-process fixture must not be used as evidence of process restart, actual business-write semantics or online model quality.

## Ledger

- Initial fixed download attempt used `1.9.1`; official download endpoint returned404. The `v1.9.1` retry and all setup results are retained under `dist/temporal-stream-service-20261029/`.
- The SDK transfer stayed slow and was stopped; the same official GitHub Release archive downloaded successfully. Extracted binary matches pinned SHA33c298d4..., CLI1.9.1/Server1.32.0; actual SDK1.34.0. Prerequisite Service started/connected/stopped with a new database.
- Initial actual Service 2 passed / 1 failed: fixture launched with -m registered __main__ Provider entries, differing from the client's canonical imported module. Fixed fixture import only, retaining identity enforcement and the 30-second wait.
- Independent review found restart needed its own repeated approval assertion to meet Task2; added it plus original returncode and final Worker PID exit records. No requirement narrowed. Earlier successful3+3 and initial failure preserved separately.
- Final source Service3 passed / installed Service3 passed, identical tests, SDK versions and original private wheel25a05bee...; six actual Histories independently replayed with unchanged audits. Source/installed final stages are source-final-repeat and installed-final-repeat.
- Product448 files unchanged. Default affected regression57 passed /3 service-config skips; real service tests independently pass above. No full SDK/platform/model-quality/enterprise/a8 qualification. Final static/hash/link audit and supported-subset record are retained with the evidence.
