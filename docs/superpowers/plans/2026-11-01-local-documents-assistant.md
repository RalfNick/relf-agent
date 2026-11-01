# Local Documents Assistant Implementation Plan

> Native execution under the user's standing continuous-execution preference. Read-only reconnaissance may run in parallel; one fresh whole-application review at the end. Preserve pre-existing uncommitted documents; local branch/commits only.

**Goal:** Ship and freeze one installed CLI local-documents assistant with actual-model, citation, approval and process-recovery evidence.

**Architecture:** Application logic in examples/local_documents, using the frozen SDK's Runtime/AgentSession, ToolRegistry, SQLiteStore and filesystem Workspace ports. No second execution authority and no new SDK capabilities.

**Tech Stack:** Python3.12 validation, Python>=3.11 syntax, existing httpx/jsonschema SDK; TOML + argparse + SQLite.

**Spec:** [design](../specs/2026-11-01-local-documents-assistant-design.md); current explicit user goal.

## Global Constraints

- CLI, single Agent, Markdown/TXT only, explicit model API; local state/output. API receives question, bounded history and necessary snippets.
- Exact SDK `0.1.0a8+maintenance.0608576182db502f`; retain original wheel SHA. No SDK rebuild if no SDK changes.
- Only create `.md` report files under a separate output root; require original approval, stable effect key and native write receipt; no overwrite.
- Actual citations come from accepted read-tool snapshots, with real path/line/SHA; no guessed references.
- Maintain observation cancellation vs explicit business cancel, durable Session seriality, original Run/action/digest and actual handler/resource closure.
- No credentials in files, output, package or git; live test credentials enter process memory only.
- User already supplied scope and continuous-execution preferences: use existing checkout/new local branch, record routine choices, no repeated plan approvals. No push/publication/remote CI.
- Verification is new example's own full suite plus affected SDK API tests and isolated install/live gates. SDK is unchanged; do not mechanically rerun its unrelated full matrix.

## Review Focus

1. Source traversal/symlink/unsupported files, truncation and forged/missing citations must not produce false file provenance.
2. Proposed path/content vs approved and saved bytes; denial, create-only conflict, duplicated commands and interrupted resume must not add writes.
3. Configuration/root changes and missing credentials must leave original tasks observable and prevent silently changing recovery identity.
4. Busy Session, wait timeout, explicit Ctrl-C cancel and failure/close retries must preserve original execution authority and actual resource ownership.
5. Fresh installed app must not depend on repository imports, untracked source or a fixture; live evidence never becomes external-adoption qualification.

## Task 1 — bounded files and evidence

Files: examples/local_documents/src/local_documents/{config,documents,evidence}.py; tests/test_local_documents_files.py.

- [x] Write tests for strict paths/config, real UTF-8 line excerpts, bounded search, unsupported files/unsafe paths and citation verification; observe RED before implementation.
- [x] Implement Config/load_config, DocumentLibrary.search/read, collect_sources/validate_answer/render_report using actual Workspace/read-only Run receipts.
- [x] Run all new file/evidence tests, preserve RED/GREEN records.

## Task 2 — managed application and CLI

Files: examples/local_documents/src/local_documents/{runtime,cli,__main__,__init__}.py; pyproject/config/demo files; tests/test_local_documents_runtime.py.

Interfaces: Config + DocumentLibrary + render_report from Task1; Application(config, provider=None) owns Runtime, documents and reports; submit(session_id, question, command_id, report_path=None), resume/approve/cancel/history/status. CLI main(argv=None) uses same paths without a source checkout.

- [x] Write real SQLite/Workspace tests: two-turn recall, approval preview zero report, rejection/cancel no effect, new process resume, same-command original receipt, create-only conflict, forged citation, connection failure and cancellation/close. Observe RED.
- [x] Register read tools and managed report effect; implement API/CLI with stable config identity, read-only inspection, clear state/error output and no auto-approval.
- [x] Run the complete example suite and affected Session/Runtime/Workspace contracts; 146 passed in41.50s; all prior failures retained. Application resume only observes unknown model actions; existing core retry behavior remains unchanged.

## Task 3 — install, real model, docs and freeze

Files: examples/local_documents/README.md, examples/README.md, own current-goal status additions, evals/results and architecture/reviews record. Build only example distribution in new ignored evidence paths.

- [ ] Provide exact wheel installation/config/start/chat/query/report/status/approve/resume/cancel/history commands, demo md/txt, privacy/data and recovery limits.
- [ ] Build example wheel once code stable; install frozen SDK + app outside checkout and verify no source imports. Run example full suite and README commands there.
- [ ] Call explicitly authorized DeepSeek with finite task/call limits: grounded QA and no evidence, report preview/reject, approval then fresh-process recovery, duplicate controls/submit, output SHA and continued Session. Keep live fixture/control failures and timing separately.
- [ ] One fresh read-only whole-application review; fix important findings once with regression-first checks. Freeze exact app+SDK hashes, local commits [skip ci] with single-command hook bypass, preserve user documents/old artifacts. Mark goal complete only on evidence for every mandatory gate.
