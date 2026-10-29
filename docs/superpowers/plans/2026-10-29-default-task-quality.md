# Fixed default-chain task evaluation plan

> **Execution:** Native execution in the established checkout, final fresh read-only review; user opted into continuous bounded delivery. Reuse the accepted b103e54 product wheel, no new runtime feature/backend/adapter/topology.

**Goal:** Measure current installed Single Agent, semantic RAG, Plan and Team using frozen final configuration and strict existing independent oracles, with repeat, recovery, usage and timing evidence.

**Architecture:** Compose original evaluate_business/evaluate_semantic_rag/evaluate_orchestration in an external evaluation tool. Evaluators retain their original Local Action/receipt authority. Do not mutate prompts, cases, or scores after observing results. Existing old dev98/dev99 reports remain historical. Download only the previously authorized pinned MiniLM safetensors assets and isolated optional dependencies.

**Spec:** Active goal third batch; docs/delivery-gates.md first-stage I/C/L/Q/D and existing docs/task-evaluation.md, docs/phase1-semantic-rag.md. Earlier numbered stages are historical, not a new scope expansion.

## Global constraints

- One wheel: 0.1.0a8+maintenance.54f45574ad74b3af, SHA3ca80c594b9d5e18946f4c016c41655754baee6284c8b96d05bc1107b9f64463. Source451 product files remain fixed; do not rebuild original Alpha or maintenance wheels.
- Four original task suites: business8 / RAG8 / Plan5 / Team5, each repeats3. Overall>=90%, each case>=80% (three out of three at this sample size); protection/effect/citation/recovery checks must pass. Unattempted/failure rows stay in denominator.
- DeepSeek flash nonthinking, temperature0, max_output_tokens2048, per-call45s, each chain max96 generation calls. JSON mode business/RAG true, Plan/Team false. Business receipt gate; RAG typed_answers; Plan/Team completion gate+member verification. No live fallback to offline fixtures.
- Frozen local semantic model/revision/config is original MiniLM-L12-v2 e8f8c211226b894fcb81acc59f3b34ba3efd5f42,384D normalized float32 CPU/one thread/128tokens. max_embedding_calls128. No implicit remote code or model downloads during evaluation.
- Secret only in process memory, from named environment or masked terminal input. Never argv/file/report/log/commit; supplier response errors are redacted. Synthetic frozen task inputs only.
- Record source/wheel/dependency/config/dataset hashes before paid calls. New private report/evidence paths only, permissions0600/0700; all old reports/failures preserved.
- Record actual readiness,total,CPU/RSS, generation/model-call and control counts. Distinguish complete-response timing, HTTP timing, any explicit streaming probe and framework incremental output; unavailable metric stays null, no invented performance claim.
- Plan/Team fixed strategies do not prove autonomous planning. External adoption/parity and broader M1/R01–R26 separate. Local commit with one-command hook bypass+[skip ci]; no push/CI/publication.

## Task1 — Restore resources and freeze inputs

- [x] Confirm clean b103e54 and old artifact hashes; locate existing environments/assets first (missing on this host), no duplicate reuse claims.
- [x] Create new isolated install of exact wheel; resolve pinned optional semantic dependencies without mutating old installs. Fetch only11 original fixed-revision assets; validate SHA/sizes and local model identity/one-worker close.
- [x] Read-only DeepSeek /models preflight using masked process credential, record only status and model IDs. Confirm requested deepseek-flash, no automatic model switch.
- [x] Freeze all four original cases, effective flags/config and dependency/product hashes before live tasks.

## Task2 — Reproducible acceptance tool

Files: tools/evaluate_default_chains.py; tests/test_default_chain_acceptance.py.

- [x] RED tests prove acceptance rejects offline model_quality=null, missing/unattempted/duplicate repeats, per-case 2/3 despite overall>=90%, missing recovery/citation or mismatched dataset/config. No metric/case deletion to turn red into green.
- [x] Implement external composer and strict acceptance summary using original evaluator rows; report all4 chains separately. No SDK API/Engine changes. Masked input only on explicit request; no secret discovery.
- [x] Fresh evidence dirs, final input manifest, report digest, resource/timing facts and original reports retained. Offline rehearsal never closes Q; run actual installed suites before live work.

## Task3 — Current quality evidence and bounded closeout

- [x] Run four fixed three-repeat live suites sequentially with exact installed SDK. Preserve full outcomes and all failures. If actual product defect appears, diagnose before minimal fix; freeze a distinct candidate/config and whole-suite rerun only when justified, never mix scores.
- [x] Inspect independent business/effect/visible citation and original recovery evidence, not just evaluator passed totals. Terminal reconnect must not create model/embedding/tool calls. Existing unaffected lifecycle evidence reused by exact original artifact scope.
- [x] Record performance/usage/known versus unknown cost. Native first-delta measurement, if separately probed, is labeled separate from default complete task runs.
- [x] Related source/install tests, static/links/product/protected-artifact checks; fresh read-only review; update capability and quality docs without granting public/platform qualification.
- [x] Local commit only; mark goal complete only after all explicit bounded requirements have actual evidence, otherwise retain precise missing items.

## Review focus

1. Aggregate green must not hide a bad individual task, missing repeats or failed safety/recovery/citation metric.
2. Offline/model error/unknown usage cannot become real-quality or zero-cost evidence.
3. No oracle leaks into requests; final selection/config frozen before paid calls; exactly one artifact per reported run.
4. Credential/exception privacy and owned CPU/HTTP cleanup survive cancellation; no new dispatch during recovery.
5. Performance timers/counts measure named boundaries; native standalone probes are not default framework streaming or end-to-end results.

## Outcome and remaining goal requirement

Task1 resources/fixed inputs complete. Task2 external tool and reviewed false-green fixes complete (26 focused tests). Task3 exact installed live78/78 with170modelHTTP calls; independent cold78root/204unchangedSQLite/zeroHTTP+Embedding; actualmodelcancel/drain/GC proof. Source and installed12modules each307pass, no skips. Private451productbytes unchanged; original9artifacts preserved. Only local commit, no public/platform/parity claim.

All original reports and failures are retained; fixture corrections did not alter SDK/oracle/paid trial. Current goal remains active because observer cost has not been separated from recorded CPU/time. Next finite diagnostic batch compares fixed offline tasks with original/disabled counting, determines whether overhead belongs to the measurement tool, and changes no runtime feature or model score. No automatic backend/adapter/topology expansion or further quality trial. See [acceptance record](../../../architecture/reviews/2026-10-29-default-task-quality.md).
