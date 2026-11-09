---
title: Installation
description: Prepare a small Python environment and run Relf-Agent locally from source.
locale: en
slug: installation
sources: [docs/installation.md, docs/getting-started.md, docs/project-naming.md, docs/current-delivery.md]
---

## Requirements

Use **Python 3.11 or newer** in a virtual environment. The local introduction uses SQLite and an offline provider. It needs no model key, Redis, Temporal or Docker. Linux and macOS are the local development environments described by the project.

Relf-Agent is in Alpha. APIs and deployment combinations continue to evolve. See the repository's [implementation status (Chinese)](repo:docs/implementation-status.md) for the actual verification scope of each combination.

This guide pins the **0.1.0a8** source of Relf-Agent at `RalfNick/relf-agent`. Its distribution, Python import and CLI names are `relf-agent`, `relf_agent`, and `relf` / `relf-*`.

## Install from source

```bash
git clone https://github.com/RalfNick/relf-agent.git
cd relf-agent
git checkout 4bb46fe7a8935e6d13962a6c34e02519122c4c53
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
relf --version
python -m pip check
```

This documentation baseline is SDK **0.1.0a8**, commit `4bb46fe7a8935e6d13962a6c34e02519122c4c53`, verified on 2026-11-09. The checkout command pins it; `relf --version` should show `0.1.0a8`. The base dependencies include `httpx` and `jsonschema`. Newer source may differ; keep the original SDK and configuration for old runs.

> This site pins the public development branch `codex/callable-preview-fixes`, including HTTP GET, stream policy configuration and managed async nodes. That source has not merged into main and is not a new public package release. Maintenance retains the a8 base version: also check `git rev-parse HEAD`, because `relf --version` alone cannot identify capabilities. The original `0.1.0a8` archive, recommended private combination and individual validation wheels retain their separate scopes and do not contain every increment. Consult the [delivery record at this fixed source (Chinese)](repo:docs/current-delivery.md); the [current entry on main (Chinese)](current-delivery:docs/current-delivery.md) may lag development changes. This page adds no platform, live-model or independent-adoption qualification. The [historical a2 archive](https://github.com/RalfNick/relf-agent/releases/tag/v0.1.0a2) retains its evidence. Keep environments separate: old Runs, History and callable identity do not migrate automatically.

If you have a local wheel, install it in a virtual environment with `python -m pip install /actual/path/package.whl`. Verify its source and version.

## Complete a local task first

Continue to the [complete offline quickstart](/en/docs/quickstart/). Create a project, approve, resume and inspect the result on one page. This flow needs no optional dependencies or model credentials.

## Add optional dependencies

Run these commands from the source checkout with the virtual environment active. Installing clients does not provision external services.

| Purpose | Command |
| --- | --- |
| Development and tests | `python -m pip install -e '.[dev]'` |
| Skill document parsing | `python -m pip install -e '.[skills]'` |
| Tokenizer protocol accounting | `python -m pip install -e '.[tokenizer]'` |
| Text PDF ingestion | `python -m pip install -e '.[pdf]'` |
| Redis client | `python -m pip install -e '.[redis]'` |
| PostgreSQL client | `python -m pip install -e '.[postgres]'` |
| Temporal client and related dependencies | `python -m pip install -e '.[temporal]'` |

The complete extras are declared in [pyproject.toml](repo:pyproject.toml). Supply model credentials through the process environment, outside source control.

## Verify the installation

```bash
relf --help
relf --version
```

If `relf` cannot be found, activate the virtual environment and inspect `python -m pip show relf-agent`. Continue to the [quickstart](/en/docs/quickstart/) for local approval and cross-process recovery.
