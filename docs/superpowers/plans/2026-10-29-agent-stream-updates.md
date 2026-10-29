# Unified Agent stream updates implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; one fresh read-only reviewer at the end. Do not delegate implementation or push.

**Goal:** Stream model text and explicitly reported async-tool progress through the original Agent event entry, preserving response/effect recovery and observation-only cancellation.

**Architecture:** Explicit StreamUpdatePolicy freezes bounded presentation in the accepted release. StreamedModelProvider consumes one existing Provider iterator and returns only its complete response after exhaustion. Authorities provide an Attempt-scoped reporting context: Local appends to its original event log; Temporal signals the original Workflow epoch, which validates and appends presentation events to History. No presentation buffer becomes a scheduler or an effect receipt. AgentRun.stream_updates projects the existing resumable event subscription into typed AgentStreamEvent records.

**Tech stack:** Python 3.11+, existing asyncio/contextvars/dataclasses, SQLite execution store, optional installed Temporal SDK. No new dependencies.

**Spec:** [approved Harness viewpoint](../../../architecture/viewpoints/harness-runtime.md), [Facade contract](../../../architecture/specs/agent-facade-session-contract.md), [alignment priorities](../../../architecture/reviews/2026-10-29-framework-alignment.md).

## Global constraints

Latest user goal update: freeze this first lifecycle/event/stream batch, then handle developer experience as a separate delivery. Default local commits are now authorized; push/CI/deployment/publication still require explicit authorization. The older commit constraint below records its earlier scope. Direct Tool-node exploration was preserved separately and removed from this batch. Final recommendation and exact evidence are in [the freeze record](../../../architecture/reviews/2026-10-29-stream-batch-freeze.md).

- Local and Temporal each retain their original single execution authority.
- Keep original a8/a7 artifacts, manifests and all failed evidence; private installation builds use unique local versions.
- Default policy None preserves existing release/event behavior; enabling uses an explicit immutable policy.
- Presentation never approves/executes a tool, settles credits, or claims a successful business outcome.
- Closing/cancelling a subscription only stops observation. Actual source cancellation and resource ownership retain existing rules.
- Model response/effect receipt recording precedes adoption. Observation errors cannot erase completed evidence or cause a new business attempt.
- Model text only; async tool JSON progress is explicit. No automatic reasoning, tool-argument deltas, synchronous stdout interception, or UI/network endpoint work.
- Initial commit 19dcc60 already completed with the single authorized hook bypass. New phase remains uncommitted unless separately requested; no push, CI dispatch or publication.

## Review focus

1. A producer emits text then fails, emits extra data after a final response, or is cancelled: no partial decision; close the iterator and keep the original unknown-effect behavior.
2. Slow/disconnected observers and progress overflow: durable cursor replay, bounded producer publication, explicit gaps, no business cancellation.
3. Tool writes before a receipt/adoption crash: progress cannot confirm effects or bypass original reconciliation; repeated control still executes once.
4. Foreign Scope/Run/epoch/Action/Attempt and duplicate/out-of-order Temporal signals: reject or mark gaps without state progression, revision bump or extra tool/model calls.
5. Provider/policy drift and cleanup failure: retain known evidence, refuse subsequent dispatch, and preserve the original Runtime resource boundary.

## Task 1 — Bounded update contracts and source adapter

Files: create `stream_updates.py`, `stream_reporting.py`, `streamed_provider.py`; export supported SDK names from `__init__.py`.

Interfaces:
- `StreamUpdatePolicy(max_deltas=64, max_bytes=65536, max_payload_bytes=4096, publish_timeout=0.25)`, finite validated identity / from_identity.
- `AgentStreamEvent(envelope)` projects original run facts, model/tool deltas, gaps, and receipt end markers; JSON payload is detached; cursor is the original EventCursor.
- `StreamedModelProvider(provider, chunk_chars=128)` borrows the existing provider, keeps capabilities/continuation and original typed response, validates one final response at EOF, closes the iterator.
- `await emit_tool_delta(payload: dict) -> bool` reports inside an original managed async Attempt; otherwise False. This is observation feedback, not execution acknowledgment.

- [x] Write failing tests for limits/finite JSON, detachment, no-context reporting, stream ordering/EOF/extra final/errors/cancellation and complete response continuation.
- [x] Run RED, implement the minimum contracts/adapter, run GREEN.

## Task 2 — Original authority integration and common Agent entry

Files: modify `engine.py`, `agent_runtime.py`, `temporal_activities.py`, `temporal_state.py`, `temporal_workflow.py`; create `local_stream_updates.py` and `temporal_stream_updates.py`.

Interfaces:
- Optional `stream_updates=StreamUpdatePolicy(...)` on LocalEngine / TemporalRuntime; identity pinned in manifest, absent by default.
- Attempt reporting context captures original Scope, run_id, release, epoch, action_id, attempt_id and operation. It publishes only bounded completed JSON, never starts background dispatch.
- Local publisher uses the original Store transaction/emit; failed display publication degrades progress, not the business response.
- Temporal registered Activities use fixed original epoch Signal callbacks. Pure `accept_update(state, payload)` validates binding, ordering and limits, appending only presentation; `_emit(..., bump=False)` leaves business revision untouched.
- `handle.stream_updates(...)` wraps `subscribe_events(...)`; lifecycle/cursors remain borrowed and observation-only. Receipt events provide end markers; they do not imply decision success or physical tool stop.

- [x] Write RED Local model→tool→model progress tests, observer cancellation, overflow/gap, native default compatibility, original approval/restart and receipt crash recovery.
- [x] Write RED Temporal pure-state/Activity/SDK-binding tests for identity fencing, replay/dedup and unchanged revision, callback failure and cancellation.
- [x] Implement authority bindings and common projection, run GREEN and original lifecycle/receipt suites.

## Task 3 — Evidence, installation and documentation

Files: add `docs/agent-stream-updates.md`, update Agent/model guides, capability/status/alignment docs, API reference and changelog; record review under architecture/reviews.

- [x] Fresh-context read-only review of the full diff. Fix actionable findings through RED→GREEN.
- [x] Freeze affected source/test hashes, run appropriate source modules with `-W error`.
- [x] Build a uniquely versioned private wheel; outside checkout, verify site-packages import, all product bytes/licenses/pip check and identical core test IDs.
- [x] Run Ruff/format/diff/link checks; retain all red/intermediate evidence and verify original archives/manifests unchanged.
- [x] State supported subset and actual Temporal evidence; do not grant live-Service/platform/model-quality qualification from offline results.

## Execution ledger

- Ruling: Use original event log/History to persist marked presentation, rather than a second progress authority. Durable cursors then reconnect without hidden client-owned execution; per-Attempt bounds limit History growth.
- Ruling: SDK signal publication has a fixed opt-in timeout and stops on transport failure; source reporting awaits only its bounded publication. Slow consumers never sit on the dispatch path. Explicit cancellation still propagates.
- Ruling: First tool progress API is async and explicit; synchronous tools keep normal lifecycle/receipt events. Avoid thread/stdout interception and detached publisher tasks in this increment.
- Ruling: Standalone Agent forwards the explicit policy; shared Agents cannot override host policy. This follows the existing H2 convenience/ownership boundary and avoids forcing basic users to assemble an Engine.
- Ruling: Preserve EOF-complete response on ordinary iterator cleanup failure, retain owned iterator and expose retry_stream_closes; do not close the borrowed Provider or change genuine source cancellation. A failed close blocks subsequent source dispatch until explicit cleanup succeeds.
- Evidence: initial callback-freeze test raced with a source edit and passed, so it is not RED evidence. A controlled old-binding rerun subsequently failed on caller-mutable Scope, then the binding was frozen through canonical JSON. Both logs retained.
- Evidence: first expanded source run had 1,369 passed / 2 failed; the newly imported policy_identity shadowed the TemporalRuntime authorization parameter. Alias fixed, original engine module 38 passed, four new core cases cover enabled/default and explicit/declared policy identity. First expanded source and installation evidence remain in first-expanded; final same-selection runs use a fresh private wheel.
- Evidence: final independent read-only review ran 92 cases with -W error, verified the three P2 lifecycle/performance fixes and authorization alias; no remaining actionable findings. Live Temporal Service and online model qualification are still open.
- Evidence: final selected source 84 modules / 1,375 passed and isolated installation 65 modules / 1,154 passed, both -W error with no skips/errors/failures. New private 448-product wheel 0.1.0a8+maintenance.80c39dc6dbd338b6 is separate from a8 and first-expanded. Final summary verifies matching core IDs, unchanged inputs and protected artifacts.

## Follow-up maintenance — 2026-10-29

The next user request was to continue optimization. Only stream_updates.py changed relative to the above validated product snapshot: rejected concurrent/foreign-loop source reads keep their original observer, and out-of-range huge integer timeouts consistently raise ValidationError. Source-read cleanup stays with the original subscription; projection errors keep the last valid public cursor. Added cancellation-during-iterator-close regression without changing the source cancellation/ownership protocol.

RED records: one concurrent observer failure; two huge timeout failures. Related 57 passed; independent read-only review 65 passed plus loop/cursor/from_identity probes. Final selected source 85 modules / 1,379 passed, isolated installation 66 modules / 1,158 passed; all use -W error with no failures/errors/skips. Private 448-product wheel 0.1.0a8+maintenance.349fff3c5a4ef63b is separate from prior packages.

A default full-suite sandbox diagnostic was interrupted after local-socket permission failures: 1,947 passed / 49 failed / 42 skipped / 6 errors. All 55 failure/error records are preserved. Their 52 unique tests passed independently with local-socket permission and original deadlines; this does not qualify the unexecuted remainder or the full SDK. Details and source/installation evidence are in [the maintenance record](../../../architecture/reviews/2026-10-29-stream-observation-boundaries.md). No new commit/push/publication or Alpha rebuild.
