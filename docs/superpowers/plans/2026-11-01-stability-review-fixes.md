# Stability review fixes implementation plan

> Execute bounded independent fixes in parallel with TDD, then one fresh consolidated review and exact installed-candidate verification. Local commits only.

**Goal:** Fix four P2 findings and source-distribution P3, unify current status, and freeze new SDK/application candidates while preserving prior artifacts.

**Architecture:** Preserve Harness proposal and Local/Temporal execution authority. Use transient direct executable pins without changing persisted tool manifests; repair the example's file search and stdin reader in place. No new features or default model calls.

**Spec:** User's 2026-11-01 instruction and the five reproduced findings from the preceding review; original app contract remains [design](../specs/2026-11-01-local-documents-assistant-design.md).

## Global Constraints

- Keep existing callable forms, explicit state/config identity rules, stable action/digest/effect identities and old Run recovery. Direct code checks must not recursively serialize closures, object state or credentials.
- Search every supported file byte within existing UTF-8/256KiB/128-entry limits; return bounded excerpts with accurate line/SHA provenance. Split each file only once per search.
- CLI input remains cancellable without an unjoinable thread; preserve complete buffered lines and partial UTF-8 input without blocking the event loop. Preserve observation vs explicit cancellation behavior.
- Current SDK sdist must include a complete standalone application source/config/demo/licenses. Dedicated SDK and app candidates have unique content-based versions and consistent metadata/module identities.
- No paid model calls, remote CI, pushes, publication or new capability work. Verify source, exact installed artifacts, affected contracts and recovery/dedup; retain all prior artifacts and failure logs.
- Work on existing codex/local-documents-assistant branch. Original user drafts are backed up before authorized status edits; old untracked review remains untouched and unstaged. Single-command hooksPath bypass only for local commits.

## Review Focus

- Generic plain/async/bound/partial/callable handler and reconciler drift before approval, dispatch and result adoption.
- Long single lines, matches beyond the former excerpt boundary, Chinese text, line provenance and bounded candidate memory; algorithmic splitting count rather than flaky speed thresholds.
- Open stdin pipes, several complete buffered lines, incomplete lines, EOF, Unicode boundaries and Ctrl-C; no busy reader or orphan input task.
- Source sdist extraction, standalone app packaging, exact installed metadata/imports/CLI with no checkout import; old manifests and original archived packages unchanged.
- Status consistency across SDK vs application qualification, historical sections, direct/default public entries and unknown or cancelled effects; no accidental new platform/model claims.

## Task 1 — generic tool executable pins

Files: src/relf_agent/tools.py, src/relf_agent/executors.py if necessary, focused new tool regression module.
Interfaces: ToolRegistry.register/get and RegisteredTool existing persisted manifest; PythonToolExecutor.execute/reconcile.

- [x] Add plain/async/bound/partial/callable and reconciler direct entry mutation regressions, plus approval and in-flight adoption coverage. Observe expected RED.
- [x] Add minimal transient checks preserving persisted implementation_digest and existing explicit config responsibility.
- [x] Pass new and adjacent tool/approval/recovery tests; record exact command/counts and limits.

## Task 2 — full-content bounded lexical search

Files: examples/local_documents/src/local_documents/documents.py and tests/test_local_documents_files.py.
Interfaces: DocumentLibrary.search/read; source records remain real line ranges/full SHA/truncation/id, unchanged tool schema.

- [x] Add the1630-byte missed-match case, mid-long-line matches, multiline/Han evidence checks and deterministic linear-work regression. Observe RED.
- [x] Scan full supported text, select bounded match-centred excerpts, split once and avoid materializing unbounded full excerpt results.
- [x] Pass all file/evidence tests, keep limits and safety behavior, record bounded performance comparison without wall-clock gating.

## Task 3 — persistent cancellable stdin

Files: examples/local_documents/src/local_documents/cli.py and tests/test_local_documents_cli.py or dedicated input tests.
Interfaces: read_line/input_line/chat and execute remain async; no model requests needed for input-only tests.

- [x] Add open-pipe '/help\\n/quit\\n', incomplete-line cancellation/EOF and multibyte buffering regressions. Observe RED without hanging test process.
- [x] Use persistent per-stream buffering/readiness handling preserving regular-file stdin and safe reader removal; no input thread.
- [x] Pass focused input and existing process/SIGINT/approval tests.

## Task 4 — packaging and state consistency

Files: MANIFEST.in, new packaging regression, docs/current-delivery.md, docs/README.md, docs/continuous-development.md, docs/local-documents-assistant.md and application README/pyproject dependency when freezing.

- [x] Reproduce incomplete root sdist, add packaging contract, include only necessary standalone application metadata/assets/licenses; validate extracted app installs.
- [x] Move stale construction wording to clearly dated history and keep one current SDK/app recommendation; retain original exact-package records.

## Task 5 — review, exact freeze and installed verification

- [x] Consolidated fresh-context review of this bounded change; one regression-first correction pass for important findings.
- [x] Run source impact suite and style; only then local implementation commit with [skip ci], single-command hook bypass.
- [x] Archive exact commit to isolated build directory; new SDK private version from product digest, new app private version with exact new SDK pin. Freeze wheel/sdist hashes; no overwrites of old artifacts.
- [x] In repository-external venv, verify metadata/module/CLI identity, all changed product bytes and same selected regression IDs, default startup plus original approval/restart/dedup workflows. No model quality or platform qualification borrowed.
- [x] Record acceptance, exact candidates and old artifact preservation; final local documentation commit; postcommit audit; no push/publication.

Final acceptance: source1320 passed /492.421s, exact installed1320 /395.389s (XML times authoritative), original1002 IDs retained and original1deselect unchanged. Separate packaging1 passed; production-only24 commands, SDK sdist app install and old/new default Local recovery passed. New SDK0.1.0a8+maintenance.f3da3f48e894e745 and app0.1.0+local.ddcf607b0929 from886c648, all17 old artifacts retained. Final documentation commit and its postcommit receipt are the closing operation, not a new development batch.
