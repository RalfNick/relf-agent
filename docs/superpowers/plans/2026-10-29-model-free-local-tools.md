# Model-free Local async Tool workflow plan

> **Execution:** Native implementation in the established checkout/local-commit workflow, followed by fresh read-only review. User's continuous-work instruction supplies scope and execution approval; no push or new backend.

**Goal:** Configure existing Local async Tool nodes through Profile/CLI without a dummy model, and prove their original approval/effect/recovery contracts.

**Evidence:** `GraphNode(tool=...)`, StaticWorkflowRuntime.tool and bounded parallel node frames already use original Tool Actions. Existing tests cover direct async calls, credits, approval/restart, unknown outcomes, cancellation/late receipt and receipt-window process crashes. The genuine config gap is RuntimeProfile refusing `providers={}` while LocalEngine already supports it. Do not add a generic NodeExecutor or restore the deferred Temporal Tool prototype.

**Design:** RuntimeProfile accepts an explicit providers object including empty; missing/wrong-type fields remain errors. Actual Agent admission still requires its configured/effective Provider before a Run is recorded. TemporalProfile retains its old nonempty-provider refusal. Existing graph starter gains an optional two-Tool application/config, using a synchronous registration factory with async handlers and the original ProfiledEngine, budgets and factory-based CLI controls. Original graph files and other templates stay unchanged except its README.

## Constraints

- No new execution authority, backend, topology/node type, adapter dependency or auto-discovery.
- Nonempty Profile normalization/identity and default starter behavior stay identical.
- Model-free means no configured Provider or model Action; credits still count Tool execution and are not money.
- Tools keep original Schema/default argument resolution, policy, approval, Action/effect identity, receipt adoption, unknown holds, physical stop and cleanup.
- Keep a7/a8, first/two-batch private wheels, all historical failures and original compatibility boundaries. New uniquely versioned private wheel only; default local commit, one-command hook bypass, no push/CI/publication.

## Task1 — Explicit empty Local provider mapping

Files: `runtime_config.py`, `temporal_profile.py`, `tests/test_model_free_workflow_profile.py`, existing Profile tests.

- [x] RED: empty Local Profile runs serial/parallel async Tool graphs, no model Actions, exact credits; JSON/TOML roundtrip; ordinary Agent and mixed Agent graph fail before recording a Run.
- [x] Preserve wrong-type/missing-provider config refusal; preserve Temporal empty-provider refusal before factory I/O.
- [x] Allow only explicit empty object by changing the Local declaration validation. Retain early guard in TemporalProfile.
- [x] Verify no changes to nonempty Profile identities and existing runtime/config/router tests.

## Task2 — Installed optional graph application

Files: new `workflow_tool_starter.py`, `starter.py`, model-free Profile tests, existing graph/starter tests.

- [x] RED: graph starter exports optional editable Tool graph, Profile, canonical factory and entry.
- [x] Add two async read-only fixture Tool nodes with input/output mapping and no model. Explicit factory registers tools; config contains providers={}; factory uses original ProfiledEngine and saved profile routing.
- [x] Default existing graph/runtime/main files remain unchanged. Docs show submit-only, inspect, resume and repeated-command behavior; factory construction is sync, handler execution async.
- [x] Exercise generated SDK/CLI outside checkout with the exact private wheel and zero source-path injection.

## Task3 — Recovery evidence and freeze

Files: `workflow_tool_crash_fixture.py`, `test_workflow_tools.py`, docs/acceptance/status.

- [x] Extend original process-crash fixture with explicit async handler variant, retain sync case; receipt commit crash then same Action/effect/result, only one handler call.
- [x] Verify model-free configured approval/duplicate control/reopen, unknown query or manual evidence without redispatch, cancel/late result and owned lifecycle using existing core paths.
- [x] Update stale Tool guide statements and Profile requirements, distinguish Agent limits from Workflow Tool actions, explain async factory versus async handler.
- [x] Source/install affected matrices, no-model installed workflow, raw budgets/control/call evidence, old artifact hashes, product/license/static/links and fresh read-only review.
- [x] Freeze one recommended private artifact, report remaining real task-quality gates; local commit only.

## Review focus

1. No hidden fallback model for empty mapping; Agent/bound effective Provider still checked by original admission.
2. Empty is explicit; malformed/missing declarations cannot become empty by coercion.
3. Shared RuntimeProfile relaxation cannot broaden Temporal or defer its rejection into service/client creation.
4. Sync registration factories cannot perform unowned async startup; no CLI support claimed for arbitrary async factories.
5. Receipt-window recovery and unknown effects must keep original identity, credits and actual stop obligations, not just final result equality.

## Outcome

Source339 / exact private installed339, no failures/skips, both -Werror. All28templates compared: only graph README+fournewassets changed. Independent review no Important/Critical; minor app-error brevity addressed in guide. Profile nonempty identities same as prior SDK; old SDK refuses explicit empty. Seven installed document commands confirmed no model Action, exact credits, duplicate Run and original CLI recovery. Final product/license/protected-artifact/static/link freeze recorded in `dist/model-free-tools-20261029/validation-summary.json`; acceptance and unique private wheel in [delivery record](../../../architecture/reviews/2026-10-29-model-free-local-tools.md). No new engine, adapter or Temporal Tool capability. Local commit only; goal remains active for fixed final-config task evaluation.
