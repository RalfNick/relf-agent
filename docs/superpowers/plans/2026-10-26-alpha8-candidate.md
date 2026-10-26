# Alpha 8 Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Freeze `relf-agent==0.1.0a8` with the maintenance fixes through `ac92006`, prove the exact local installation, and commit locally without pushing or publishing.

**Architecture:** Reuse the existing package, release gate, preflight and manually dispatched release pipeline. Add an independent a8 manifest/checker/workflows; retain original a7 bytes and reports. No runtime behavior changes beyond the accepted maintenance baseline.

**Tech Stack:** Python 3.11–3.13, setuptools/build, pytest, existing hash-locked wheelhouse, GitHub Actions definitions only.

**Spec:** User request dated 2026-10-26; existing release protocol in `docs/releasing.md`, `tools/release_gate.py` and the frozen `tools/release_gate_manifest.alpha7.json`.

## Global Constraints

- Base: `ac920069e206f39d75ef0ab334f41b0619ca5a27`; distribution/import/CLI stay `relf-agent` / `relf_agent` / `relf`.
- Preserve original a7 artifacts, manifests, workflows, checkers, acceptance and historical failures.
- Keep original311 base,16 recovery,9 interruptions and two starters; add21 ownership and13 CLI cleanup checks. Keep locked dependencies, warning policy and original deadlines.
- Linux gate definitions retain2 CPU/2GiB/swap0/offline/Python3.11–3.13 serial requirements; actual remote/native qualification is not authorized in this batch.
- Only local commit, command-scoped `core.hooksPath=/dev/null`, `[skip ci]`; no push, remote CI, account configuration, website deployment or public release.
- Follow the established local main-branch release preparation workflow authorized in this conversation; all SDK changes relative to base are version/install presentation only. One final local commit is the requested deliverable.

## Review Focus

- An old/foreign version, artifact, commit, run attempt or repository must not qualify a8.
- Failed/private-draft staging must never publish or hand off partial bytes; old staging identities remain accepted only for their own versions.
- Fixed gate collection must include both recent maintenance regression modules with sorted-node identities and zero skipped gate tests.
- Current install/tutorial references must select a8; frozen a7 and the website's pinned a6 remain intact.
- Same-version archives must not be overwritten; source/archives/rebuilt installation must match, with final receipts outside the input archive to avoid self-reference.

### Task 1: Version and independent release controls

**Files:** Create a8 counterparts of `tests/test_alpha7_{release,distribution,workflows,publication}.py`, `tools/check_alpha7_publication.py`, `tools/release_gate_manifest.alpha7.json` and the three `.github/workflows/alpha7-*` files. Modify current-version assertions, `pyproject.toml`, `src/relf_agent/__init__.py`, the existing starter install hint and `tools/stage_alpha1_candidate.py`.

**Interfaces:** Existing `stage`, `release_preflight.prepare`, `verify_run`, `verify_evidence`, and `release_gate` contracts remain; only a8's version, prefixes and fixed manifest select the new candidate.

- [x] Add a8 tests first, observe missing metadata/prefix/checker/workflow failures, retain RED evidence.
- [x] Prepare independent a8 controls and current version/install identity; keep original a7 gate phases unchanged and add ownership21/cli_factory13 using actual sorted collection.
- [x] Run new release tests plus existing staging/publication/preflight regressions; expect zero failures and preserve historical inputs. If an existing observation test assumes terminal wait joins the host task, retain failure evidence and use a bounded observation-only idle fence without product, deadline or assertion weakening.

### Task 2: Current and historical release documentation

**Files:** Create `docs/releases/0.1.0a8.md`, `docs/alpha8-validation-status.md`, `docs/pypi-publishing-alpha7.md` and `architecture/reviews/2026-10-26-alpha8-candidate.md`. Update README/CHANGELOG, current install/tutorial, release, status and remaining-work entries.

**Interfaces:** Current documentation points to a8; immutable a7 records and website baseline keep their original versions. Snapshot docs are complete before final archive creation; final SHA/results are appended afterward only as external receipts.

- [x] Describe exactly the accepted CLI/Builder/router cleanup fixes, a8's370 checks/two starters, compatibility and unverified external steps.
- [x] Audit install references, local links and unchanged original history; resolve review findings before freezing.

### Task 3: Freeze exact pair and verify installation

**Files:** `dist/alpha8-candidate/` (ignored original archives, source inputs and evidence); final external `tools/release_gate_manifest.alpha8.json`.

**Interfaces:** `release_gate.prepare_artifacts`, `release_preflight.prepare`, unchanged gate runner and dependency lock operate on the exact new pair; no remote calls.

- [x] Build wheel/sdist offline with fixed build epoch, record source/product/test hashes; verify442 products and controlled version/install-only differences from base.
- [x] Run exact Mac installed gate311+16+9+21+13 and two approval/recovery starters; expect zero failures/errors/skips.
- [x] Rebuild from sdist; verify products, metadata,8CLI entries, licenses, pip check and relevant installed regressions with original test bytes and no src path.
- [x] Run Twine strict and offline source/preflight; append actual results and pending remote/native/account/public-install gates without borrowing original a7 or private maintenance results.

### Task 4: Final review, integrity and local commit

**Files:** Acceptance/delivery/hash receipts and current documentation; no new product behavior.

- [x] Fresh independent read-only review; correct actionable findings and revalidate only affected checks. No test-load concurrency with timing-sensitive installation checks.
- [x] Verify all protected hashes, committed product/test equivalence, Ruff, format, whitespace and local links; retain all failures.
- [x] Commit locally with single hooks bypass and `[skip ci]`; verify clean tree and permanent hooks unchanged. Report exact pair, local results and the point where remote authorization is required.


Execution receipts: `dist/alpha8-candidate/delivery.json` and `evidence/progress.md`. Initial release RED, original source-observation failure, diagnostic helper field error and installed-summary parser error are retained. Source598, original fixed370/two starters, rebuilt installation574/three optional YAML collection skips/two starters are independently recorded, not added together. Original a7 and website preserved; remote/public steps remain unauthorized and unqualified. The final local commit is recorded by Git and `evidence/local-commit.json`.
