# Installed support journey implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. Implementation stays in this session; one fresh read-only review before freezing. User has supplied the delivery scope and opted out of repeated design/permission rounds.

**Goal:** Let an installed default starter provide one editable Agent → Session → RAG → Facts → Workflow application and explicit model/tool/memory replacement examples, without repository imports or additional templates.

**Architecture:** Extend the existing oncall generator with application files only. Package the existing support journey as an editable asset, keeping the repository example byte-identical. Its `main(argv=None, *, provider=None, tools=None, memory=None)` and `run(args, provider, *, tools=None, memory=None)` accept borrowed components; defaults keep current SQLite execution and memory. A generated customization module supplies a normal Provider and async Python tool, with an explicitly documented InMemoryMemory alternative. Runtime, Profile, Action and execution authorities do not change.

**Tech stack:** Existing Python3.11+, starter, Agent/Runtime, SQLite/InMemory memory, Provider and ToolRegistry. No new dependency or network service.

**Spec:** Latest user objective and [first-batch freeze](../../../architecture/reviews/2026-10-29-stream-batch-freeze.md). This is the developer-experience slice of batch2; async node drafts, backend expansion and task-quality evaluation stay separate.

## Design choices and constraints

- Reuse the default oncall template, rather than add a 29th template or require users to download unversioned examples.
- Export actual editable application sources, rather than introduce a generic plugin loader or another framework facade.
- Preserve existing oncall runtime/approval commands and non-oncall templates. New component parameters affect only the optional application example.
- `None` alone selects a default; an explicit invalid or false-valued component must not silently become the default. Configured live Provider options and an injected Provider are mutually exclusive.
- Injected resources remain borrowed. InMemoryMemory is disposable, not a durable backend or a new execution store. Existing persistent SQLite remains the default for recovery.
- Keep first-batch private wheel and a8/a7 artifacts immutable. Build a new uniquely versioned private installation only if package bytes change; no push, CI, deployment or publication.

## Task1 — Editable application and replacement seams

Files: `examples/support_journey.py`, new `src/relf_agent/_support_journey.py`, new `tests/test_support_journey_customization.py`.

- [x] Write failing tests: injected Provider plus async tool is actually used; borrowed memory persists across in-process Session Turns and remains caller-owned; false-valued Provider is preserved; explicit live settings plus injection reject before a database is created.
- [x] Add only the two application-level signatures above; defaults keep old stage behavior. Statistics must not assume arbitrary Providers have `.calls`.
- [x] Keep packaged asset and repository example identical. Run current five-stage/duplicate-command and cross-process Session tests.

## Task2 — Existing starter and installation path

Files: `src/relf_agent/starter.py`, new `src/relf_agent/_support_customization.py`, tests from Task1 plus installed starter tests.

- [x] RED: default `create_starter` must export `agent_app/journey.py` and `agent_app/customize.py`; generated example must run outside checkout.
- [x] Export the assets only for oncall. Preserve existing default files and atomically generated destination rules. Document complete installed commands in generated README.
- [x] Default customization uses persistent SQLite, an explicit custom Provider and async lookup. Document the single InMemoryMemory substitution as ephemeral; do not pretend it can recover across process loss.
- [x] Verify five stages, replay, Session restart, customization and failure diagnostics in the same private installed wheel, no src/PYTHONPATH injection.

## Task3 — Tutorial, review and freeze

Files: `docs/support-journey.md`, `docs/getting-started.md`, `docs/extending.md`, index/status/queue, acceptance record.

- [x] Lead with generated installed application; retain fixed old tutorial/source links and old package boundaries.
- [x] Explain three replacement hooks, borrowed lifetime, fixed identities, memory durability, and when existing Agent/Runtime/Profile is appropriate. Use existing Profile docs, not another configuration layer.
- [x] Provide symptoms and next commands for wrong environment, missing Provider config, changed release, Session busy, observation timeout and incomplete close.
- [x] Run affected source/install tests and unchanged default-starter approval/recovery tests; confirm license/product bytes, original artifact hashes, Ruff/format/diff/links.
- [x] Fresh read-only review, then local commit with no push. Freeze the unique recommended private artifact and state the remaining async-node and task-quality work.

## Review focus

1. A generator-only change must not edit an existing app, change its original approval factory, or add sources to unrelated templates.
2. A component whose `bool` is false still needs exact dispatch; arbitrary Provider counters are not part of the port.
3. Swapping memory does not swap execution authority; disposable memory must not claim durable restart.
4. Runtime owns its Engine, injected adapters stay borrowed, and failed close must not be described as safe to discard resources.
5. Source examples and installed assets must match; an installed test cannot obtain framework code from checkout.

## Final ledger

Hooks/export valid REDs and all earlier errors retained. Async-memory reviewer P2 reproduced with ThreadedMemoryAdapter under -W error then fixed in application only. Source92 / independent installation92 passed; all28 templates independently compared, original oncall runtime and other27 unchanged. Exact private450-product artifact and generated documentation smoke verified. No backend/port/topology expansion or online model call. Local commit receipt is retained with evidence after the final audit; push/CI/deployment/publication remain unauthorized.
